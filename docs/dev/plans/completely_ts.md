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
| `zjus-frontend/src/types/websocket.ts` | Added `WsClientAction` action variants, `RelaxTarget`, and `isWsMessage` guard |
| `zjus-frontend/src/types/api.generated.ts` | Generated OpenAPI schema types; do not hand-edit |
| `zjus-frontend/src/api/client.ts` | Hand-written thin HTTP client wrapper around generated schema types |
| `zjus-frontend/src/composables/useGameWebSocket.ts` | `send()` upgraded from `unknown` to typed WebSocket actions |
| `zjus-frontend/src/types/modal.ts` | Modal payloads and DingTalk message fields are typed |
| `zjus-frontend/package.json` | Type-check, API generation, test, and Vite build scripts |

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
| LoginView | typed invite-code auth form and LLM safety confirmation state |
| SaveSelect | `SaveSummary[]` from generated OpenAPI schema |
| CharacterCreate | `MajorOption[]`, typed stat allocation and init payload |

## Config Fixes

| File | Fix |
|---|---|
| `zjus-frontend/eslint.config.js` | TypeScript-aware lint config for `.ts` and `.vue` files |
| `zjus-frontend/vitest.config.js` | `@` resolve alias matching `vite.config.js` |
