import pathlib
import subprocess

def run(*args):
    subprocess.run(args, check=True)

home = pathlib.Path(__file__).resolve().parent
site = pathlib.Path('/etc/nginx/sites-available/cloudreve.conf')
if site.exists():
    raise SystemExit('Cloudreve site already exists; refusing to overwrite.')
branding = pathlib.Path('/opt/cloudreve/branding')
branding.mkdir(exist_ok=True)
for name in ['logo.svg', 'icon.svg', 'admin.html']:
    (branding / name).write_bytes((home / name).read_bytes())
body = pathlib.Path('/var/lib/cloudreve/nginx-body')
body.mkdir(mode=0o700, exist_ok=True)
run('chown', 'www-data:www-data', str(body))
pathlib.Path('/etc/nginx/snippets/cloudreve-proxy.conf').write_bytes((home / 'cloudreve-proxy.conf').read_bytes())
site.write_bytes((home / 'cloudreve-nginx.conf').read_bytes())
enabled = pathlib.Path('/etc/nginx/sites-enabled/cloudreve.conf')
enabled.symlink_to(site)
try:
    run('nginx', '-t')
except subprocess.CalledProcessError:
    enabled.unlink()
    raise
run('systemctl', 'reload', 'nginx')
print('Cloudreve HTTPS enabled on port 443; existing server blocks preserved.')
