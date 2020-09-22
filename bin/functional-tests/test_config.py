#!/usr/bin/env python3
"""
This file is for system testing the Astronomer Helm chart.

Testinfra is used to create test fixures.

testinfra simplifies and provides syntactic sugar for doing
execs into a running pods.
"""

import json
import os
import docker
import time
import yaml
from kubernetes import client, config
from kubernetes.client.rest import ApiException

def test_prometheus_user(prometheus):
    """ Ensure user is 'nobody'
    """
    user = prometheus.check_output('whoami')
    assert user == "nobody", \
        f"Expected prometheus to be running as 'nobody', not '{user}'"

def test_houston_config(houston_api):
    """ Make assertions about Houston's configuration
    """
    data = houston_api.check_output("echo \"config = require('config'); console.log(JSON.stringify(config))\" | node -")
    houston_config = json.loads(data)
    assert 'url' not in houston_config['nats'].keys(), \
        f"Did not expect to find 'url' configured for 'nats'. Found:\n\n{houston_config['nats']}"
    assert len(houston_config['nats']['servers']), \
        f"Expected to find 'servers' configured for 'nats'. Found:\n\n{houston_config['nats']}"
    for server in houston_config['nats']:
        assert 'localhost' not in server, \
            f"Expected not to find 'localhost' in the 'servers' configuration. Found:\n\n{houston_config['nats']}"

def test_houston_can_reach_prometheus(houston_api):
    houston_api.check_output("wget -qO- --timeout=1 http://astronomer-prometheus.astronomer.svc.cluster.local:9090/targets")

def test_nginx_can_reach_default_backend(nginx):
    nginx.check_output("curl -s --max-time 1 http://astronomer-nginx-default-backend:8080")

def test_prometheus_targets(prometheus):
    """ Ensure all Prometheus targets are healthy
    """
    data = prometheus.check_output("wget -qO- http://localhost:9090/api/v1/targets")
    targets = json.loads(data)['data']['activeTargets']
    for target in targets:
        assert target['health'] == 'up', \
            'Expected all prometheus targets to be up. ' + \
            'Please check the "targets" view in the Prometheus UI' + \
            f" Target data from the one that is not up:\n\n{target}"


def test_core_dns_metrics_are_collected(prometheus):
    """ Ensure CoreDNS metrics are collected.

    This test should work in CI and locally because Kind uses CoreDNS
    """
    data = prometheus.check_output("wget -qO- http://localhost:9090/api/v1/query?query=coredns_dns_request_count_total")
    parsed = json.loads(data)
    assert len(parsed['data']['result']) > 0, \
        f"Expected to find a metric coredns_dns_request_count_total, but we got this response:\n\n{parsed}"

def test_houston_metrics_are_collected(prometheus):
    """ Ensure Houston metrics are collected and prefixed with 'houston_'
    """
    data = prometheus.check_output("wget -qO- http://localhost:9090/api/v1/query?query=houston_up")
    parsed = json.loads(data)
    assert len(parsed['data']['result']) > 0, \
        f"Expected to find a metric houston_up, but we got this response:\n\n{parsed}"


def test_prometheus_config_reloader_works(prometheus, kube_client):
    """ 
    Ensure that Prometheus reloads its config when the cofigMap is updated
    and the reloader sidecar triggers the reload
    """
    # define new value we'll use for the config change
    new_scrape_interval = "31s"

    # get the current configmap
    orig_cm = kube_client.read_namespaced_config_map("astronomer-prometheus-config", "astronomer")

    prom_config = yaml.safe_load(orig_cm.data['config'])
    # modify the configmap
    prom_config['global']['scrape_interval'] = new_scrape_interval
    new_body = {
        "apiversion": "v1",
        "kind": "ConfigMap",
        "data": {
            "config": yaml.dump(prom_config)
        }
    }

    try:
        # update the configmap
        kube_client.patch_namespaced_config_map(
            name="astronomer-prometheus-config",
            namespace="astronomer",
            body=new_body
        )
    except ApiException as e:
        print("Exception when calling CoreV1Api->patch_namespaced_config_map: %s\n" % e)
    
    # This can take more than a minute.
    i = 0 
    while i < 12: 
        data = prometheus.check_output("wget -qO- http://localhost:9090/api/v1/status/config")
        j_parsed = json.loads(data)
        # print(parsed['data']['yaml']['config']['global'])
        y_parsed = yaml.safe_load(j_parsed['data']['yaml'])
        if y_parsed['global']['scrape_interval'] != "30s":
            print(y_parsed['global']['scrape_interval'])
            break
        else:
            time.sleep(10)
        i+=1
        

    # set the config back to it's original settings
    prom_config['global']['scrape_interval'] = "30s"
    new_body = {
        "apiversion": "v1",
        "kind": "ConfigMap",
        "data": {
            "config": yaml.dump(prom_config)
        }
    }

    try:
        # update the configmap
        kube_client.patch_namespaced_config_map(
            name="astronomer-prometheus-config",
            namespace="astronomer",
            body=new_body
        )
    except ApiException as e:
        print("Exception when calling CoreV1Api->patch_namespaced_config_map: %s\n" % e)


    assert y_parsed['global']['scrape_interval'] != "30s", \
        f"Expected the prometheus config file to change"
