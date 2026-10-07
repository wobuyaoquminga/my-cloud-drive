"""Provide an administrator login URL excluded even by the original offline worker."""
import argparse
import datetime
import pathlib
import shutil
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--nginx-site', type=pathlib.Path, default=pathlib.Path('/etc/nginx/sites-available/cloudreve.conf'))
args = parser.parse_args()
site = args.nginx_site
original = site.read_text()
route = '    location = /f/admin { alias /opt/cloudreve/branding/admin.html; default_type text/html; add_header Cache-Control "no-store" always; }\n'
anchor = '    location /branding/'
updated = original
if 'location = /f/admin ' not in updated:
    if updated.count(anchor) != 1:
        raise SystemExit('Expected branding route not found; refusing to change nginx.')
    updated = updated.replace(anchor, route + anchor, 1)
old_route = 'location = /manage { alias /opt/cloudreve/branding/admin.html; default_type text/html; }'
updated = updated.replace(old_route, 'location = /manage { return 302 /f/admin; }')
backup = pathlib.Path('/var/backups/cloudreve') / ('direct-admin-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
backup.mkdir(parents=True, mode=0o700)
shutil.copy2(site, backup / 'nginx.conf')
site.write_text(updated)
try:
    subprocess.run(['nginx', '-t'], check=True)
    subprocess.run(['systemctl', 'reload', 'nginx'], check=True)
except subprocess.CalledProcessError:
    site.write_text(original)
    raise
print('Direct administrator login available at /f/admin; backup:', backup)
