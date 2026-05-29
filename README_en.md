<div align="center">
  <img src="https://zjusim-docs.67656.fun/assets/images/logo.svg" alt="Game Logo" width="120" />
  <h1>ZJUers Simulator</h1>
  <p><strong>I placed 67,656 stars here, hoping every ZJUer can find the one that belongs to them</strong></p>
</div>

[![中文](https://img.shields.io/badge/🇨🇳_中文-Available-green)](README.md)
[![English](https://img.shields.io/badge/🇺🇸_English-Current-blue)](README_en.md)

## **Disclaimer**
This project is for entertainment purposes only. It does not provide any educational, examination, administrative, or management functions. All rights regarding specific information about the university are reserved by [@Zhejiang University](https://www.zju.edu.cn).

## Game URL: [67656.fun](https://67656.fun)

## Documentation: View [Project Docs](https://zjusim-docs.67656.fun)

## What is this?

This is "ZJUers Simulator," a game dedicated to building a parallel universe of Zhejiang University. We use large language models to provide content support for the game and maintain a comprehensive set of world-building files as the game's foundational setting.

## Co-create the World
If you think this game is decent but still feels like something is missing, it's because the world-building files we maintain are still in their early stages.
The structure of our world-building files is as follows:

```
zjus-backend/world/
├── courses/
│   └── ... (40 course JSON files in total, e.g., CS.json, AI.json)
├── achievements.json  # Achievement system
├── characters.json    # Character system
├── game_balance.json  # Game balance
├── keywords.json      # Keywords
├── majors.json        # Major system
├── notice.md          # Announcements
└── rules.html         # Game rules
```

The files within the `courses` folder constitute the course system (data source: [Undergraduate Academic Management Information Service Platform](https://zdbk.zju.edu.cn)). These files, along with `achievements.json`, `characters.json`, `majors.json`, `game_balance.json`, `keywords.json`, and others, are loaded directly by the backend.

The world-building files and the LLM together form the soul of this game. Using the LLM requires a paid API, but the contents of the `world/` folder are priceless. Its growth depends on every alumnus dedicated to building the world of the ZJUers Simulator.

We need you! Please don't hesitate to share your keyword inspirations, your suggestions, your PRs, your Issues — any help you can offer is our driving force.

## Game Interface Previews

<details>
<summary>🏁 Start Screen</summary>

![Start Screen](https://zjusim-docs.67656.fun/assets/images/start.png)

</details>

<details>
<summary>🧑‍🎓 Character Creation</summary>

![Character Creation](https://zjusim-docs.67656.fun/assets/images/create.png)
New players log in with an invite code, select a major, and allocate initial IQ / EQ / Luck attributes.

</details>

<details>
<summary>🎛️ Game Dashboard</summary>

![Game Dashboard](https://zjusim-docs.67656.fun/assets/images/dashboard.png)

</details>

<details>
<summary>🎛️ Campus Log</summary>

![Campus Log](https://zjusim-docs.67656.fun/assets/images/events.png)

</details>

<details>
<summary>✨ Random Events</summary>

![Random Events](https://zjusim-docs.67656.fun/assets/images/random.png)
![Random Events 2](https://zjusim-docs.67656.fun/assets/images/random2.png)
![Random Events 3](https://zjusim-docs.67656.fun/assets/images/random3.png)

</details>

<details>
<summary>💬 DingTalk Messages</summary>

![DingTalk Messages](https://zjusim-docs.67656.fun/assets/images/dingtalk.png)

</details>

## Quick Start

```bash
# Clone the source code
git clone https://github.com/pirate-608/ZJUers_simulator.git
cd ZJUers_simulator
# Configure environment variables
cp .env.template .env
```
Environment variable template
```bash
SECRET_KEY=your_random_string
DATABASE_URL=postgresql+asyncpg://zju:your_database_password@db:5432/zjus
POSTGRES_PASSWORD=your_database_password
ADMIN_USERNAME=your_admin_username
ADMIN_PASSWORD=your_admin_password
ADMIN_SESSION_SECRET=your_admin_session_secret
INVITE_CODES=local_test_invite_code_1,local_test_invite_code_2
LLM_API_KEY=your_llm_api_key (optional)
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM=your_model_name
MINIMAX_API_KEY=your_minimax_api_key (optional, leave empty to fall back to default LLM)
MINIMAX_MODEL=minimax-m2-her
MINIMAX_BASE_URL=https://api.minimax.chat/v1/text/chatcompletion_v2
```

```bash
# Copy the Docker Compose local override template
cp docker-compose.override.example docker-compose.override.yml

# Build and start
docker compose up -d --build

# Visit http://localhost to start playing
```

## Content Synchronization

To sync the documentation content from the local code repository to the documentation repository, simply place both in the same parent directory, for example:

```
projects
├── ZJUers_simulator
└── ZJUers_simulator-docs
```

Then configure `project_dir`, `source_folder`, and `target_folder` in `scripts/sync_config.json`.

Execute from the root of the code repository:
```bash
python scripts/sync_docs.py
```

## License
This project is open-sourced under the MIT License.

## Contributions
Keyword contributions are welcome!
PRs, Issues, and suggestions are welcome!

## Author
pirate-608