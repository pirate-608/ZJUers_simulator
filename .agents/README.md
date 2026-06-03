# Shared `.agents/` in `ZJUers Simulator` Project.

This directory is used by various AI agent tooling (e.g., Devin, OpenHands, or custom agent harnesses) for shared configuration.

> You can also migrate content from .claude/ or .codex/ configuration to this folder.
> **Note:** Claude Code does not read from the .agents/ folder. This directory is for other agent tooling only.

## Contents

- `AGENTS.md` – The primary agent instruction file. This is loaded by many agentic tools as the project-level "constitution" or README for agents.
- `skills/` – Cross-agent skills (format may vary by tool; markdown is safest).
- `workflows/` – YAML or markdown definitions of multi-step agent workflows.
- Configuration files for specific agents (e.g., `devin.yml`, `opencode.toml`).

## How to use

- **`AGENTS.md`** is the most important file. Write clear instructions that any general-purpose coding agent can follow.
- Prefer simple, action-oriented language: "When you see X, do Y."
- If a tool has its own format (e.g., Devin's `devin.yml`), place it here but name it clearly.

## For contributors

- Keep `AGENTS.md` tool-agnostic as much as possible. Avoid referencing a specific agent by name unless necessary.
- Use skills for complex, multi-step routines. Write them as step-by-step checklists.
- Test changes with at least one agent (e.g., Codex or Claude) before committing.
- Do not include environment-specific paths or credentials.

## Example AGENTS.md snippet

```markdown
# Agent instructions for Project X

- Always run `pnpm test` before suggesting a commit.
- Use `console.log` for debugging, never `alert()`.
- If you modify the API schema, update `docs/dev/api.md`.

## See Also:
- [AGENTS.md specification (unofficial)](https://agents.md/)