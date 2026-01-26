# ZJUers_simulator

浙江大学校园生活模拟器

## 项目简介
本项目为浙江大学校园生活模拟器，支持学业、选课、成就、事件、学期循环等玩法，后端基于 FastAPI，前端基于 HTML/JS，支持 Docker 部署和 Cloudflare Tunnel 公网分流。

## 主要功能
- 多专业/学院分流，课程池自动筛选
- 学期循环、GPA计算、成就系统
- 支持 Cloudflare Tunnel 公网访问
- 支持 HTTPS 反向代理（nginx）
- 数据结构高度可扩展，支持自定义培养方案

## 快速启动
1. 安装 Python 3.11+，并创建虚拟环境
2. 安装依赖：`pip install -r requirements.txt`
3. 启动后端：`uvicorn app.main:app --host 0.0.0.0 --port 8000`
4. 启动前端（nginx 或本地静态服务）
5. 可选：使用 Docker 或 Cloudflare Tunnel 部署

## 目录结构
- app/        后端核心代码
- static/     前端静态资源
- templates/  前端页面模板
- world/      课程池、专业映射等数据
- tunnel/     Cloudflare Tunnel 配置
- nginx/      反向代理与证书

## 许可证
本项目采用 MIT License 开源。

## 贡献
欢迎 PR、Issue 及建议！

## 作者
pirate-608
