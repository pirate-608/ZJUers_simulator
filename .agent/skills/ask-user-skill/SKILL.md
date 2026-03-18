# Universal Environment Configurator

## Description
当用户要求初始化项目、设置环境变量、配置数据库连接，或处理 `.env`、`config.yaml` 等配置文件时，触发此技能。它负责安全地收集、验证并应用环境配置。

## Instructions
在执行任何环境配置任务时，必须严格遵循以下步骤：

1. **扫描模板文件：** 首先检查项目根目录或 `config/` 目录下是否存在 `.env.example`、`.env.template`、`config.sample.json` 等参考文件。
2. **提取必需项：** 分析模板文件或项目代码（如依赖检查），列出所有缺失的关键环境变量（例如：API 密钥、数据库端口、运行环境标识）。
3. **主动询问 (Crucial Step)：** **严禁**自行伪造、猜测或生成随机的密码、密钥和端口号。对于任何缺失的具体配置值，必须调用 `ask_user` 工具向用户请求信息。
   - 使用 `ask_user` 时，将需要填写的变量以清晰的列表形式呈现。
   - 如果某个变量有合理的默认值（例如本地开发时的 `PORT=8080`），请在提问时附带该默认值供用户参考或确认。
   - 如果涉及环境选择，请提供明确的选项（如：Development, Testing, Production）。
4. **安全写入：** 获取用户回复后，再将最终配置写入目标文件（如 `.env`）。
5. **Git 安全检查：** 确保写入的敏感配置文件已经被包含在 `.gitignore` 中，防止意外提交。

## Constraints
- **绝对禁止**在没有用户明确授权的情况下，覆盖或删除已存在且包含数据的 `.env` 或配置文件。如果文件已存在，必须先使用 `ask_user` 询问是否覆盖或追加。
- **绝对禁止**在日志或常规对话中明文回显用户通过 `ask_user` 输入的高敏感信息（如真实的云服务 Secret Key）。
- 始终保持配置文件的标准格式（例如，Python/Docker 项目常用的 `KEY=VALUE` 格式，等号两边无空格）。

## Examples
### Example 1: 初始化新环境
**User:** "帮我把这个项目的环境配好。"
**Agent Internal Logic:** 扫描发现 `.env.example` 包含 `DB_HOST` 和 `OPENAI_API_KEY`，但本地没有 `.env` 文件。
**Agent Action:** 调用 `ask_user` 工具：
> "我需要为您创建 `.env` 文件。请提供以下缺失的配置项：
> 1. `OPENAI_API_KEY` (必填)
> 2. `DB_HOST` (回车默认使用 localhost)"

### Example 2: 危险操作拦截
**User:** "把数据库配置改成生产环境的。"
**Agent Internal Logic:** 发现目标文件 `.env` 已经存在，直接修改有丢失本地开发配置的风险。
**Agent Action:** 调用 `ask_user` 工具：
> "检测到当前已存在 `.env` 文件。您是要直接覆盖它，还是让我创建一个新的 `.env.production` 文件？"