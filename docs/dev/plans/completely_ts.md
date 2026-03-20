# Vue TypeScript Migration — Walkthrough

## ✅ Verification Results

| Check | Result |
|---|---|
| `vue-tsc --noEmit` | ✅ 0 errors |
| `npm run lint` | ✅ 0 errors |
| `npm test` | ✅ 1 passed |
| `npm run build` | ✅ 565ms, 55 modules |

## Phase 0: Type Alignment Infrastructure

| File | Change |
|---|---|
| [websocket.ts](file:///d:/projects/ZJUers_simulator/zjus-frontend/src/types/websocket.ts) | Added `WsClientAction` (15 action variants) + `RelaxTarget` + `isWsMessage` guard |
| [api.ts](file:///d:/projects/ZJUers_simulator/zjus-frontend/src/types/api.ts) | **[NEW]** 6 interfaces aligned with backend Pydantic models |
| [client.ts](file:///d:/projects/ZJUers_simulator/zjus-frontend/src/api/client.ts) | **[NEW]** Type-safe HTTP client (5 functions) |
| [useGameWebSocket.ts](file:///d:/projects/ZJUers_simulator/zjus-frontend/src/composables/useGameWebSocket.ts) | `send()` upgraded from `unknown` → `WsClientAction` |
| [modal.ts](file:///d:/projects/ZJUers_simulator/zjus-frontend/src/types/modal.ts) | `DingTalkMessage.role/content` → required fields |
| [package.json](file:///d:/projects/ZJUers_simulator/zjus-frontend/package.json) | Added `gen:api`, `openapi-typescript`, `@typescript-eslint/*` |

## Phases 1–3: Component Migration (12 / 12)

All components migrated to `<script setup lang="ts">`:

| Component | Key Types Added |
|---|---|
| TopNav | `defineEmits<WsClientAction>` |
| ExitConfirmModal | `defineEmits<WsClientAction>` |
| TranscriptModal | `TranscriptModalData` cast, `TranscriptModalCourseRow` lambda type |
| RandomEventModal | `RandomEventModalData` cast, `makeChoice(effects: unknown)` |
| EndScreen | `startTypewriter(text: string)` |
| HudBar | `safeNumber(val: unknown, defaultVal: number): number` |
| CourseList | `getProgressColor(progress: number)`, `changeStrategy(courseId: string, newState: number)` |
| MidPanel | `ref<HTMLDivElement \| null>`, `getRoleConfig(role: string)`, `setSpeed(speed: number)` |
| RightPanel | `animationFrameId: number \| null`, `sendRelax(activity: RelaxTarget)` |
| App | `handleEnterGame(token: string)` |
| LoginView | `ref<ExamQuestion[]>`, `ref<Record<number, string>>`, typed `viewState` union |
| AdmissionScreen | `ref<{username: string; major: string}>`, `defineEmits<{enter-game: [string]}>` |

## Config Fixes

| File | Fix |
|---|---|
| [eslint.config.js](file:///d:/projects/ZJUers_simulator/zjus-frontend/eslint.config.js) | Added `@typescript-eslint/parser` for `.ts` and `.vue` files |
| [vitest.config.js](file:///d:/projects/ZJUers_simulator/zjus-frontend/vitest.config.js) | Added `@` resolve alias matching vite.config |
