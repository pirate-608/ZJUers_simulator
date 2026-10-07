# 登录前序章归档

2026-10-07 起，序章从游戏主线移除。首次访问直接进入登录页；已有登录状态继续按原凭证、存档和 `game_started` 分流。

此目录保存三页日记序章的组件、静态文案、原入口闸门测试和设计说明，供历史查阅。它位于前端 `src/` 与文档站之外，不参与前端编译、测试、文档构建或 Docker 应用构建。

- `components/PrologueScene.vue`：献词、逐字书写、翻页和背景切换组件；文案引用已改为本目录相对路径。
- `data/prologue.ts`：静态文案、图片映射和原 `zjus_prologue_seen_v1` key。
- `App.spec.js`：原 `App.vue` 闸门测试快照，依赖归档前的目录与启动逻辑，不能作为当前入口测试运行。
- `prologue-design.md`：原设计与实现说明。

校园图片仍由登录页和毕业页共用，保留在 `zjus-frontend/public/images/`。浏览器中遗留的 `zjus_prologue_seen_v1` key 不再读写，无需玩家清理。

如果未来重新接入，需要独立评估入口设计与测试。当前 `App.vue` 不加载此目录，也没有序章完成/跳过回调。
