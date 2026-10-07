"""Reuse the existing IP certificate and port while preserving Chat API and WS routes."""
import datetime
import pathlib
import shutil
import subprocess

path = pathlib.Path('/etc/nginx/sites-available/chat-ip.conf')
if not path.exists():
    path = pathlib.Path('/etc/nginx/sites-enabled/chat-ip.conf').resolve()
original = path.read_text()
if 'listen 443 ssl;' not in original or original.count('location / {\n        proxy_pass http://127.0.0.1:8082;') != 1:
    raise SystemExit('Unexpected Chat proxy config; refusing to change routes.')
backup = pathlib.Path('/var/backups/cloudreve')
backup.mkdir(mode=0o700, exist_ok=True)
shutil.copy2(path, backup / ('chat-ip.conf.' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S')))
old = '    location / {\n        proxy_pass http://127.0.0.1:8082;'
# Capture the existing block as-is and duplicate it for API / WS / status.
start = original.index(old)
end = original.index('\n    }', start) + len('\n    }')
chat_block = original[start:end]
blocks = '\n'.join(chat_block.replace('location / {', 'location ' + route + ' {', 1)
                   for route in ['/api/', '/ws', '= /chat-status'])
cloud = '''
    client_max_body_size 64m;
    client_body_temp_path /var/lib/cloudreve/nginx-body 1 2;
    location = /manage { alias /opt/cloudreve/branding/admin.html; default_type text/html; }
    location /branding/ { alias /opt/cloudreve/branding/; }
    location = /api/v4/session/token {
        limit_req zone=cloudreve_auth burst=10 nodelay;
        limit_req_status 429;
        include /etc/nginx/snippets/cloudreve-proxy.conf;
    }
    location = /api/v4/user {
        limit_req zone=cloudreve_register burst=2 nodelay;
        limit_req_status 429;
        include /etc/nginx/snippets/cloudreve-proxy.conf;
    }
    location /api/v4/ {
        include /etc/nginx/snippets/cloudreve-proxy.conf;
    }
    location / {
        include /etc/nginx/snippets/cloudreve-proxy.conf;
    }
'''
# Status forwards to the backend root rather than an unknown /chat-status endpoint.
blocks = blocks.replace('location = /chat-status {\n        proxy_pass http://127.0.0.1:8082;',
                        'location = /chat-status {\n        proxy_pass http://127.0.0.1:8082/;')
updated = original[:start] + blocks + cloud + original[end:]
rate_file = pathlib.Path('/etc/nginx/conf.d/cloudreve-ratelimit.conf')
rate_file.write_text('''limit_req_zone $binary_remote_addr zone=cloudreve_auth:1m rate=2r/s;
limit_req_zone $binary_remote_addr zone=cloudreve_register:1m rate=1r/m;
''')
private_site = pathlib.Path('/etc/nginx/sites-enabled/cloudreve.conf')
if private_site.is_symlink():
    private_site.unlink()
path.write_text(updated)
try:
    subprocess.run(['nginx', '-t'], check=True)
    subprocess.run(['systemctl', 'reload', 'nginx'], check=True)
except subprocess.CalledProcessError:
    path.write_text(original)
    rate_file.unlink()
    raise
print('Port 443 now serves Cloudreve; Chat /api/, /ws, and /chat-status preserved. Original config backed up.')
