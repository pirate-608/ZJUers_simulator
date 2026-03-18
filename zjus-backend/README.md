<div align="center">
  <img src="https://zjusim-docs.67656.fun/assets/images/logo.svg" alt="Game Logo" width="120" />
  <h1>ZJUers Simulator Backend</h1>
  <p><strong>我在这里放了67656颗星星，希望每个折大人都能找到属于自己的一颗</strong></p>
</div>

你正在阅读的是ZJUers模拟器的后端代码，基于 Python/FastAPI 构建。
后端代码经历了多次重构，目前已经比较完善。

## 快速开始

详细内容，请查看[后端文档](https://zjusim-docs.67656.fun/dev/framework/backend_framework)。

### 本地开发
```bash
# 这里默认已经激活了虚拟环境，且在zjus-backend目录下
# .\.venv\Scripts\activate
# cd zjus-backend

# 安装依赖
pip install -r requirements.txt

# 启动开发服务器
uvicorn main:app --reload
```

### 使用docker

注意，在本地启动时，建议在根目录创建docker-compose.override.yml以覆写生成配置为开发配置。

示例：
```yaml
version: '3.8'

# 这是专门用于本地开发的覆盖文件。
# 当你在本地运行 `docker-compose up -d` 时，Docker 会自动将此文件与基础的 docker-compose.yml 进行合并。
# 这里的 `build` 指令会覆盖掉原文件中的 `image` 指令，从而实现本地从源码构建镜像，而不是拉取线上镜像。

services:
  backend:
    build:
      context: ./zjus-backend
      dockerfile: Dockerfile
    # 本地开发时挂载代码以实现热更新
    volumes:
      - ./zjus-backend/app:/app/app
      - ./zjus-backend/world:/app/world

  migrate:
    build:
      context: ./zjus-backend
      dockerfile: Dockerfile

  nginx:
    # 覆盖掉线上的只读前端镜像，重新在本地构建
    build:
      context: ./zjus-frontend
      dockerfile: Dockerfile
    # 或者如果你不想在 docker 里 build 前端，你可以把这里改回：
    # image: nginx:latest
    # volumes:
    #   - ./zjus-frontend/dist:/usr/share/nginx/game-frontend
```

#### 启动

```bash
# 回到项目根目录
cd..

# 构建并启动
docker-compose up -d --build

# 停止
docker-compose down
```

### 调试

通过FastAPI自带的Swagger UI可以轻松地进行调试，访问地址：http://localhost:8000/docs

FastAPI会在这里生成一个交互式的API文档，你可以在这里进行调试。

### 测试

```bash
# 确保在zjus-backend目录下
# .\.venv\Scripts\activate
# cd zjus-backend

# 运行测试
python -m pytest tests/ -v # 运行测试
```

#### 运行结果示例

```
======================== 61 passed, 1 warning in 0.38s ========================
```

这代表61个测试用例全部通过，1个测试用例有警告。这种情况是可接受的。如果想看具体是哪个测试用例有警告，可以使用 `python -m pytest tests/ -v` 命令。