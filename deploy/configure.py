"""Configure the private instance through an SSH tunnel on localhost:15212."""
import argparse
import base64
import os
import json
import pathlib
import secrets
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument('--site-url', required=True, help='Public HTTPS URL')
parser.add_argument('--admin-email', required=True)
parser.add_argument('--name', default='我的网盘')
parser.add_argument('--open-registration', action='store_true', help='Enable public registration with CAPTCHA')
args = parser.parse_args()
if not args.site_url.startswith('https://'):
    raise SystemExit('--site-url must use HTTPS')
ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:15212/api/v4'
credentials = pathlib.Path(os.environ.get('CLOUDREVE_CREDENTIALS', str(ROOT / '.secrets' / 'admin.json')))
credentials.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
if not credentials.exists():
    credentials.write_text(json.dumps({'email': args.admin_email, 'password': secrets.token_urlsafe(24)}, ensure_ascii=False, indent=2), encoding='utf-8')
credentials.chmod(0o600)
account = json.loads(credentials.read_text(encoding='utf-8'))
token = ''

def api(method, endpoint, data=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(BASE + endpoint, data=None if data is None else json.dumps(data).encode(), headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as response:
        result = json.load(response)
    if result.get('code') != 0:
        raise RuntimeError(f'{method} {endpoint}: code={result.get("code")} msg={result.get("msg")}')
    return result.get('data')

try:
    api('POST', '/user', {**account, 'language': 'zh-CN'})
except RuntimeError as e:
    if '40034' not in str(e):
        # Login below also supports rerunning after a partial configuration.
        print('Registration already initialized; checking login.')
login = api('POST', '/session/token', account)
token = login['token']['access_token']
assert login['user']['group']['name'] == 'Admin', 'Initial account is not the administrator'
settings = {
    'siteName': args.name, 'siteTitle': args.name, 'siteDes': '',
    'siteURL': args.site_url,
    'register_enabled': '1' if args.open_registration else '0', 'default_group': '2', 'reg_captcha': '1', 'forget_captcha': '1', 'email_active': '0',
    'site_logo': '/branding/logo.svg', 'site_logo_light': '/branding/logo.svg',
    'pwa_small_icon': '/branding/icon.svg', 'defaultTheme': '#2563eb',
    'temp_path': '/var/lib/cloudreve/temp',
    'queue_thumb_worker_num': '2', 'queue_media_meta_worker_num': '1',
    'queue_io_intense_worker_num': '1', 'max_parallel_transfer': '2',
    'tos_url': '', 'privacy_policy_url': '',
}
api('PATCH', '/admin/settings', {'settings': settings})
for group_id, name in [(1, 'Admin'), (2, '普通用户')]:
    group = api('GET', f'/admin/group/{group_id}')
    group['max_storage'] = 10 * 1024**3
    group['name'] = name
    permissions = bytearray(base64.b64decode(group['permissions']))
    if group_id == 1:
        permissions[0] |= 1
    else:
        permissions[0] &= ~1
    group['permissions'] = base64.b64encode(permissions).decode()
    if group_id == 2:
        group['settings']['trash_retention'] = 24 * 3600
    api('PUT', f'/admin/group/{group_id}', {'group': group})
anonymous = api('GET', '/admin/group/3')
permissions = bytearray(base64.b64decode(anonymous['permissions']))
permissions[0] &= ~(1 | 128)
anonymous['permissions'] = base64.b64encode(permissions).decode()
api('PUT', '/admin/group/3', {'group': anonymous})
policy = api('GET', '/admin/policy/1')
policy['name'] = '共用 10 GB 存储池'
policy['max_size'] = 10 * 1024**3
api('PUT', '/admin/policy/1', {'policy': policy})
print('Administrator and storage configured. Credentials saved privately at:', credentials)
print('Public registration enabled with CAPTCHA.' if args.open_registration else 'Public registration disabled.')
