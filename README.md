<div align="center">
  <img src="https://zjusim-docs.67656.fun/assets/images/logo.svg" alt="Game Logo" width="120" />
  <h1>ZJUers Simulator</h1>
  <p><strong>我在这里放了67656颗星星，希望每个折大人都能找到属于自己的一颗</strong></p>
</div>

[![简体中文](https://img.shields.io/badge/🇨🇳_简体中文-当前-blue)](README.md)
[![English](https://img.shields.io/badge/🇺🇸_English-Available-green)](README.en.md)

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688?logo=fastapi)
![Vue.js](https://img.shields.io/badge/Vue.js-3.x-4FC08D?logo=vuedotjs)
![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?logo=typescript)
![Redis](https://img.shields.io/badge/Redis-7.x-DC382D?logo=redis&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+pgvector-4169E1?logo=postgresql)
![Nginx](https://img.shields.io/badge/Nginx-1.24+-009639?logo=nginx&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI_python_SDK-1.12+-412991)
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)
![Docker Compose](https://img.shields.io/badge/Docker_Compose-2496ED?logo=docker&logoColor=white)

## **声明**
该项目仅供娱乐，不提供任何教学、考试、行政、管理方面的其他功能，一切有关学校具体信息的内容，由[@浙江大学](https://www.zju.edu.cn) 保留一切权利。

## 游戏网址：[67656.fun](https://67656.fun)

## 文档：查看[项目文档](https://zjusim-docs.67656.fun)

## 这是什么？

这是「折姜大学模拟器」，一个致力于打造浙江大学平行空间的游戏。我们使用大模型为游戏提供内容支持，并维护一份完整的世界观文件集作为游戏的底层设定。

## 共建世界观
如果你认为这款游戏还不错，但仍然缺少了什么，那是因为我们维护的世界观文件集还处于初级阶段。
我们的世界观文件集结构如下：

```
zjus-backend/world/
├── courses/
│   └── ... (共 40 个课程 JSON 文件，如 CS.json, AI.json 等)
├── achievements.json  # 成就系统
├── characters.json    # 角色系统
├── game_balance.json  # 游戏平衡
├── keywords.json      # 关键词
├── majors.json        # 专业系统
├── notice.md          # 公告
└── rules.html         # 游戏规则
```

其中`courses`文件夹下的文件是课程系统（数据来源：[本科教学管理信息服务平台](https://zdbk.zju.edu.cn)），其与`achievements.json`、`characters.json`、`majors.json`、`game_balance.json`、`keywords.json`等文件都直接被后端加载。

世界观文件集和llm共同构成了这个游戏的灵魂，llm需要付费来用API，但world/文件夹下的内容是无价的，它的成长依赖于每一个致力于构建 ZJUers 模拟器世界观的校友。

我们需要你们！请不要吝啬你的关键词灵感，你的建议，你的PR，你的Issue，你的任何帮助都是我们前进的动力。

## 游戏界面预览

<details>
<summary>🏁 开始界面</summary>

![开始界面](https://zjusim-docs.67656.fun/assets/images/start.png)

</details>

<details>
<summary>🧑‍🎓 角色创建</summary>

![角色创建](https://zjusim-docs.67656.fun/assets/images/create.png)
新玩家通过邀请码登录后选择专业，并分配 IQ / EQ / Luck 初始属性。

</details>

<details>
<summary>🎛️ 游戏控制台</summary>

![游戏控制台](https://zjusim-docs.67656.fun/assets/images/dashboard.png)

</details>

<details>
<summary>🎛️ 校园日志 </summary>

![校园日志](https://zjusim-docs.67656.fun/assets/images/events.png)

</details>

<details>
<summary>✨ 随机事件</summary>

![随机事件](https://zjusim-docs.67656.fun/assets/images/random.png)
![随机事件2](https://zjusim-docs.67656.fun/assets/images/random2.png)
![随机事件3](https://zjusim-docs.67656.fun/assets/images/random3.png)

</details>

<details>
<summary>💬 钉钉消息</summary>

![钉钉消息](https://zjusim-docs.67656.fun/assets/images/dingtalk.png)

</details>

## 快速开始

```bash
# 克隆源代码
git clone https://github.com/pirate-608/ZJUers_simulator.git
cd ZJUers_simulator
# 配置环境变量
cp .env.template .env
```
环境变量模版
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
MINIMAX_MODEL=minimax-m2-her
MINIMAX_BASE_URL=https://api.minimax.chat/v1/text/chatcompletion_v2
```

```bash
# 复制 Docker Compose 本地覆写模板
cp docker-compose.override.example docker-compose.override.yml

# 构建并启动
docker compose up -d --build

# 访问 http://localhost 即可开始游戏
```

## 内容同步

如需将本地的代码仓库中的文档内容同步到文档仓库，只需将两者放在统一目录下，如：

```
projects
├── ZJUers_simulator
└── ZJUers_simulator-docs
```

然后在scripts/sync_config.json中配置好`project_dir`, `source_folder`和`target_folder`

在代码仓库根目录执行
```bash
python scripts/sync_docs.py
```

## 许可证
本项目采用 MIT License 开源。

## 贡献
欢迎进行关键词补充！
欢迎 PR、Issue 及建议！

## 作者
pirate-608
