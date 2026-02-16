# 前端迁移方案（从纯静态到 React/Vue 架构）

## 目标
- 将当前多页静态 + 原生 JS 的交互迁移到现代前端栈（建议：Vite + React 或 Vite + Vue + Pinia）。
- 用组件化、状态管理和类型化提升可维护性、可测试性，并减少 DOM 直接操作。
- 渐进式替换，保持业务可用，避免一次性重写带来的风险。

## 总体思路（渐进式）
1) **抽象逻辑，解耦视图**：先把现有逻辑（WebSocket 管理、事件分发、gameState、配置、存档、LLM、计时器等）抽到独立 TS 模块，保证纯函数/少依赖 DOM。
2) **新前端项目搭建**：用 Vite 初始化 React/Vue 项目，引入 UI 体系（Ant Design/MUI/Tailwind 或 Element Plus），配置环境变量（API/WS 基址）、构建产物输出到 `static/` 或独立前端容器。
3) **页面渐进接管**：
   - 先接管登录/考试页（最少依赖），验证 API 调用、表单、模态逻辑。
   - 再接管 Dashboard 的只读部分（状态面板、日志、钉钉列表），保持与现有 WS 事件对齐。
   - 最后接管可交互部分（课程策略切换、休闲按钮、暂停/速度控制、计时器），完成全迁移后下线旧模板/JS。
4) **双轨运行与验证**：在切换阶段保留旧入口，提供新入口做 A/B 测试或内部预览；稳定后将 nginx/入口指向新构建。

## 技术选型建议
- **构建**：Vite（快速开发、内置 HMR）。
- **框架**：React + Zustand/Redux Toolkit 或 Vue 3 + Pinia。
- **语言**: TypeScript 全面启用。
- **UI**：根据审美选择 Ant Design/MUI（React）或 Element Plus（Vue），或 Tailwind 辅助布局。
- **路由**：React Router / Vue Router；至少包含登录/考试、Dashboard。
- **请求与 WS**：fetch/axios + 原生 WebSocket 封装；可用自定义 hook/composable 统一管理连接、重连、事件分发。

## 状态与数据流规划
- **全局 store**：
  - 用户/认证：token、用户名、专业、学期。
  - 游戏状态：stats、courses、courseStates、paused、speed、relaxCooldowns。
  - UI 状态：模态、toast、未读数（钉钉）、日志列表。
  - 配置：服务端配置、balance 数据、环境变量（API/WS）。
- **事件处理**：
  - WS 消息 → reducer/action，更新 store；组件订阅 store 自动渲染。
  - 暂停/恢复：直接更新 `paused`，组件自动禁用按钮/计时器。
  - 日志/消息：列表追加，支持虚拟滚动避免卡顿。

## 组件拆分（示例）
- 布局：导航栏、侧栏/主面板、底部操作区。
- 仪表：状态条（精力/心态/压力/GPA）、效率提示。
- 课程列表：课程卡片、策略切换按钮、状态动画。
- 休闲区：动作按钮（显示数值效果、冷却、暂停禁用）。
- 日志 & 钉钉：Tab 切换，支持未读数和滚动。
- 模态：成绩单、随机事件、Game Over、退出确认、LLM 授权。

## 路径与目录建议
- `src/`：组件、pages、hooks/composables、store、services（ws/api）、types。
- `src/services/ws.ts`：WS 连接与重连、心跳、消息分发。
- `src/store/game.ts`：核心游戏状态（stats/courses/paused/...）。
- `src/store/ui.ts`：UI 辅助状态（未读、模态开关）。
- `src/types/`：消息、课程、用户、LLM 配置、事件等类型定义（最好与后端共享 schema）。
- `src/config.ts`：读取 `import.meta.env`，生成 API/WS 基址。

## 迁移步骤（时间线示例）
- **第 1 周**：
  - 抽取现有 JS 逻辑为独立 TS 模块（无需框架），补类型。
  - 建立新项目骨架（Vite + TS + 选定 UI 库），接入 env 配置。
- **第 2 周**：
  - 完成登录/考试页移植；打通 API/LLM 同意流程；打包产物可访问。
  - 接入基础 store 和 WS 封装，能收发消息、更新状态原型。
- **第 3-4 周**：
  - 移植 Dashboard 只读组件（仪表、日志、钉钉）；实现暂停/速度控制。
  - 移植课程/休闲交互、计时器与动画；完善未读提示和模态。
- **第 5 周**：
  - 灰度切流，A/B 验证；性能与 UX 调优；清理旧静态页面。

## 注意事项与提醒
- **缓存与部署**：构建产物文件名哈希，防止 CDN/浏览器缓存旧脚本；nginx/Cloudflare 配置静态缓存与 Gzip/Brotli。
- **安全与存储**：token 仍用 localStorage；LLM key 仅 sessionStorage；首条 WS 消息携带凭证与自定义 LLM。
- **类型与测试**：为事件处理和 reducer 写单测；E2E（Playwright/Cypress）覆盖考试提交、暂停/继续、休闲操作、WS 重连。
- **性能**：日志/消息列表用虚拟滚动，避免长列表卡顿；渲染频繁区域做拆分和 memo。
- **回退方案**：迁移过程中保留旧入口，问题时可快速切回旧版。

## 成功验收标准
- 新前端可完整跑通：登录/考试→录取→进入游戏→暂停/继续→休闲与课程交互→学期总结→毕业。
- 无关键交互回退到 DOM 操作；主要逻辑由 store/组件驱动。
- 构建产物部署在现有 nginx/Cloudflare 下，首屏加载与交互性能不低于当前版本。
