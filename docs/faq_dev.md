## 开发者常见问题 (FAQ)

> 适用对象：参与该项目后端/前端/数据维护/部署的开发者。

### 1. 项目入口与整体结构是什么？
- 后端入口是 [app/main.py](https://github.com/pirate-608/ZJUers_simulator/tree/main/app/main.py)。
- 主要目录：
	- [app/api](https://github.com/pirate-608/ZJUers_simulator/tree/main/app/api)：HTTP/WS 路由与依赖注入。
	- [app/core](https://github.com/pirate-608/ZJUers_simulator/tree/main/app/core)：配置、数据库、LLM、安全等基础能力。
	- [app/game](https://github.com/pirate-608/ZJUers_simulator/tree/main/app/game)：核心玩法逻辑与引擎。
	- [app/repositories](https://github.com/pirate-608/ZJUers_simulator/tree/main/app/repositories)：Redis 读写与数据归一化。
	- [app/services](https://github.com/pirate-608/ZJUers_simulator/tree/main/app/services)：业务编排（存档、世界、游戏流程）。
	- [world](https://github.com/pirate-608/ZJUers_simulator/tree/main/world)：静态世界数据（专业/课程/规则/成就等）。

### 2. 本地运行的最小步骤？
- 安装依赖：
	- `pip install -r requirements.txt`
- 启动服务：
	- `uvicorn app.main:app --reload`
- 如果依赖 Redis/数据库，请参考 README 中的环境变量与 Docker 配置。

### 3. Redis 数据在哪里定义？如何保证结构一致？
- 所有 Redis 读写都集中在 [app/repositories/redis_repo.py](https://github.com/pirate-608/ZJUers_simulator/tree/main/app/repositories/redis_repo.py)。
- 统一的结构归一化使用 Pydantic 模型（如 `GameStateSnapshot`），避免字段类型漂移。

### 4. 为什么不在引擎里直接写 Redis？
- 为了可测试性与一致性，引擎只调用仓储层接口。
- 这样可以集中处理 TTL、字段归一化、版本兼容等逻辑。

### 5. WebSocket 与引擎如何解耦？
- 引擎通过事件队列发出 `GameEvent`。
- WebSocket 层只负责转发事件，异常不会中断循环。

### 6. 游戏初始化与“开局数据”从哪里来？
- 开局流程由 `GameService` 负责（初始化 stats/major 等）。
- 读取世界数据使用 `WorldService`，可做缓存优化。

### 7. 课程/专业/规则数据如何维护？
- 静态数据位于 [world](https://github.com/pirate-608/ZJUers_simulator/tree/main/world)。
- 课程在 [world/courses](https://github.com/pirate-608/ZJUers_simulator/tree/main/world/courses) 下以专业缩写命名的 JSON 文件维护。
- 修改后建议运行数据清洗脚本并验证前端展示。

### 8. 存档数据是如何保存与恢复的？
- `SaveService` 负责从 Redis 快照生成 DB 存档与恢复。
- 如果更改 stats/courses 结构，需同步更新快照与迁移逻辑。

### 9. 如何添加新的事件或推送字段？
- 事件结构定义在 `GameEvent`（[app/core/events.py](https://github.com/pirate-608/ZJUers_simulator/tree/main/app/core/events.py)）。
- 引擎中统一通过 `emit()` 推送事件。
- 前端接收字段需同步更新静态脚本（如 [static/js/main.js](https://github.com/pirate-608/ZJUers_simulator/tree/main/static/js/main.js)）。

### 10. 依赖注入 (DI) 入口在哪里？
- 所有 FastAPI 依赖集中在 [app/api/deps.py](https://github.com/pirate-608/ZJUers_simulator/tree/main/app/api/deps.py)。
- 新增 service/repo 时优先加入该文件，避免散落式依赖。

### 11. 常见问题：IQ 或课程进度异常
- 如果某些老存档缺少字段，仓储层会进行修复/默认值填充。
- 若业务规则改变，请在 `GameService` 中集中处理迁移逻辑。

### 12. 如何排查“事件不推送/WS 中断”？
- 检查 WebSocket 是否保持连接、前端是否有重连逻辑。
- 事件转发处已做异常捕获，但仍建议查看服务日志。

### 13. 如何添加新配置或环境变量？
- 配置统一在 [app/core/config.py](https://github.com/pirate-608/ZJUers_simulator/tree/main/app/core/config.py)。
- README 中同步补充使用说明。

### 14. 什么时候需要更新 requirements.txt？
- 新增第三方依赖或版本变更时。
- 记得保持与 Dockerfile/CI 的一致性。

### 15. 有推荐的调试流程吗？
- 后端：先看日志，再看 Redis 快照内容是否合理。
- 前端：检查 WebSocket 数据流和渲染异常。
- 数据：验证 world JSON 的结构与字段完整性。
