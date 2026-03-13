# 集成 MiniMax M2-her：解耦钉钉消息生成

## 问题描述

当前 `llm.py` 中 `generate_dingtalk_message` 将 `characters.json` 整体 dump 给通用 LLM，无法利用 M2-her 的 RP 角色系统。计划：
1. 将钉钉消息生成**从 `llm.py` 解耦**为独立模块
2. 使用 **httpx 直接调用 M2-her 原生 API**，深度利用其 `system`/`user_system`/`group`/`sample_message_*` 角色能力
3. 将 `characters.json` 中每个角色映射为 M2-her 的结构化 message

## User Review Required

> [!IMPORTANT]
> M2-her **不支持 `response_format: json_object`**，因此生成结果为自由文本而非 JSON。新模块会采用"先随机选角色，让 M2-her 以该角色身份生成一条消息"的策略，而非一次批量生成 5 条。

> [!WARNING]
> 需要配置 `MINIMAX_API_KEY` 环境变量。如果 M2-her 不可用，会自动 fallback 到原有的 `generate_dingtalk_message`。

---

## Proposed Changes

### 新模块：core/dingtalk_llm.py

#### [NEW] [dingtalk_llm.py](file:///d:/projects/ZJUers_simulator/zjus-backend/app/core/dingtalk_llm.py)

独立的 M2-her 钉钉消息生成模块，核心设计：

**1. 角色映射**：将 `characters.json` 中每个角色转为 M2-her messages：

```python
# characters.json 中的一个角色：
{
    "name": "【室友】",
    "role": "roommate",
    "content": "你是浙江大学某学生的室友...",
    "examples": ["你早上出门忘关空调了！", ...]
}

# 转换为 M2-her messages：
[
    {"role": "system", "name": "室友", "content": "你是浙江大学某学生的室友..."},
    {"role": "user_system", "content": "你是一位浙江大学{major}专业的学生，名叫{username}..."},
    {"role": "group", "content": "场景：浙大校园，{semester}，钉钉私聊"},
    {"role": "sample_message_ai", "name": "室友", "content": "你早上出门忘关空调了！"},
    {"role": "sample_message_user", "name": "用户", "content": "好的收到"},
    {"role": "sample_message_ai", "name": "室友", "content": "steam冬促又开始了..."},
    {"role": "user", "name": "用户", "content": "（等待接收钉钉消息）"}
]
```

**2. 核心函数签名**：

```python
async def generate_dingtalk_via_m2her(
    player_stats: dict,
    context: str = "random",
) -> Optional[dict]:
    """
    使用 M2-her 生成单条角色扮演钉钉消息。
    返回: {"sender": "室友", "role": "roommate", "content": "...", "is_urgent": false}
    """
```

**3. 调用方式**：httpx 直接请求原生 API

```python
async with httpx.AsyncClient() as client:
    resp = await client.post(
        "https://api.minimaxi.com/v1/text/chatcompletion_v2",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "M2-her",
            "messages": messages,
            "temperature": 1.0,
            "top_p": 0.95,
            "max_completion_tokens": 200,
        },
        timeout=15.0,
    )
```

**4. Redis 缓存**：M2-her 按角色生成单条消息（非批量），但仍可缓存：
- 每次调用可随机选 2-3 个不同角色并发请求
- 多余的消息存入 Redis 队列 `game:dingtalk_m2her`
- 后续优先从缓存消费

**5. Fallback**：若 M2-her 不可用（无 API key / 超时 / 报错），自动降级调用 `llm.py` 中的原有 `generate_dingtalk_message`

---

### 配置新增

#### [MODIFY] [config.py](file:///d:/projects/ZJUers_simulator/zjus-backend/app/core/config.py)

新增 MiniMax 相关配置：

```python
# MiniMax M2-her 配置（钉钉消息RP生成）
MINIMAX_API_KEY: str = os.environ.get("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL: str = os.environ.get(
    "MINIMAX_BASE_URL", "https://api.minimaxi.com/v1/text/chatcompletion_v2"
)
```

---

### 引擎切换

#### [MODIFY] [engine.py](file:///d:/projects/ZJUers_simulator/zjus-backend/app/game/engine.py)

修改 `_trigger_dingtalk_message`，优先使用 M2-her：

```python
async def _trigger_dingtalk_message(self):
    if not self.is_running:
        return
    try:
        snapshot = await self.repo.get_snapshot()
        stats = snapshot.stats.model_dump()

        # 上下文判断（保持不变）
        context = "random"
        ...

        # 优先使用 M2-her
        from app.core.dingtalk_llm import generate_dingtalk_via_m2her
        msg_data = await generate_dingtalk_via_m2her(stats, context)

        # M2-her fallback 到旧接口
        if not msg_data:
            msg_data = await generate_dingtalk_message(
                stats, context, llm_override=self.llm_override
            )

        if msg_data:
            await self.emit("dingtalk_message", {"data": msg_data})
    except Exception as e:
        logger.error(f"DingTalk trigger error: {e}", exc_info=True)
```

---

### 不修改的部分

- `llm.py` 中的 `generate_dingtalk_message` — **保留不变**，作为 fallback
- `characters.json` — **保留不变**，新模块读取同一份数据
- `cache.py` / `redis_repo.py` — 复用现有 Redis 缓存能力

---

## 变更影响总结

| 文件 | 变更类型 | 说明 |
|---|---|---|
| `core/dingtalk_llm.py` | **新建** | M2-her 原生 API 调用，角色映射，Redis 缓存 |
| `core/config.py` | 修改 | 新增 `MINIMAX_API_KEY` / `MINIMAX_BASE_URL` |
| `game/engine.py` | 修改 | `_trigger_dingtalk_message` 优先走 M2-her |

---

## Verification Plan

### Automated Tests

```bash
# 语法检查
python -c "import py_compile; py_compile.compile('app/core/dingtalk_llm.py', doraise=True)"

# 确认新模块存在并可导入（需在项目根目录）
python -c "from app.core.dingtalk_llm import generate_dingtalk_via_m2her; print('OK')"
```

### Manual Verification

1. 设置 `MINIMAX_API_KEY` 环境变量
2. 启动游戏，等待钉钉消息触发
3. 验证消息内容是否符合角色人设（检查日志中的 sender/role）
4. 移除 `MINIMAX_API_KEY`，验证自动 fallback 到旧接口
