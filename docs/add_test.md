# pytest 测试基础设施 — 完成

## 创建的文件

| 文件 | 用途 | 测试数 |
|---|---|---|
| [pyproject.toml](file:///d:/projects/ZJUers_simulator/zjus-backend/pyproject.toml) | pytest 配置（pythonpath、asyncio_mode） | — |
| [conftest.py](file:///d:/projects/ZJUers_simulator/zjus-backend/tests/conftest.py) | 环境变量、sample data fixtures、mock Redis | — |
| [test_game_state.py](file:///d:/projects/ZJUers_simulator/zjus-backend/tests/unit/test_game_state.py) | PlayerStats: build_initial / from_redis / get_repair_fields / GameStateSnapshot | 20 |
| [test_balance.py](file:///d:/projects/ZJUers_simulator/zjus-backend/tests/unit/test_balance.py) | GameBalance: 加载/属性/默认值/热重载 | 12 |
| [test_dingtalk_llm.py](file:///d:/projects/ZJUers_simulator/zjus-backend/tests/unit/test_dingtalk_llm.py) | M2-her: 消息构建/API mock/缓存/fallback | 29 |

## 运行结果

```
======================== 61 passed, 1 warning in 0.38s ========================
```

## 使用方式

```bash
# 激活 venv 后
python -m pytest tests/ -v
```
