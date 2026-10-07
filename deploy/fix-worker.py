"""Exclude the separate administrator dashboard from Cloudreve's offline navigation."""
import argparse
import datetime
import pathlib
import shutil
import subprocess
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument('--nginx-site', type=pathlib.Path, default=pathlib.Path('/etc/nginx/sites-available/cloudreve.conf'))
parser.add_argument('--worker-path', type=pathlib.Path, help='Existing nginx worker alias; preserve other route exclusions')
args = parser.parse_args()
if args.worker_path:
    worker = args.worker_path.read_text(encoding='utf-8')
else:
    with urllib.request.urlopen('http://127.0.0.1:5212/sw.js', timeout=15) as response:
        worker = response.read().decode('utf-8')
if 'Administrator dashboard navigation fix' in worker:
    print('Administrator worker exclusions already installed.')
    raise SystemExit(0)
marker = 'denylist:['
if worker.count(marker) != 1 or 'createHandlerBoundToURL("index.html")' not in worker:
    raise SystemExit('Unexpected upstream worker; refusing to modify it.')
worker = worker.replace(marker, r'denylist:[/^\/manage(?:\/|$)/,/^\/branding\//,', 1)
# Activate this update immediately and recover tabs showing the cached not-found page.
lifecycle = '''// Administrator dashboard navigation fix; upstream worker remains GPL-3.0.
self.skipWaiting();
self.addEventListener('activate', event => event.waitUntil((async () => {
  await self.clients.claim();
  for (const client of await self.clients.matchAll({type: 'window', includeUncontrolled: true})) {
    const url = new URL(client.url);
    if (url.pathname === '/manage' || url.pathname === '/branding/admin.html') {
      client.navigate(client.url).catch(() => {});
    }
  }
})()));
'''
target = args.worker_path or pathlib.Path('/opt/cloudreve/branding/sw.js')
site = args.nginx_site
original = site.read_text()
directive = 'location = /sw.js'
if args.worker_path or directive in original:
    updated = original
else:
    anchor = '    location /branding/'
    if original.count(anchor) != 1:
        raise SystemExit('Expected branding location not found; refusing to change nginx.')
    route = '    location = /sw.js { alias /opt/cloudreve/branding/sw.js; default_type application/javascript; add_header Cache-Control "no-cache" always; }\n'
    updated = original.replace(anchor, route + anchor, 1)
backup = pathlib.Path('/var/backups/cloudreve') / ('worker-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
backup.mkdir(parents=True, mode=0o700)
shutil.copy2(site, backup / 'nginx.conf')
old_worker = target.read_bytes() if target.exists() else None
if old_worker is not None:
    (backup / 'worker-original.js').write_bytes(old_worker)
target.write_text(lifecycle + worker, encoding='utf-8')
target.chmod(0o644)
site.write_text(updated)
try:
    subprocess.run(['nginx', '-t'], check=True)
    subprocess.run(['systemctl', 'reload', 'nginx'], check=True)
except subprocess.CalledProcessError:
    site.write_text(original)
    if old_worker is None:
        target.unlink()
    else:
        target.write_bytes(old_worker)
    raise
print('Worker routing fixed; nginx configuration saved:', backup)
