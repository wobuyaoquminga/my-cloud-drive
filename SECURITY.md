# 安全与凭据

本仓库不发布管理员密码、数据库密码、SSH 密钥、浏览器登录资料、用户文件或数据库备份。

管理员凭据由初始化脚本随机生成，保存在 `.secrets/admin.json`；数据库密码在服务器 `/etc/cloudreve/conf.ini`。这些内容均不应上传到 GitHub。截图来自空的验证环境。

网盘仅监听回环地址，由 Nginx 提供 HTTPS；公开注册启用图片验证码和入口限流。这里的检查不是独立安全审计，也没有并发容量测试。

发现漏洞时，请通过仓库维护者的 GitHub 联系方式私下联系，避免在公开 Issue 中附密码、可用攻击链接或用户文件。Cloudreve 本体漏洞请优先向 [Cloudreve 上游](https://github.com/cloudreve/cloudreve/security) 报告。
