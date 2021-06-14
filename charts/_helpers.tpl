{{ define "sidecar_nginx_auth_headers" -}}
internal;
proxy_pass_request_body     off;
proxy_set_header            Content-Length          "";
proxy_set_header            X-Forwarded-Proto       "";
proxy_set_header            Host                    houston.{{ .Values.global.baseDomain }};
## new added
proxy_set_header            X-Original-URL          https://$http_host$request_uri;
proxy_set_header            X-Original-Method       $request_method;
##
proxy_set_header            X-Real-IP               $remote_addr;
proxy_set_header            X-Forwarded-For         $remote_addr;
proxy_set_header            X-Auth-Request-Redirect $request_uri;
proxy_buffering             off;
proxy_buffer_size           4k;
proxy_buffers               4 4k;
proxy_request_buffering     on;
proxy_http_version          1.1;
proxy_ssl_server_name       on;
proxy_pass_request_headers  on;
client_max_body_size        1024m;
proxy_pass  https://houston.{{ .Values.global.baseDomain }}/v1/authorization;
{{- end }}

{{ define "sidecar_nginx_location" -}}
auth_request     /auth;
# setting custom headers required by authentication
auth_request_set $auth_status $upstream_status;
auth_request_set $auth_cookie $upstream_http_set_cookie;
add_header       Set-Cookie $auth_cookie;
auth_request_set $authHeader0 $upstream_http_authorization;
proxy_set_header 'authorization' $authHeader0;
auth_request_set $authHeader1 $upstream_http_username;
proxy_set_header 'username' $authHeader1;
auth_request_set $authHeader2 $upstream_http_email;
proxy_set_header 'email' $authHeader2;
error_page 401 = @401_auth_error;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection 'connection_upgrade';
proxy_set_header X-Real-IP              $remote_addr;
proxy_set_header X-Forwarded-For        $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_cache_bypass $http_upgrade;
proxy_set_header X-Original-Forwarded-For $http_x_forwarded_for;
#proxy_set_header  X-Forwarded-Proto https;
proxy_connect_timeout                   15s;
proxy_send_timeout                      600s;
proxy_read_timeout                      600s;
proxy_buffering                         off;
proxy_buffer_size                       4k;
proxy_buffers                           4 4k;
proxy_max_temp_file_size                1024m;
proxy_request_buffering                 on;
proxy_http_version                      1.1;
proxy_cookie_domain                     off;
proxy_cookie_path                       off;
proxy_redirect                          off;
{{- end }}

