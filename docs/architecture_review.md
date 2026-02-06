# FastAPI 项目架构分析与改进计划

## 现状分析

### 1) 依赖注入与资源生命周期
- 当前依赖注入主要集中在数据库会话 (get_db) 与少量路由中。
- Redis 连接池在多个模块中各自维护，缓存与游戏状态层有重复逻辑。
- WebSocket 生命周期和游戏引擎生命周期耦合，缺少统一的连接/会话上下文管理。

### 2) 代码解耦与层次划分
- API 层、业务逻辑层、存储层混用较多，模块间直接依赖较深。
- 某些业务逻辑位于路由函数中 (例如存档加载/修复流程)，不利于复用和测试。
- LLM 逻辑、Redis 缓存、游戏数值与状态更新之间的边界不够清晰。

### 3) 可测试性
- 业务逻辑依赖全局状态或模块级实例，单元测试难以隔离。
- 复杂流程缺少可插拔的 service 或 repository 接口，难以注入 mock。
- WebSocket 路径与游戏引擎耦合，测试时不易模拟多用户并发。

### 4) 接口与实现堆砌
- 路由函数承担了过多职责：鉴权、加载存档、修复数据、启动引擎。
- 存储细节 (Redis key, JSON 结构) 在不同层面重复出现。

### 5) 存储与应用逻辑混合
- Redis 写入、读取和业务决策混在同一模块内，难以复用或替换存储层。
- DB 和 Redis 的一致性策略分散在多个文件中，维护成本较高。

## 改进计划

### 1) 依赖注入与资源管理
- 引入统一的依赖注入入口，集中定义:
  - DB 会话依赖 (get_db)
  - Redis 客户端依赖 (get_redis)
  - 配置对象依赖 (get_settings)
- 在 app/api/deps.py 中集中管理 Depends，避免散落定义。
- WebSocket 连接使用会话对象封装 (WebSocketContext)，统一管理 user_id, state, engine。

### 2) 分层清晰化
- 建议分为 API / Service / Repository 三层:
  - API: 只负责 HTTP/WS 协议、参数验证、返回格式。
  - Service: 业务逻辑 (存档处理、初始化、修复、游戏循环入口等)。
  - Repository: 存储操作 (Redis/DB 封装)。
- 将存档加载、修复、保存等逻辑从路由移至 Service。
- RedisState 专注于状态读写，业务流程由 GameService 或 SaveService 处理。

### 3) 统一存储协议与模型
- 定义 Pydantic 模型作为 Redis/DB 数据映射的中间层。
- Redis 的 key 规则和数据结构集中在单一模块 (例如 repositories/redis_keys.py)。
- 使存储实现可替换，方便测试时使用内存存储。

### 4) 降低模块耦合
- LLM 调用封装为 LLMService，API 与引擎通过接口调用，不直接依赖 SDK。
- 连接管理、引擎、状态更新解耦，避免引擎直接访问 WebSocket。
- 使用事件总线或消息队列 (内存队列即可) 传递事件与通知。

### 5) 可测试性提升
- 为 Service 层设计接口，支持注入 mock repository。
- 为游戏引擎提供可配置 tick 间隔与随机数种子，便于可复现测试。
- 新增单元测试覆盖:
  - 存档加载/修复流程
  - Redis TTL 刷新策略
  - GameEngine 关键路径 (tick, game over, exam)

### 6) 依赖与配置规范化
- 将 Redis TTL、LLM 缓存上限/TTL 等配置项纳入 config.py。
- 在 settings 中添加缓存策略配置，统一维护。
- 明确生产/开发配置差异，避免硬编码。

## 建议的目录结构示例

app/
  api/
    deps.py
    auth.py
    game.py
  services/
    game_service.py
    save_service.py
    llm_service.py
  repositories/
    redis_repo.py
    db_repo.py
  core/
    config.py
    security.py
  game/
    engine.py
    state.py
  websockets/
    manager.py

## 下一步实施建议 (优先级)

1) 抽离存档流程到 SaveService，路由只做参数验证和调用。
2) 引入统一 RedisRepository，集中 Redis key 与 TTL 管理。
3) 拆分 WebSocket 处理流程，减少 game.py 路由体积。
4) 为 Service 层增加单元测试与 mock。
5) 配置项规范化，减少硬编码常量。

## 风险与注意事项

- 分层重构需要逐步进行，避免一次性大改导致功能回归。
- WebSocket 逻辑需保持兼容，建议保留旧接口并逐步替换。
- Redis/DB 的一致性策略调整要配合测试验证。
