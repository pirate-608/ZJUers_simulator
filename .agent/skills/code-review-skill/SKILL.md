# Smart Full-Stack Code Review Skill

## Description
当 Agent 较大程度修改了项目代码（“程度”由 Agent 自行判断，但必须确保不进行无意义的测试），或者用户要求“审查代码”、“跑一下检查”时触发。该技能具备路径感知能力，能够自动判断是前端还是后端代码发生了变更，并按需执行对应的静态检查和单元测试。

## Instructions
执行 Code Review 时，必须严格遵循以下步骤：

1. **变更范围侦测 (Scope Detection)：**
   - 检查本次对话中被修改、新增或审查的文件路径。
   - 如果变更包含 `zjus-backend/` 下的文件，标记 `RUN_BACKEND = true`。
   - 如果变更包含 `zjus-frontend/` 下的文件，标记 `RUN_FRONTEND = true`。
   - **核心规则：未被标记的端，绝对不执行对应的检查和测试。**

2. **后端审查流水线 (If RUN_BACKEND is true)：**
   - 必须先 `cd zjus-backend`。
   - 运行格式化：`python -m ruff format .`
   - 运行静态检查：`python -m ruff check --fix .`
   - 如果 ruff 报错，阅读并尝试修改代码修复，直到通过。
   - 运行测试：`python -m pytest tests/ -v`
   - 如果 pytest 失败，读取 traceback 并尝试修复代码至多 2 次。如果依然失败，使用 `ask_user` 询问用户。

3. **前端审查流水线 (If RUN_FRONTEND is true)：**
   - 必须先 `cd zjus-frontend`。
   - 运行逻辑与格式检查：`npm run lint` (假设 package.json 中配置了 eslint --fix)。
   - 如果 ESLint 报出 Error 级别的错误，阅读并尝试修改代码修复。
   - 运行前端测试：`npm run test` (假设配置了 Vitest)。
   - 如果测试失败，尝试修复至多 2 次。如果依然失败，使用 `ask_user` 询问用户。

4. **结果汇报 (Reporting)：**
   - 检查完成后，向用户提供一份简报。
   - 明确指出刚才执行了哪一端的检查（例如：“检测到仅修改了 FastAPI 路由，已跳过前端检查”），并汇报最终的通过情况。

## Constraints
- **严禁**跨目录执行命令（必须在对应的 `zjus-backend` 或 `zjus-frontend` 目录下执行各自的命令）。
- **严禁**为了让测试通过而删除或注释掉测试用例中的断言。
- **严禁**修改任何代码时都执行测试，必须判断是否有测试的必要性。
- 对于后端的警告 (Warning) 视为通过；但对于前端 ESLint 的 Error 必须修复。