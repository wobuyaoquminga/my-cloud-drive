# 第三方说明

本项目基于 Cloudreve Community 部署，Cloudreve 本体及其前端由 Cloudreve 项目维护，遵循 GPL-3.0 及上游列出的第三方许可。

- Cloudreve：https://github.com/cloudreve/cloudreve
- Cloudreve 前端：https://github.com/cloudreve/frontend
- Cloudreve 文档：https://docs.cloudreve.org/zh/

本仓库不包含完整 Cloudreve 源码或其二进制文件；补丁包含必要的源码差异，安装器从官方发布页下载并验证发布包。截图中包含上游产品界面与标识，仅用于展示本项目实际部署效果。

本仓库另提供 `patches/cloudreve-admin-content.patch`，用于定制 Cloudreve 4.19.1 管理员全空间文件管理与内容编辑。该补丁基于上游提交 `a8becb9f5b226024c83230bc52857c04966e2c30`，按 GPL-3.0 提供，许可证文本见 `patches/LICENSE-GPL-3.0`。`deploy/build-admin.py` 是独立的本地构建脚本，不改变 `deploy/install.py` 安装官方发布二进制的行为。

原创部署脚本、说明和蓝色云朵品牌 SVG 按本仓库 MIT 许可证提供。MIT 许可证不改变 Cloudreve 本体的授权条款。
