"""Build the administrator extension without rebuilding the unchanged official UI."""
import argparse
import hashlib
import io
import os
import pathlib
import struct
import subprocess
import tarfile
import urllib.request
import zipfile

parser = argparse.ArgumentParser()
parser.add_argument('--archive', type=pathlib.Path, help='Official 4.19.1 Linux amd64 archive')
parser.add_argument('--go', default='go', help='Go 1.26.5 executable')
args = parser.parse_args()
root = pathlib.Path(__file__).resolve().parents[1]
work = root / 'work'
work.mkdir(exist_ok=True)
source = work / 'cloudreve-source'
if source.exists():
    raise SystemExit('Source directory already exists; use a fresh checkout to avoid overwriting changes.')
archive = args.archive or work / 'cloudreve_4.19.1_linux_amd64.tar.gz'
if not archive.exists():
    if args.archive:
        raise SystemExit('Specified archive does not exist')
    urllib.request.urlretrieve('https://github.com/cloudreve/Cloudreve/releases/download/4.19.1/cloudreve_4.19.1_linux_amd64.tar.gz', archive)
if hashlib.sha256(archive.read_bytes()).hexdigest() != '287a1f59adb1249af15cd550b191d2fa71132bfd125fead8578f20152c4b99de':
    raise SystemExit('Official archive SHA-256 mismatch')
subprocess.run(['git', 'clone', '--depth', '1', '--branch', '4.19.1', 'https://github.com/cloudreve/Cloudreve.git', str(source)], check=True)
commit = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
if commit != 'a8becb9f5b226024c83230bc52857c04966e2c30':
    raise SystemExit('Unexpected upstream commit')
subprocess.run(['git', '-C', str(source), 'apply', str(root / 'patches' / 'cloudreve-admin-content.patch')], check=True)
with tarfile.open(archive) as package:
    member = next(m for m in package.getmembers() if pathlib.PurePosixPath(m.name).name == 'cloudreve')
    binary = package.extractfile(member).read()
position = 0
while True:
    position = binary.find(b'PK\x05\x06', position)
    if position < 0:
        raise RuntimeError('Official embedded frontend archive not found')
    try:
        *_, size, offset, comment = struct.unpack_from('<4s4H2LH', binary, position)
        start = position - size - offset
        data = binary[start:position + 22 + comment]
        with zipfile.ZipFile(io.BytesIO(data)) as frontend:
            if 'assets/build/index.html' in frontend.namelist():
                (source / 'application/statics/assets.zip').write_bytes(data)
                break
    except (struct.error, zipfile.BadZipFile, ValueError):
        pass
    position += 4
env = {**os.environ, 'GOOS': 'linux', 'GOARCH': 'amd64', 'CGO_ENABLED': '0'}
subprocess.run([args.go, 'build', '-trimpath', '-p', '2', '-ldflags', '-s -w -X github.com/cloudreve/Cloudreve/v4/application/constants.BackendVersion=4.19.1 -X github.com/cloudreve/Cloudreve/v4/application/constants.LastCommit=a8becb9-admin', '-o', str(work / 'cloudreve-admin'), '.'], cwd=source, env=env, check=True)
print('Built Linux amd64 extension:', work / 'cloudreve-admin')
