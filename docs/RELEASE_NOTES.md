# Release Notes

## Release Title

**ZJUers Simulator v1.0.0 - Docker 一键部署版** 🎓🐳

---

## Release Body

### 🎉 发布说明

折姜大学校园生活模拟器 Docker 版正式发布！这是一个基于大语言模型的文本校园模拟游戏，支持学业系统、选课系统、成就系统、随机事件等丰富玩法。本次发布采用 **Docker 容器化部署**，实现真正的一键启动，无需复杂配置。

### ✨ 核心特性

#### 🎮 游戏功能
- **多专业体系**：支持42个专业培养方案，真实还原浙江大学课程体系
- **学期循环系统**：完整的学年/学期/周循环，GPA 计算，成绩管理
- **成就系统**：70+ 个成就等待解锁，涵盖学业、社交、活动等多个维度
- **AI 驱动事件**：基于阿里云百炼大模型，生成动态校园事件和剧情
- **可扩展数据**：JSON 格式配置，方便添加/修改课程和事件

#### 🚀 部署特性
- **Docker 一键部署**：真正的开箱即用，3 分钟完成部署
- **跨平台支持**：Windows/Linux/macOS 统一部署体验
- **智能环境检测**：自动检测 Docker、Python 环境，提供最佳部署方案
- **交互式配置**：友好的 API 配置向导，支持跳过 AI 功能
- **安全随机密钥**：自动生成数据库密码和应用密钥，保障安全

#### 🏗️ 技术架构
- **后端**：FastAPI + PostgreSQL + Redis
- **前端**：原生 HTML/CSS/JavaScript + WebSocket 实时通信
- **容器化**：Docker Compose 多服务编排
- **CI/CD**：GitHub Actions 自动构建镜像和发布包

---

### 📦 快速开始

#### **方式一：一键部署（推荐）** ⭐

**Windows 用户**：
```cmd
scripts\deploy.bat
```

**Linux/Mac 用户**：
```bash
chmod +x scripts/deploy.sh && ./scripts/deploy.sh
```

脚本将自动：
1. ✅ 检测 Docker 和 Python 环境
2. ✅ 引导配置阿里云 API（可选）
3. ✅ 生成安全随机密钥
4. ✅ 构建并启动所有服务
5. ✅ 自动打开浏览器访问游戏

#### **方式二：手动部署**

1. **安装 Docker Desktop**
   - Windows/Mac: https://www.docker.com/products/docker-desktop/
   - Linux: `curl -fsSL https://get.docker.com | sh`

2. **配置环境变量**（可选）
   ```bash
   cp .env.example .env
   # 编辑 .env 填入 API 密钥（参考 scripts/README.md）
   ```

3. **启动服务**
   ```bash
   docker compose up -d --build
   ```

4. **访问游戏**
   - 打开浏览器访问：http://localhost:8000

---

### 🤖 AI 功能配置（可选）

AI 功能需要阿里云百炼平台的 API 密钥。如果不配置，基础游戏功能仍可正常使用。

