# About `.github/` of ZJUers Simulator Project

This directory contains GitHub-specific configuration for this repository.

## Contents

### For GitHub Copilot

| File / Directory | Purpose |
| :--- | :--- |
| `copilot-instructions.md` | Main instruction file for Copilot Chat. Automatically included in all Copilot requests. |
| `instructions/*.instructions.md` | Path‑specific instructions. Use `applyTo` glob pattern to target certain files or directories. |
| `prompts/*.prompt.md` | Reusable prompt templates. Reference them manually with `#` in Copilot Chat. |
| `skills/*/SKILL.md` | Agent skills for Copilot. Place each skill in its own subdirectory. |

> **Note:** Copilot also reads `AGENTS.md` or `CLAUDE.md` if placed at the repository root, but does **not** read `.agents/` or `.claude/` subdirectories automatically.
> You can also migrate skills from `.codex/`,`.agents/` or `.claude/` to this folder.

### For GitHub Actions (Workflows)

- `workflows/` – CI/CD pipeline definitions
- `workflows/deploy_docs.yml` - Auto build and deploy documentations（View them in `docs/` and [mkdocs.yml](../mkdocs.yml)）
- `workflows/docker-release.yml` - Build and publish Docker Images of game modules（`zjus-backend` and `zjus-frontend`）to [Docker Hub](https://hub.docker.com/) when pushing tags.
- `workflows/mirror-to-gitee.yml` - Auto mirror this repo to [Gitee repo](https://gitee.com/huang-youran/ZJUers_simulator)
---

## For contributors

- Keep `copilot-instructions.md` concise and project‑wide.
- Use `instructions/` for rules that apply only to specific paths (e.g., backend vs frontend).
- Name instruction files clearly: `python.instructions.md`, `frontend.instructions.md`, etc.
- Each skill in `skills/` should have a `SKILL.md` with frontmatter (`name`, `description`) and clear steps.

## See also

- [GitHub Action documentation](https://docs.github.com/actions)
- [GitHub Copilot documentation](https://docs.github.com/en/copilot)
- [GitHub Copilot instructions](https://docs.github.com/en/copilot/how-tos/chat-with-copilot/chat-in-ide#adding-custom-instructions-for-copilot-chat)
- [GitHub Copilot Skills](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills)