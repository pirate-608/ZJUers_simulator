# 纯宿主机本地部署指南 (无 Docker)

> **⚠️ 强烈建议**：当前项目默认基于 Docker 环境部署，这是最稳定且省心的方案。
> 如果你因为开发调试、二次开发或单纯“想折腾”而希望在纯宿主机环境（不依赖 Docker）直接运行前后端，你需要了解并完成以下较为繁琐的环境配置。

## 0. 环境要求总览

- **前端**：Node.js (建议 v18+)
- **后端**：Python (建议 3.10+)
- **数据库**：PostgreSQL 14+ 
- **缓存**：Redis 6+ (Windows 宿主机建议安装在 WSL 中)
- **底层 C 库环境**：GCC / MinGW (用于编译并加载判卷用的 C 动态链接库)

---

## 1. 启动底层依赖：Redis 与 PostgreSQL

如果你使用的是 Windows，最省心的方式是依靠 WSL (Windows Subsystem for Linux) 来运行 Redis 和 PG 数据库。

### 1.1 安装并启动 Redis (推荐 WSL)
使用`wsl --install`安装WSL，然后安装Ubuntu（一般会默认安装），打开你的 WSL (Ubuntu) 终端（`wsl`），执行：
```bash
sudo apt update
sudo apt install redis-server
sudo service redis-server start
```
测试连接：运行 `redis-cli ping`，若返回 `PONG` 则成功。默认端口为 `6379`。

### 1.2 安装并启动 PostgreSQL

---

对于Windows用户，你可以前往[PostgreSQL官网](https://www.postgresql.org/download/windows/)在 Windows 本地安装原生的 PostgreSQL（推荐，有图形化配置界面）

对于Linux 有以下步骤（Windows同样可在wsl中操作）：
```bash
# WSL 安装示例
sudo apt install postgresql postgresql-contrib
sudo service postgresql start
```

进入 PostgreSQL 命令行，创建数据库与专用的用户：
```bash
sudo -u postgres psql
```
在 psql 控制台执行：
```sql
CREATE DATABASE zjus_db;
CREATE USER zjus_user WITH ENCRYPTED PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE zjus_db TO zjus_user;
\q
```

macOS 安装 PostgreSQL
你有三种方式：Homebrew、官方 DMG、Postgres.app。

方法 1：Homebrew（推荐给开发者）
```bash
brew update
brew install postgresql
```
启动服务：

```bash
brew services start postgresql
```
初始化数据库（如果需要）：

```bash
initdb /usr/local/var/postgres
```
连接：

```bash
psql postgres
```
方法 2：Postgres.app（最简单）
1. 下载：https://postgresapp.com/
2. 拖入 Applications
3. 打开 Postgres.app  → 自动启动数据库

方法 3：官方 DMG 安装包
https://www.postgresql.org/download/macosx/

---

## 2. 后端部署 (zjus-backend)

进入后端目录：
```bash
cd zjus-backend
```

### 2.1 虚拟环境与依赖
推荐创建虚拟环境隔离包：
```bash
python -m venv .venv
# 激活环境 (Windows)
.\.venv\Scripts\activate
# 安装依赖
pip install -r requirements.txt
```

### 2.2 环境变量配置
复制 `.env.template` 为 `.env`：
```bash
cp .env.template .env
```
修改 `.env` 中的服务连接地址，将原本指向 Docker 容器名的地址替换为 `localhost`：
```ini
# PostgreSQL (注意：密码和库名替换为你第一步中创建的)
DATABASE_URL=postgresql+asyncpg://zjus_user:your_password@localhost/zjus_db

# Redis
REDIS_URL=redis://localhost:6379/0

# LLM 密钥（如果需要测试对话，必须配置）
LLM_API_KEY=sk-xxxxxx
LLM_BASE_URL=https://api.openai.com/v1
# 游戏防沉迷/管理员等配置...
```
*(注意：请确保 `ENVIRONMENT` 设置为 `development`，这会启用彩色结构化日志和快速热重载。)*

### 2.3 关于底层 C 库的说明 (重要)
本项目入学考试环节调用了 C 语言编写的动态链接库（源码位于 `access` 目录下）。
- 如果你使用的是纯 Windows，必须确保存在编译好的 `.dll` 文件（如 `zju_admission.dll`）。
- 如果没有，你需要使用 MinGW-w64 或者 GCC 将 C 源码编译为动态库。如果运行在 WSL 则需要 `.so` 文件。

### 2.4 启动后端服务
在 `zjus-backend` 根目录下运行（确保你的 `.venv` 已激活）：
```bash
python -m main
# 或者通过 uvicorn 启动
uvicorn app.main:app --reload --host 127.0.0.0 --port 8000
```
如未报错，且能看到彩色日志 `[INFO] Logging initialized`，并看到 heartbeat 注册，说明后端已成功启动，运行在 `http://127.0.0.1:8000`。

---

## 3. 前端部署 (zjus-frontend)

打开一个新终端，进入前端目录：
```bash
cd zjus-frontend
```

### 3.1 安装 Node 依赖
```bash
npm install
```

### 3.2 启动前端本地服务器
```bash
npm run dev
```
按照控制台提示，你可以打开浏览器访问（通常是 `http://localhost:3000` 或者类似端口）。

Vite 本地开发服务器默认已经在 `vite.config.js` 中配置了代理规则，它会将诸如 `/api` 和 `/ws` 的请求转发至本机的 `http://127.0.0.1:8000`（也就是上面启动的后端端口）。

---

## 4. 常见问题排查

1. **连接数据库/Redis被拒绝 (`Connection refused`)**：
   - 检查该服务是否已启动。如果跑在 WSL 中，WSL 的 localhost 和 Windows 本机的 localhost 端口映射默认互通，但如果有代理软件或者防火墙，可能会拦截。
2. **PostgreSQL 身份验证失败 (`password authentication failed`)**：
   - 检查 `.env` 中的用户名、密码，或者尝试将 pg_hba.conf 中本地访问模式改为 `trust` 或 `md5`。
3. **C 库调用报错 (`OSError: [WinError 126] The specified module could not be found`)**：
   - 这是因为 python 的 ctypes 找不到 dll，检查 dll 文件是否存在于后端正确的目录下，并且你的 Python 和 DLL 都是同一架构（比如都是 64位）。
4. **LLM 不能正常对话**：
   - 绝大多数是 API Key 或者网络问题。也可直接在前端登录界面的高级选项里指定自定义模型做临时调试。