---
name: code-review-skill
description: 一个智能的全栈代码审查技能，能够根据修改的文件路径自动判断是前端还是后端代码发生了变更，并按需执行对应的静态检查和单元测试。
---

# Smart Full-Stack Code Review Skill

## Description
触发条件（满足任一即触发）：
- 用户明确要求"审查代码"、"跑一下检查"、"lint"、"format"等。
- Agent 修改了项目中任意文件，且变更行数 ≥ 5 行（仅统计新增/修改行，不含删除行）。
- Agent 修改了核心模块（`app/game/`、`app/services/`、`src/stores/`、`src/api/`），不受行数限制。

该技能具备路径感知能力，能够自动判断是前端还是后端代码发生了变更，并按需执行对应的静态检查和单元测试。

## Instructions
执行 Code Review 时，必须严格遵循以下步骤：

### 步骤 1：变更范围侦测 (Scope Detection)
检查本次对话中被修改、新增或审查的文件路径：
- 变更包含 `zjus-backend/` → 标记 `RUN_BACKEND = true`
- 变更包含 `zjus-frontend/` → 标记 `RUN_FRONTEND = true`
- 两端均有变更 → 两者均标记为 true，按先 Backend 后 Frontend 的顺序依次执行
- **核心规则：未被标记的端，绝对不执行对应的检查和测试。**

### 步骤 2：执行审查流水线
根据步骤 1 的标记，仅执行被标记的流水线。两端均标记时，先执行 Backend 流水线，完成后再执行 Frontend 流水线。

#### 后端审查流水线 (RUN_BACKEND = true)
| 顺序 | 操作 | 命令 | 失败处理 |
|------|------|------|----------|
| 1 | 切换目录 | `cd zjus-backend` | — |
| 2 | 格式化 | `python -m ruff format .` | — |
| 3 | 静态检查 | `python -m ruff check --fix .` | 阅读错误，修改代码直到通过 |
| 4 | 单元测试 | `python -m pytest tests/ -v` | 修复至多 2 次，仍失败则询问用户 |

#### 前端审查流水线 (RUN_FRONTEND = true)
| 顺序 | 操作 | 命令 | 失败处理 |
|------|------|------|----------|
| 1 | 切换目录 | `cd zjus-frontend` | — |
| 2 | Lint + 类型检查 | `npm run lint && npm run type-check` | ESLint Error 级别必须修复 |
| 3 | 组件类型检查 | `vue-tsc --noEmit` | 修复类型错误 |
| 4 | 单元测试 | `npm run test` | 修复至多 2 次，仍失败则询问用户 |

4. **结果汇报 (Reporting)：**
   - 检查完成后，向用户提供一份简报。
   - 明确指出刚才执行了哪一端的检查（例如：“检测到仅修改了 FastAPI 路由，已跳过前端检查”），并汇报最终的通过情况。

## Constraints
独立步骤（按顺序执行）：
1) 目录：命令必须在对应目录执行；后端仅在 `zjus-backend`，前端仅在 `zjus-frontend`。
2) 工具：若工具缺失或命令无法执行，告知用户并给出安装/修复建议，停止。
3) 静态检查：ESLint Error 必须修复；后端 ruff Warning 视为通过。
4) 测试触发：仅在函数/方法实现逻辑、数据库查询或写入逻辑、API 路由或请求/响应字段、数据模型或状态流转变更时运行测试；仅格式化/注释/类型注解变更跳过测试。
5) 测试禁令：禁止为通过测试而删除/注释测试用例断言。