# GitHub Release 发布模板

## Release Title（发布标题）

```
ZJUers Simulator v1.0.0 - Docker 一键部署版 🎓🐳
```

---

## Release Body（发布说明正文）

复制以下内容到 GitHub Release 的描述框：

---

## 🎉 折姜大学校园生活模拟器 Docker 版首次发布！

这是一个基于大语言模型的文本校园模拟游戏，支持学业系统、选课系统、成就系统、随机事件等丰富玩法。本版本采用 **Docker 容器化部署**，实现真正的一键启动。

### ✨ 核心特性

- 🎮 **42个专业培养方案**，真实还原浙大课程体系
- 📚 **完整学期循环**，GPA计算，70+成就系统
- 🤖 **AI驱动事件**，基于阿里云百炼大模型生成动态剧情
- 🚀 **一键部署**，跨平台支持 Windows/Linux/macOS
- 🔐 **自动安全配置**，随机密钥生成，交互式API配置
- ⚡ **轻量高效**，2核2G服务器可承载300人在线

### 📦 快速开始

#### Windows 用户
```cmd
# 下载并解压发布包
scripts\deploy.bat
```

#### Linux/Mac 用户
```bash
# 下载并解压发布包
chmod +x scripts/deploy.sh && ./scripts/deploy.sh
```

脚本将自动完成环境检测、配置生成、服务启动，浏览器自动打开游戏！

### 🤖 AI功能配置（可选）

AI功能需要阿里云百炼平台的API密钥（有免费额度）。如不配置，基础游戏功能仍可正常使用。

**快速获取**：
1. 访问 https://bailian.console.aliyun.com
2. 登录/注册并完成实名认证
3. 进入"密钥管理"创建API Key
4. 选择模型（推荐 `qwen-plus`）

详细教程：[scripts/README.md](scripts/README.md)

### 📋 系统要求

**最低配置**：
- CPU: 2核 | 内存: 2GB | 磁盘: 5GB
- 已安装 Docker Desktop 或 Docker Engine

**支持系统**：
- ✅ Windows 10/11 (64-bit)
- ✅ macOS 10.15+
- ✅ Ubuntu 20.04+ / Debian 11+ / CentOS 8+

### 🆕 主要功能

- ✅ Docker一键部署，开箱即用
- ✅ 跨平台部署脚本
- ✅ 智能环境检测与配置向导
- ✅ 自动随机密钥生成
- ✅ 阿里云百炼AI集成
- ✅ PostgreSQL + Redis 数据持久化
- ✅ GitHub Actions CI/CD

### 🔧 管理命令

```bash
docker compose ps          # 查看状态
docker compose logs -f     # 查看日志
docker compose down        # 停止服务
docker compose restart     # 重启服务
```

### 📂 下载说明

**推荐下载**：`zjuers-simulator-docker-v1.0.0.zip` (Windows)

解压后运行 `scripts\deploy.bat` 即可开始游戏！

### 🐛 已知问题

1. 首次构建需5-10分钟（下载镜像和编译）
2. Cloudflare Tunnel 免费版可能不稳定（建议本地部署）
3. AI功能为可选项，不影响基础游戏体验

### 🔐 安全提示

- 🔒 生产环境请使用强随机密码
- 🔒 妥善保管 `.env` 文件，勿提交到版本控制
- 🔒 定期备份 PostgreSQL 数据卷

### 🤝 参与贡献

欢迎参与项目建设！特别需要：
- 补充 `world/keywords.json` 关键词库
- 完善专业培养方案数据
- 优化游戏事件和成就系统

### 📄 开源协议

MIT License

**免责声明**：本项目仅供娱乐和学习交流，不提供任何教学、考试、行政功能支持。

---

**祝你在折姜大学度过愉快的校园生活！** 🎓✨

