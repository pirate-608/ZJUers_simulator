<div align="center">
  <h1>发行说明</h1>
</div>

## 1.1.0

### 内容与检索架构升级

- 内容系统从“运行时大模型直生”切换为“**离线预构建 + 运行时检索**”。
- 新增预构建产物：
  - `world/event_library.json`
  - `world/cc98_library.json`
  - `world/query_embeddings.json`
  - `world/character_embeddings.csv`
- 运行时检索策略：
  - 事件/CC98：本地库优先，LLM 兜底
  - 钉钉角色：pgvector 相似度检索优先，随机/LLM 兜底

### 部署链路更新

- Docker 启动新增 `seed_embeddings` 一次性服务：
  - `migrate` 后自动导入 `character_embeddings.csv` 到 pgvector 表。
- `backend` 启动依赖改为：`db -> migrate -> seed_embeddings -> backend`。
- 本地开发与云端部署流程统一为同一检索范式。

### CI/CD 更新

- 发布工作流增加预构建资产完整性校验，防止缺失资产发布。
- 本地 release 包流程同步加入 `seed_embeddings` 服务定义。

### 开发文档更新

- 新增“本地预构建资产流程”说明：
  - 本地 AI 生成 JSON 内容库脚本
  - 本地向量化导出 CSV/查询向量脚本

## 1.0.0

- 初始版本