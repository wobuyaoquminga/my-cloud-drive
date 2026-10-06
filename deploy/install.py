"""Run with sudo python3. Installs Cloudreve without modifying existing applications."""
import argparse
import os
import platform
import hashlib
import pathlib
import secrets
import shutil
import subprocess
import tarfile
import urllib.request

parser = argparse.ArgumentParser(description='Install Cloudreve on Ubuntu 24.04 x86_64')
parser.add_argument('--archive', type=pathlib.Path, help='Official release archive downloaded in advance')
args = parser.parse_args()
if os.geteuid() != 0 or platform.machine() != 'x86_64':
    raise SystemExit('Requires root and Linux x86_64.')
VERSION = '4.19.1'
ASSET = f'cloudreve_{VERSION}_linux_amd64.tar.gz'
EXPECTED = '287a1f59adb1249af15cd550b191d2fa71132bfd125fead8578f20152c4b99de'

def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)

if pathlib.Path('/etc/cloudreve/conf.ini').exists():
    raise SystemExit('Existing Cloudreve config found; refusing to overwrite.')

existing = subprocess.check_output(['mysql', '-NBe', "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME='cloudreve'; SELECT User FROM mysql.user WHERE User='cloudreve';"], text=True)
if existing.strip():
    raise SystemExit('Cloudreve database/account already exists; refusing to overwrite.')
if pathlib.Path('/var/lib/cloudreve-storage.img').exists():
    raise SystemExit('Existing storage image found; refusing to format.')
if shutil.disk_usage('/var/lib').free < 12 * 1024**3:
    raise SystemExit('At least 12 GiB free disk space is required.')
base = pathlib.Path('/opt/cloudreve')
base.mkdir(mode=0o755, exist_ok=True)
archive = base / ASSET
uploaded = args.archive or pathlib.Path('/nonexistent-cloudreve-archive')
if args.archive and (not uploaded.is_file() or hashlib.sha256(uploaded.read_bytes()).hexdigest() != EXPECTED):
    raise SystemExit('Provided release archive is missing or has the wrong SHA-256.')
if uploaded.exists() and hashlib.sha256(uploaded.read_bytes()).hexdigest() == EXPECTED:
    archive.write_bytes(uploaded.read_bytes())
else:
    with urllib.request.urlopen(f'https://github.com/cloudreve/cloudreve/releases/download/{VERSION}/{ASSET}', timeout=60) as response:
        archive.write_bytes(response.read())
if hashlib.sha256(archive.read_bytes()).hexdigest() != EXPECTED:
    raise SystemExit('Release checksum mismatch')
with tarfile.open(archive) as tf:
    member = next(m for m in tf.getmembers() if pathlib.PurePosixPath(m.name).name == 'cloudreve' and m.isfile())
    (base / 'cloudreve').write_bytes(tf.extractfile(member).read())
(base / 'cloudreve').chmod(0o755)

if subprocess.run(['id', 'cloudreve'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
    run('useradd', '--system', '--home', '/var/lib/cloudreve', '--shell', '/usr/sbin/nologin', 'cloudreve')

pool = pathlib.Path('/var/lib/cloudreve')
pool.mkdir(exist_ok=True)
image = pathlib.Path('/var/lib/cloudreve-storage.img')
if image.exists() or any(pool.iterdir()):
    raise SystemExit('Storage already exists; refusing to format.')
run('fallocate', '-l', str(10 * 1024**3), str(image))
image.chmod(0o600)
run('mkfs.ext4', '-q', '-m', '0', '-L', 'cloudreve-data', str(image))
mount_line = f'{image} {pool} ext4 loop,nodev,nosuid,noexec 0 0\n'
with open('/etc/fstab', 'a') as f:
    f.write(mount_line)
run('mount', str(pool))
run('chown', 'cloudreve:cloudreve', str(pool))
(pool / 'data').mkdir(exist_ok=True)
run('chown', 'cloudreve:cloudreve', str(pool / 'data'))
(base / 'data').symlink_to(pool / 'data', target_is_directory=True)

password = secrets.token_hex(32)
sql = f"""CREATE DATABASE cloudreve CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'cloudreve'@'127.0.0.1' IDENTIFIED BY '{password}';
GRANT ALL PRIVILEGES ON cloudreve.* TO 'cloudreve'@'127.0.0.1';
"""
run('mysql', input=sql, text=True)
config_dir = pathlib.Path('/etc/cloudreve')
config_dir.mkdir(mode=0o750)
run('chown', 'root:cloudreve', str(config_dir))
config = config_dir / 'conf.ini'
config.write_text(f'''[System]
Mode = master
Listen = 127.0.0.1:5212
ProxyHeader = X-Real-IP
LogLevel = info
GracePeriod = 30

[Database]
Type = mysql
Host = 127.0.0.1
Port = 3306
User = cloudreve
Password = {password}
Name = cloudreve
Charset = utf8mb4
''')
config.chmod(0o640)
run('chown', 'root:cloudreve', str(config))
pathlib.Path('/etc/systemd/system/cloudreve.service').write_text('''[Unit]
Description=Cloudreve personal cloud drive
After=network.target mysql.service
RequiresMountsFor=/var/lib/cloudreve

[Service]
Type=simple
User=cloudreve
Group=cloudreve
WorkingDirectory=/var/lib/cloudreve
ExecStart=/opt/cloudreve/cloudreve -c /etc/cloudreve/conf.ini
Restart=on-failure
RestartSec=5
TimeoutStopSec=45
Environment=GOMEMLIMIT=256MiB
MemoryHigh=320M
MemoryMax=512M
CPUQuota=100%
UMask=0027
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
ReadWritePaths=/var/lib/cloudreve
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
''')
run('systemctl', 'daemon-reload')
run('systemctl', 'enable', '--now', 'cloudreve')
print('Installed Cloudreve', VERSION, 'with verified SHA256, private MySQL schema and 10 GiB storage pool.')
