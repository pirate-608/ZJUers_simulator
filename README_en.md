<div align="center">
  <img src="https://zjusim-docs.67656.fun/assets/images/logo.svg" alt="Game Logo" width="120" />
  <h1>ZJUers Simulator</h1>
  <p><strong>I've placed 67,656 stars here, hoping every ZJUer can find their own.</strong></p>
</div>

[![English](https://img.shields.io/badge/🇺🇸_English-current-green)](README_en.md)
[![中文](https://img.shields.io/badge/🇨🇳_中文-切换-blue)](README.md)

## **Disclaimer**
This project is for entertainment purposes only and does not provide any teaching, examination, administrative, or management-related functions. All rights regarding specific information about the university are reserved by [Zhejiang University](https://www.zju.edu.cn).

## Game Website: [67656.fun](https://67656.fun)

## Documentation: [Project Documentation](https://zjusim-docs.67656.fun)

## What is this?

This is the "Zhejiang University Simulator," a game dedicated to creating a parallel universe of Zhejiang University. We use large language models to provide content support for the game and maintain a comprehensive set of world-building files as the foundational setting for the game.

## Co-create the Worldview
If you think this game is decent but still feels like something is missing, it's because the world-building files we maintain are still in their early stages.  
Our world-building files are structured as follows:

```
zjus-backend/world/
├── courses/
│   └── ... (40 course JSON files in total, such as CS.json, AI.json, etc.)
├── achievements.json  # Achievement system
├── characters.json    # Character system
├── entrance_exam.json # Entrance exam
├── game_balance.json  # Game balance
├── keywords.json      # Keywords
├── majors.json        # Major system
├── notice.md          # Announcements
└── rules.html         # Game rules
```

The `courses` folder contains the course system (data source: [Undergraduate Academic Management Information Service Platform](https://zdbk.zju.edu.cn)), and along with files like `achievements.json`, `characters.json`, `majors.json`, `game_balance.json`, and `keywords.json`, they are loaded directly by the backend.

Together, the world-building files and the LLM form the soul of this game. While the LLM requires paid API usage, the content in the `world/` folder is invaluable. Its growth depends on every alumnus committed to building the world of the ZJUers Simulator.

We need you! Please don’t hesitate to share your keyword inspirations, suggestions, PRs, issues, or any form of help. Your support is what drives us forward.

## Game Interface Previews

<details>
<summary>🏁 Start Screen</summary>

![Start Screen](https://docs.67656.fun/assets/images/start.png)

</details>

<details>
<summary>📝 Entrance Exam</summary>

![Entrance Exam](https://docs.67656.fun/assets/images/exam.png)

</details>

<details>
<summary>📜 Admission Letter</summary>

![Admission Letter](https://docs.67656.fun/assets/images/admission.png)

</details>

<details>
<summary>🎛️ Game Dashboard</summary>

![Game Dashboard](https://docs.67656.fun/assets/images/dashboard.png)

</details>

<details>
<summary>🎛️ Game Dashboard 2</summary>

![Game Dashboard 2](https://docs.67656.fun/assets/images/dashboard2.png)

</details>

<details>
<summary>✨ Random Events</summary>

![Random Events](https://docs.67656.fun/assets/images/event.png)

</details>

<details>
<summary>💬 DingTalk Messages</summary>

![DingTalk Messages](https://docs.67656.fun/assets/images/dingtalk.png)

</details>

## License
This project is open-sourced under the MIT License.

## Contributions
We welcome keyword contributions!  
Feel free to submit PRs, issues, or suggestions!

## Author
pirate-608