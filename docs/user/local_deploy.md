## 本地部署游戏

!!! tip "提示"
    本地部署游戏需要配置环境（并不是很复杂），和一定的技术知识（对于在座的各位应该都不难），如果实在不想折腾，建议使用[在线游戏](online_guide.md)。

---


### 环境准备

#### 克隆源代码
    ```bash
    git clone https://github.com/pirate-608/ZJUers_simulator.git

    cd ZJUers_simulator
    ```

#### 环境与配置
1. 环境变量：创建`.env` 文件，并按照根目录下的环境变量模版（`.env.template`）进行配置，有以下字段：

```bash
ENVIRONMENT=development # 本地部署时请使用开发模式
SECRET_KEY=YOUR_SECRET_KEY_HERE # 随机字符串，用于加密会话
DATABASE_URL=YOUR_DATABASE_URL_HERE # 数据库连接字符串
POSTGRES_PASSWORD=YOUR_POSTGRES_PASSWORD_HERE # 数据库密码
ADMIN_USERNAME=YOUR_ADMIN_USERNAME_HERE # 管理员用户名
ADMIN_PASSWORD=YOUR_ADMIN_PASSWORD_HERE # 管理员密码
ADMIN_SESSION_SECRET=YOUR_ADMIN_SESSION_SECRET_HERE # 管理员会话密钥
LLM_API_KEY=YOUR_LLM_API_KEY_HERE # 大模型API密钥
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1 # 大模型Base URL，以阿里云为例
LLM=YOUR_LLM_HERE # 大模型名称
MINIMAX_API_KEY=YOUR_MINIMAX_API_KEY_HERE # MiniMax API密钥
MINIMAX_MODEL=minimax-m2-her # MiniMax模型名称
MINIMAX_BASE_URL=https://api.minimax.chat/v1/text/chatcompletion_v2 # MiniMax Base URL
```

*注：MiniMax-M2-Her是一款专为角色扮演（RP）优化的模型，如果你不想使用或没有API key，可以将MiniMax相关的字段留空，游戏会回退为默认的LLM*

模型配置请查看[游戏LLM配置](./models.md)

#### 宿主机

!!! tip "提示"
    对于当前版本的游戏（包含数据库、后端、前端），我们强烈建议使用[Docker容器化部署](#docker)，如果你真的想在本地折腾😅，请参考以下步骤（不保证成功）。

---

详细内容请查看[原生部署指南](./local_deploy_bare.md)


#### 使用 Docker 一键启动（推荐）

!!! tip "提示"
    对于Windows和macOS用户，请直接访问[Docker Desktop](https://www.docker.com/products/docker-desktop/)下载并安装Docker Desktop（Windows需要WSL2）。

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
docker-compose up -d --build # 这会在本地构建镜像并拉起所有服务，包括数据库、后端、前端，且会自动执行数据库迁移
```

拉起前端：

```bash
cd zjus-frontend
npm run dev
```

访问[http://localhost:3000](http://localhost:3000)即可开始游戏

*注：如果你想要直接将游戏跑在8000端口，需要给nginx配置证书。*

如果要停止服务，执行：

```bash
docker-compose down
```

如果要停止服务并删除数据，执行：

```bash
docker-compose down -v
```