**获取步骤**：
1. 访问 [阿里云百炼](https://bailian.console.aliyun.com)
2. 登录/注册并完成实名认证
3. 开通服务后，进入"密钥管理"创建 API Key
4. 在"模型服务"中选择模型（推荐 `qwen-plus`）

详细说明请查看：[scripts/README.md](../scripts/README.md)

---

### 📋 系统要求

#### **最低配置**
- CPU: 2 核
- 内存: 2GB
- 磁盘: 5GB 可用空间
- Docker Desktop 或 Docker Engine

#### **推荐配置**
- CPU: 4 核
- 内存: 4GB
- 磁盘: 10GB 可用空间
- 稳定的网络连接（用于 AI 功能）

#### **支持的操作系统**
- ✅ Windows 10/11 (64-bit)
- ✅ macOS 10.15+
- ✅ Ubuntu 20.04+
- ✅ Debian 11+
- ✅ CentOS 8+
- ✅ 其他支持 Docker 的 Linux 发行版

---

### 🔧 管理命令

```bash
# 查看服务状态
docker compose ps

# 查看实时日志
docker compose logs -f

# 停止服务
docker compose down

# 重启服务
docker compose restart

# 清理数据（谨慎使用）
docker compose down -v
```

---

### 📂 发布包内容

```
ZJUers_Simulator_Docker_v1.0.0/
├── 📁 app/                    # 后端应用代码
├── 📁 static/                 # 前端静态资源
├── 📁 templates/              # HTML 模板
├── 📁 world/                  # 游戏数据配置
│   ├── courses/              # 42个专业培养方案
│   ├── keywords.json         # AI生成关键词库
│   ├── achievements.json     # 成就定义
│   └── game_balance.json     # 游戏平衡配置
├── 📁 scripts/                # 部署脚本
│   ├── deploy.py             # Python智能部署
│   ├── deploy.bat            # Windows一键启动
│   ├── deploy.sh             # Linux/Mac一键启动
│   ├── stop.bat/sh           # 服务停止脚本
│   └── README.md             # API配置指南
├── 📄 docker-compose.yml      # Docker编排配置
├── 📄 Dockerfile              # 容器构建配置
├── 📄 .env.example            # 环境变量示例
├── 📄 README.md               # 项目说明
└── 📄 LICENSE                 # 开源协议
```

---

### 🆕 本版本更新内容

#### **新增功能**
- ✅ Docker 一键部署方案
- ✅ 跨平台部署脚本（Windows/Linux/Mac）
- ✅ 交互式 API 配置向导
- ✅ 自动随机密钥生成
- ✅ 环境检测与智能回退
- ✅ 安全警告机制（备用部署方案）
- ✅ GitHub Actions CI/CD 自动化

#### **优化改进**
- 🔄 移除 nginx 依赖，简化部署架构
- 🔄 统一使用阿里云百炼作为默认 LLM 服务
- 🔄 优化数据库健康检查，避免启动竞态
- 🔄 改进日志输出，增强调试体验
- 🔄 完善 .env.example 示例配置

#### **文档更新**
- 📝 新增 scripts/README.md（API配置指南）
- 📝 更新 .env.example（Docker版本配置）
- 📝 完善 README.md（部署流程说明）
- 📝 新增发布计划文档（DOCKER_RELEASE_PLAN.md）

---

### 🐛 已知问题

1. **Cloudflare Tunnel 不稳定**
   - 现象：使用免费版 Cloudflare Tunnel 可能出现 WebSocket 连接中断
   - 影响：公网访问体验受影响
   - 建议：本地部署或使用其他公网方案（如 fly.io）

2. **首次构建较慢**
   - 现象：首次运行 `docker compose build` 需要 5-10 分钟
   - 原因：需要下载基础镜像和编译 C 扩展模块
   - 解决：后续启动将使用缓存，速度显著提升

3. **AI 功能可选**
   - 说明：如不配置 API 密钥，AI 相关事件将不会生成
   - 影响：不影响基础游戏功能（选课、GPA、成就等）
   - 推荐：配置阿里云百炼免费额度即可体验完整功能

---

### 🔐 安全说明

#### **生产环境部署建议**
1. **修改默认密钥**：必须使用强随机密码替换示例配置
2. **限制端口访问**：仅向可信网络开放 8000 端口
3. **定期备份**：重要数据请定期备份 PostgreSQL 数据卷
4. **API 密钥保护**：妥善保管 .env 文件，避免提交到版本控制

#### **本地测试环境**
- 使用脚本自动生成的随机密钥即可
- 无需额外配置，开箱即用

---

### 🤝 贡献指南

欢迎参与项目建设！

**如何贡献**：
- 🐛 报告 Bug：[提交 Issue](../../issues)
- 💡 功能建议：[提交 Feature Request](../../issues)
- 📚 补充数据：编辑 `world/keywords.json` 和课程数据
- 🔀 代码贡献：Fork 项目并提交 Pull Request

**特别需要**：
- 补充 `world/keywords.json` 关键词库（AI 生成依据）
- 添加/完善专业培养方案数据
- 优化游戏事件和成就系统
- 改进前端交互体验

---

### 📞 支持与反馈

- **项目主页**：https://github.com/YOUR_USERNAME/ZJUers_simulator
- **问题反馈**：[GitHub Issues](../../issues)
- **功能讨论**：[GitHub Discussions](../../discussions)

---

### 📄 开源协议

本项目采用 MIT License 开源协议。

**免责声明**：
- 本项目仅供娱乐和学习交流使用
- 不提供任何教学、考试、行政、管理方面的功能
- 所有学校相关信息版权归浙江大学所有

---

### 🙏 致谢

- 感谢 [浙江大学](https://www.zju.edu.cn) 提供灵感来源
- 感谢阿里云百炼平台提供大模型服务
- 感谢所有贡献者和测试用户

---

**享受你的折姜大学校园生活！** 🎓✨

