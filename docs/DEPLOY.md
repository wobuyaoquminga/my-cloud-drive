# 部署说明

## 前提

- Ubuntu 24.04 x86_64、Python 3、systemd、MySQL 8、Nginx。
- root/sudo 权限；root 可通过本机 `mysql` 命令管理数据库。
- 建议至少 2 GB 内存、12 GiB 空闲磁盘；10 GiB 存储池之外需为系统、数据库和已有应用保留空间。
- 可用的域名或公网 IP、匹配该地址且受信任的 TLS 证书。
- 服务器能够访问 GitHub 官方发布资源，或提前下载发布包。

若服务器已有网站，先检查 Nginx 443 端口与现有路由。独立站点模板不能直接替换已有网站配置。

## 1. 安装程序与存储区

将仓库下载到服务器。安装器不会安装 MySQL/Nginx，也不会申请证书。

```sh
sudo python3 deploy/install.py
```

若 GitHub 下载不稳定，可从 [Cloudreve 4.19.1 官方发布页](https://github.com/cloudreve/cloudreve/releases/tag/4.19.1) 下载 `cloudreve_4.19.1_linux_amd64.tar.gz` 并上传到服务器：

```sh
sudo python3 deploy/install.py --archive /path/to/cloudreve_4.19.1_linux_amd64.tar.gz
```

安装器校验 SHA-256，创建 `cloudreve` 系统用户、数据库及独立数据库账号，随机生成数据库密码并保存在 `/etc/cloudreve/conf.ini`。网盘监听 `127.0.0.1:5212`。

文件存储区为 `/var/lib/cloudreve-storage.img`，挂载在 `/var/lib/cloudreve`；程序数据目录 `/opt/cloudreve/data` 指向该存储区。服务内存上限 512 MiB，CPU 上限一核。

安装器不提供自动失败回滚。失败后先检查已创建的用户、挂载和数据库，保留日志，不要反复执行或手动格式化现有存储。

## 2. 初始化管理员

在运行初始化脚本的电脑上建立 SSH 隧道，并保持连接：

```sh
ssh -N -L 127.0.0.1:15212:127.0.0.1:5212 your-user@your-server
```

另开终端，在仓库根目录执行，将示例 URL 和管理员邮箱换成自己的值：

```sh
python deploy/configure.py --site-url https://pan.example.com --admin-email admin@example.com --name 我的网盘 --open-registration
```

脚本生成随机管理员密码，保存到本机 `.secrets/admin.json`，不在终端输出密码。默认禁止公开注册；指定 `--open-registration` 才会开启注册，并同时启用图片验证码。

首个注册账号必须是自己的管理员账号。初始化脚本会调整站点设置与用户组，不是只读检查工具，不能作为定时任务反复运行。改名时还需修改 `deploy/logo.svg` 内的文字。

## 3. 配置 HTTPS

编辑 `deploy/cloudreve-nginx.conf`，把 `example.com`、证书和私钥路径替换为自己的实际值。确认 443 端口上的既有应用不会被覆盖，再在服务器执行：

```sh
sudo python3 deploy/enable-web.py
```

它复制品牌文件、安装代理配置，在 `nginx -t` 成功后 reload Nginx。它不会设置云安全组、申请证书或自动创建 DNS 记录。

`deploy/use-shared-https.py` 是本项目与 Chat 服务共用 443 的可选工具，只适用于 `/etc/nginx/sites-available/chat-ip.conf` 中存在预期的 Chat 回环代理时；它将首页交给网盘，保留 Chat 的 `/api/` 与 `/ws`，网盘使用 `/api/v4/`。它依赖 `enable-web.py` 已安装的品牌和代理文件，且会保存修改前配置。其他网站请人工合并路由，不要直接执行该工具。

## 4. 验证与管理

```sh
sudo systemctl status cloudreve --no-pager
sudo journalctl -u cloudreve -n 60 --no-pager
df -h /var/lib/cloudreve /
```

在浏览器检查注册验证码、管理员登录和上传下载。管理员通过 `/admin` 进入后台；登录后修改初始密码。

使用 Node.js 20 或以上版本可运行公网检查：

```sh
# Linux/macOS
CLOUDREVE_URL=https://pan.example.com node deploy/public-check.mjs
```

```powershell
# Windows PowerShell
$env:CLOUDREVE_URL = 'https://pan.example.com'
node deploy/public-check.mjs
```

检查工具使用 `.secrets/admin.json`，创建并永久删除自己的 1 MiB 验证文件，不更改注册配置。若管理员密码已修改，请同步更新该本机私密文件。它不会忽略 HTTPS 证书错误。

## 5. 备份与维护

`deploy/backup.py` 会短暂停止网盘、导出数据库并备份文件及配置，然后重新启动网盘。备份保存在 `/var/backups/cloudreve/`，包含敏感配置，应妥善保管。

备份工具会收集存在的独立站点或 Chat 共用 Nginx 配置。数据超过 1 GiB 时脚本拒绝再在服务器上复制文件，避免挤占共享系统盘。

生产数据应备份到另一台设备或对象存储；本项目没有自动异地备份或已验证的恢复流程。文件池限制不包含 MySQL 和系统日志，应同时监测系统盘。

升级请按 [Cloudreve 官方文档](https://docs.cloudreve.org/zh/maintenance/update) 执行并先备份。证书续期由部署者维护；不要用旧部署脚本覆盖已经合并好的共用路由。
