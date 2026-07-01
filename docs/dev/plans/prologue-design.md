# 登录前序章实现说明

- 实现位置：`zjus-frontend/src/components/PrologueScene.vue` 与 `zjus-frontend/src/data/prologue.ts`

- 文本来源：序章文本已内置在前端 `prologue.ts` 中，不依赖后端静态 world 路径

- 时机：在用户首次访问站点时，加载登录页之前播放；播放完成或跳过后写入 `localStorage.zjus_prologue_seen_v1`

- 效果：前两句献词依次全屏闪现；主体故事以三页日记本逐字书写呈现，翻页切换白天、夜晚启真湖和重生返校三段；背景画面根据文字氛围动态切换

- 元素：可跳过，用户首次访问站点才加载；序章期间不进入登录/存档分流，也不建立游戏 WebSocket

- 注意要点：`PrologueScene.vue` 只负责视觉节奏；入口 gate、localStorage 记录和后续 `GamePhase` 分流由 `App.vue` 负责
