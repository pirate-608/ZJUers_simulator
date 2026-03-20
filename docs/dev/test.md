# pytest 测试基础设施

## 测试文件

| 文件                                                                                                      | 用途                                                                            | 测试数 |
| --------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- | ------ |
| [pyproject.toml](file:///d:/projects/ZJUers_simulator/zjus-backend/pyproject.toml)                        | pytest 配置（pythonpath、asyncio_mode）                                         | —      |
| [conftest.py](file:///d:/projects/ZJUers_simulator/zjus-backend/tests/conftest.py)                        | 环境变量、sample data fixtures、mock Redis                                      | —      |
| [test_game_state.py](file:///d:/projects/ZJUers_simulator/zjus-backend/tests/unit/test_game_state.py)     | PlayerStats: build_initial / from_redis / get_repair_fields / GameStateSnapshot | 20     |
| [test_balance.py](file:///d:/projects/ZJUers_simulator/zjus-backend/tests/unit/test_balance.py)           | GameBalance: 加载/属性/默认值/热重载                                            | 12     |
| [test_dingtalk_llm.py](file:///d:/projects/ZJUers_simulator/zjus-backend/tests/unit/test_dingtalk_llm.py) | M2-her: 消息构建/API mock/缓存/fallback                                         | 29     |

## 测试依赖

后端测试依赖已在 requirements.txt 中声明，主要包括：

- **pytest**：主测试框架。
- **pytest-asyncio**：支持异步测试。
- **ruff**：代码风格检查与自动修复。

其他依赖如 mock、数据库驱动等也会被用于 fixture 或测试环境。

## 使用方式

```bash
# 激活 venv 后
cd zjus-backend # 进入后端目录

# 运行测试
python -m pytest tests/ -v

# 代码风格检查
python -m ruff format .         # 运行格式化
python -m ruff check --fix .    # 运行静态检查并修复
```

## 运行结果示例

```
======================== 61 passed, 1 warning in 0.38s ========================
```

这代表61个测试用例全部通过，1个测试用例有警告。这种情况是可接受的。如果想看具体是哪个测试用例有警告，可以使用 `python -m pytest tests/ -v` 命令。