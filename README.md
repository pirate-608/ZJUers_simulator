# ZJUers_simulator
## **声明**
该项目仅供娱乐，不提供任何教学、考试、行政、管理方面的其他功能，一切有关学校具体信息的内容，由[@浙江大学](https://www.zju.edu.cn) 保留一切权利。

## 游戏网址：[game.67656.fun](game.67656.fun)

	————我在这里放了67656颗星星，希望每个折大人都能找到属于自己的一颗。

![logo](./static/images/logo.png)
## 开始界面
![start](./static/images/start.png)
## 入学考试
![exam](./static/images/exam.png)
## 录取通知书
![admission](./static/images/admission.png)
## 游戏控制台
![dashboard](./static/images/dashboard.png)
![dashboard2](./static/images/dashboard2.png)
## 随机事件
![event](./static/images/event.png)
## 钉钉消息
![dingtalk](./static/images/dingtalk.png)

## 邀请：关键词添加和补充
该游戏是一个基于大模型的文本游戏，world/keywords.json是大模型生成内容的一个重要根据，目前数据较为不全，欢迎有兴趣的uu们在其中补充关键信息（请参照原有json表结构）

## 架构简述
*	服务端：FastAPI/uvicorn。
*	前端 HTML（jinja2）/JS。
*	状态机和缓存：Redis
*	数据持久化与ORM：postgreSQL/sqlalchemy
*	数据验证与管理：pydantic
*	大模型集成：OpenAI 官方 SDK

## 主要功能
- 多专业/学院分流，课程加载来源于world/courses目录下json格式的简化培养方案（数据来源于[本科教学管理信息服务平台](https://zdbk.zju.edu.cn/)）
- 学期循环、GPA计算、成就系统，游戏进行时状态全部依赖Redis缓存，为典型IO密集型项目（数据库读写仅用于登录验证，后续可扩展），2核2G服务器可以轻松承载300人活跃在线
- 数据结构高度可扩展，支持自定义培养方案(可更改world/courses目录下的表结构和字段)

# 本地部署

本项目推荐使用 Docker 部署，支持 Windows、Linux、macOS。

## Linux/macOS

### 1. 安装 Docker

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo \
	"deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
	$(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
	sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
# 重新登录终端以生效
```

#### macOS (推荐 Homebrew)
```bash
brew install --cask docker
open /Applications/Docker.app
# 等待 Docker 图标常驻菜单栏后即可用
```

### 2. 配置大模型 API Key（如 OpenAI/通义千问等）

可在 .env 文件或命令行导出环境变量，示例：

```bash
export OPENAI_API_KEY=sk-xxxxxx
export QWEN_API_KEY=xxxxxx
# 如需持久化可写入 ~/.bashrc 或 ~/.zshrc
```

或在 docker-compose.yml 中添加 environment 字段：
```yaml
	environment:
		- OPENAI_API_KEY=sk-xxxxxx
		- QWEN_API_KEY=xxxxxx
```

### 3. 拉取代码并启动

```bash
git clone https://github.com/yourname/ZJUers_simulator.git
cd ZJUers_simulator
docker compose up -d --build
```

### 4. 访问服务

浏览器打开 http://localhost:8000

如需关闭服务：
```bash
docker compose down
```

## Windows

1. 安装 [Docker](https://www.docker.com/get-started)
2. 在项目根目录执行：
	```bash
	docker-compose up -d --build
	```
3. 访问 http://localhost:8000 体验（如有 nginx，前端静态资源为 80 端口）

如需关闭服务：
```bash
docker-compose down
```

### 手动部署（开发/调试）

1. 安装 Python 3.11+，并创建虚拟环境
2. 安装依赖：
	```bash
	pip install -r requirements.txt
	```
3. 启动后端：
	```bash
	uvicorn app.main:app --host 0.0.0.0 --port 8000
	```
4. 启动前端：
	- 推荐用 nginx 反向代理 static/ 目录
	- 或用 Python 简单 HTTP 服务：
	  ```bash
	  cd static && python -m http.server 8080
	  ```
5. （可选）使用 Cloudflare Tunnel 实现公网访问，详见 tunnel/ 目录说明

## 目录结构
- app/        后端核心代码
- static/     前端静态资源
- templates/  前端页面模板
- world/      课程池、专业映射等数据
- tunnel/     Cloudflare Tunnel 配置(可选)
- nginx/      反向代理与证书

## 许可证
本项目采用 MIT License 开源。

## 贡献
欢迎进行关键词补充！
欢迎 PR、Issue 及建议！

## 作者
pirate-608
