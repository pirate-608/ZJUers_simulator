# Auto Docs Sync Skill

## Description
当 Agent 在项目中新建、修改或删除了 `docs` 目录下的任何文档文件，或者当用户明确输入“同步文档”等相关指令时，自动触发此技能。该技能负责读取和调整 `scripts/sync_docs.json`，执行同步脚本 `scripts/sync_docs.py`，并确保过程无误。

## Instructions
执行文档同步任务时，请严格按照以下步骤操作：

1. **配置检查与动态调整 (Pre-check)：**
   - 检查项目根目录下的 `scripts/sync_docs.json` 是否存在且格式有效。
   - 默认情况下保持现有配置不变。
   - **特殊情况处理：**
     - 如果用户要求“测试同步”或“试运行”，请将 `"dry_run"` 临时设置为 `true`。
     - 如果本次文档更新涉及大量文件重构或覆盖，主动将 `"backup.enabled"` 设置为 `true`，以防数据丢失。

2. **执行同步 (Execution)：**
   - 在项目根目录下执行命令：
     ```bash
     ./.venv/scripts/activate      # 激活虚拟环境
     python scripts/sync_docs.py   # 执行同步脚本
     ```
   - 捕获脚本的标准输出 (stdout) 和标准错误 (stderr)。

3. **自动诊断与修复 (Auto-Correction)：**
   - 检查脚本的退出状态码和错误日志。如果检测到失败（非 0 退出码或出现 Traceback）：
     - **路径错误：** 如果是 `target_folder` (zjusim-docs) 不存在，请尝试自动创建该目录。
     - **权限错误：** 检查文件锁定或权限问题。
     - **代码级错误：** 如果是 `sync_docs.py` 内部的 Python 逻辑报错，请阅读脚本源码并尝试修复 Bug。
     - 自动修复后允许重试 **1 次**。如果再次失败，必须使用 `ask_user` 工具将错误日志直接展示给用户，暂停后续操作。

4. **结果反馈 (Reporting)：**
   - 脚本成功执行后，解析控制台输出或读取 `"logging.log_file"` (`sync_log.txt`) 中的最新条目。
   - 向用户提供一个简明的同步摘要（例如：“同步完成：新增 2 个文件，更新 1 个文件。排除规则已生效”）。

## Constraints
- **严禁**随意修改 `"exclude_patterns"` 中的安全项（如 `.git`, `__pycache__`），除非用户明确指示。
- **禁止**进入死循环：如果修复脚本后依然报错，必须停止重试并呼叫用户。
- 只有在执行完文档的“编写/修改”动作后，才能触发此同步流程，不要在同步过程中再次修改文档内容。

