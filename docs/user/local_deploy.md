## 本地部署游戏

::: tip 提示
本地部署游戏需要配置环境（并不是很复杂），和一定的技术知识（对于在座的各位应该都不难），如果实在不想折腾，建议使用[在线游戏](online_guide.md)。

:::
---


### 环境准备

#### 克隆源代码
    ```bash
    git clone https://github.com/pirate-608/ZJUers_simulator.git

    cd ZJUers_simulator
    ```

#### 环境与配置

1. 复制环境变量模板并编辑：

```bash
cp .env.template .env
```

按需修改 `.env` 中的配置，必须填写的字段：

```bash
SECRET_KEY=你的随机字符串
DATABASE_URL=postgresql+asyncpg://zju:你的数据库密码@db:5432/zjus
POSTGRES_PASSWORD=你的数据库密码
ADMIN_USERNAME=你的管理员用户名
ADMIN_PASSWORD=你的管理员密码
ADMIN_SESSION_SECRET=你的管理员会话密钥
INVITE_CODES=本地测试邀请码1,本地测试邀请码2
LLM_API_KEY=你的大模型API密钥（可选）
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM=你的模型名称
MINIMAX_API_KEY=你的MiniMax API密钥（可选，留空则回退到默认LLM）
MINIMAX_MODEL=M2-her
MINIMAX_BASE_URL=https://api.minimaxi.com/v1
```

`INVITE_CODES` 为逗号分隔的邀请码列表。在线/本地登录都需要填写其中一个邀请码；新玩家登录后会进入角色创建页，老玩家登录还需要提供学生凭证。

2. 复制 Docker Compose 本地覆写模板：

```bash
cp docker-compose.override.example docker-compose.override.yml
```

该文件将 Docker 镜像拉取替换为本地源码构建，是本地开发必需的。
它还会把后端端口映射到 `127.0.0.1:8000`，方便本地前端代理、OpenAPI 生成和调试；生产基础配置不会向宿主机公开后端端口。

#### 宿主机

::: tip 提示
对于当前版本的游戏（包含数据库、后端、前端），我们强烈建议使用Docker 容器化部署，如果你真的想在本地折腾😅，请参考以下步骤（不保证成功）。

:::
---

详细内容请查看[原生部署指南](./local_deploy_bare.md)


#### 使用 Docker 一键启动（推荐）

::: tip 提示
对于Windows和macOS用户，请直接访问[Docker Desktop](https://www.docker.com/products/docker-desktop/)下载并安装Docker Desktop（Windows需要WSL2）。

:::
---

对于Linux用户（以Ubuntu / Debian为例），请参考以下步骤安装docker和docker-compose：

```bash
# 1. 安装依赖
sudo apt update
sudo apt install -y apt-transport-https ca-certificates curl gnupg lsb-release

# 2. 添加 Docker GPG 密钥
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# 3. 添加 Docker 稳定源
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 4. 安装 Docker Engine
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io

# 5. 启动并设置开机自启
sudo systemctl start docker
sudo systemctl enable docker

# 6. 验证安装
docker --version
sudo docker run hello-world
```

在项目根目录执行：

```bash
docker compose up -d --build
```

这会构建所有服务的本地镜像并拉起容器：数据库（PostgreSQL + pgvector）、缓存（Redis）、后端（FastAPI，开发覆写下仅绑定宿主机 `127.0.0.1:8000`）、前端（Nginx :80），并自动执行数据库迁移和向量数据导入。

访问 [http://localhost](http://localhost) 即可开始游戏。

*注：`docker compose`（无连字符）是 Docker Compose V2 的命令格式。如果你还在使用旧版 `docker-compose`，替换即可。*

### 管理数值、属性和道具

本地 Docker Compose 会挂载 `zjus-backend/world/`，因此你可以用两种方式调整游戏设定：

- 进入 `http://localhost:8000/admin`，使用 `.env` 中的管理员账号登录，在“数值平衡”页面调整 `game_balance.json` 中的学期时长、概率、冷却、休闲和考试参数。保存后后端会热重载，并写入审计记录。
- 在同一个后台的“道具配置”页面调整 `items.json` 中的初始金币、期末金币公式、道具价格、标签和被动加成，也可以新增或删除道具。保存后会热重载，并写入审计记录。
- 直接编辑 `zjus-backend/world/` 下的 JSON 文件，例如 `items.json` 或 `stat_definitions.json`。编辑属性或手工改道具后建议运行世界数据校验，避免 JSON 格式或 effect 字段写错。

常用校验：

```bash
cd zjus-backend
python scripts/validate_world_data.py
```

新增道具通常只需要使用后台“道具配置”页面或编辑 `world/items.json`；新增属性还要同步生成前端属性元数据。完整流程见[游戏设定维护](/dev/world-data)。

如果要停止服务，执行：

```bash
docker compose down
```

如果要停止服务并删除数据，执行：

```bash
docker compose down -v
```
