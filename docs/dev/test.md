# 测试与验证

本页记录当前项目常用验证入口。测试数量会随功能变化增减，最终以命令输出为准。

## 后端

后端测试位于 `zjus-backend/tests/unit/`，覆盖游戏状态、数值配置、Admin 数值平衡表单发布、钉钉私聊状态、DingTalk LLM 降级、认证校验和玩家入口/存档流程。

常用命令：

```powershell
cd zjus-backend
..\.venv\Scripts\python.exe -m pytest tests\unit
..\.venv\Scripts\python.exe -m pytest tests\unit\test_admin_balance_config.py tests\unit\test_balance.py
..\.venv\Scripts\python.exe -m py_compile app\game\engine.py
..\.venv\Scripts\python.exe -m py_compile app\game\balance.py app\services\balance_admin.py app\admin.py
..\.venv\Scripts\python.exe -m ruff check .
```

修改共享模型、引擎状态、Redis 快照或存档逻辑时，优先跑完整 `tests\unit`。只改窄路径时，可以先跑对应 focused test，再在交付前补完整相关套件。

## 前端

前端测试位于 `zjus-frontend/src/**/*.spec.*`。

当前重点：

- `src/App.spec.js`：登录前序章闸门、登录/存档启动分流、WebSocket 不应在序章期间提前连接。
- `src/stores/gameStore.spec.ts`：钉钉联系人状态恢复、未读数与本地已读更新。

常用命令：

```powershell
cd zjus-frontend
.\node_modules\.bin\vue-tsc.cmd --noEmit
.\node_modules\.bin\vitest.cmd run
.\node_modules\.bin\vite.cmd build
```

涉及玩家入口、WebSocket、钉钉面板、引导暂停或反馈弹窗时，应增加 focused test 或浏览器 smoke。

## 文档

文档站使用 VitePress。首页交互式 demo 复用了 `zjus-frontend` 的 Vue 组件，因此干净环境或 CI 中要先安装前端依赖，再构建文档：

```powershell
cd zjus-frontend
npm install
cd ..\docs
npm install
npm run build
```

文档站不再手工维护旧资源下载包；世界观、课程、角色、数值和向量资源以仓库中的 `zjus-backend/world/` 最新文件为准。

## OpenAPI 与 Compose 验证

后端 HTTP 路由或 Pydantic 模型变化后，需要用 Docker Compose 后端重新生成前端类型：

```powershell
docker compose up -d --build backend
$openapi = $null
for ($i = 0; $i -lt 30; $i++) {
    try {
        $openapi = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/openapi.json
        if ($openapi.StatusCode -eq 200) { break }
    } catch {
        Start-Sleep -Seconds 2
    }
}
if (-not $openapi -or $openapi.StatusCode -ne 200) {
    throw "Backend did not serve /openapi.json in time."
}
cd zjus-frontend
.\node_modules\.bin\openapi-typescript.cmd http://127.0.0.1:8000/openapi.json -o src/types/api.generated.ts
```

不要手写 `zjus-frontend/src/types/api.generated.ts`；生成类型不匹配时先修后端 Pydantic/FastAPI 契约。`zjus-frontend/src/api/client.ts` 保持手写薄封装。生产基础 Compose 不发布后端端口，本地 OpenAPI 生成依赖 `docker-compose.override.yml` 提供的 `127.0.0.1:8000:8000` 映射。

## 选择测试范围

| 改动范围 | 建议验证 |
|---|---|
| 纯文档 | 前端依赖已安装时 `cd docs; npm run build`；干净环境先安装 `zjus-frontend` 依赖 |
| 前端 UI/状态 | `vue-tsc --noEmit`、`vitest run` 或 focused spec |
| 后端引擎/状态 | `pytest tests\unit`、`py_compile`、`ruff check` |
| API/模型 | Docker Compose 后端、OpenAPI 生成、前端类型检查 |
| Docker/部署 | `docker compose config`、服务启动日志、生产 smoke |

pytest 可能出现依赖库弃用警告；只要测试结果通过且警告与本次改动无关，可以在交付说明中记录为残余风险。
