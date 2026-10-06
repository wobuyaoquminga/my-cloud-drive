"""Create a consistent manual backup of Cloudreve only. Run using sudo python3."""
import datetime
import gzip
import pathlib
import shutil
import subprocess

root = pathlib.Path('/var/backups/cloudreve')
root.mkdir(mode=0o700, exist_ok=True)
stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
target = root / stamp
target.mkdir(mode=0o700)
def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)
# The file payload may take up to the storage-pool size, so keep this initial backup
# small and refuse manual server-side backups after the pool passes 1 GiB.
size = int(subprocess.check_output(['du','-sb','/var/lib/cloudreve'], text=True).split()[0])
if size > 1024**3:
    raise SystemExit('More than 1 GiB data: stream an off-server backup instead of duplicating files on this server.')
run('systemctl', 'stop', 'cloudreve')
try:
    with gzip.open(target / 'database.sql.gz', 'wb') as output:
        process = subprocess.Popen(['mysqldump', '--single-transaction', '--no-tablespaces', '--databases', 'cloudreve'], stdout=subprocess.PIPE)
        shutil.copyfileobj(process.stdout, output)
        process.stdout.close()
        if process.wait() != 0:
            raise RuntimeError('Database backup failed')
    paths = ['var/lib/cloudreve', 'etc/cloudreve', 'etc/systemd/system/cloudreve.service',
             'opt/cloudreve/branding', 'etc/nginx/snippets/cloudreve-proxy.conf']
    for optional in ['etc/nginx/sites-available/cloudreve.conf', 'etc/nginx/sites-available/chat-ip.conf',
                     'etc/nginx/conf.d/cloudreve-ratelimit.conf']:
        if pathlib.Path('/' + optional).exists():
            paths.append(optional)
    run('tar', '-czf', str(target / 'files-config.tar.gz'), '-C', '/', *paths)
finally:
    run('systemctl', 'start', 'cloudreve')
for f in target.iterdir(): f.chmod(0o600)
print('Consistent Cloudreve-only backup:', target)
