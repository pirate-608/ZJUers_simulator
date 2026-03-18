# Vue 3 (JavaScript) 至 TypeScript 渐进式迁移技术文档

本文档旨在为 `zjus-frontend` 项目提供一套安全、稳健的 TypeScript (TS) 迁移方案。

## 1. 迁移目标与收益

### 核心价值
- **前后端类型全链路对齐**：通过与后端 FastAPI (Pydantic) 模型保持一致的 Interface 定义，前端可以实时感知数据结构的变化，彻底消除“后端改字段，前端碎一地”的痛点。
- **重构信心**：在修改核心逻辑（如游戏引擎状态流转）时，TS 的静态检查能瞬间指出受影响的组件。
- **IDE 智能补齐**：大幅提升组件 Props、Pinia Store 状态的开发体验。

---

## 2. 第一阶段：基础设施与基座搭建

### 安全引入依赖
执行以下命令安装核心依赖，而不改动现有业务代码：
```bash
npm install -D typescript vue-tsc @vue/tsconfig
```

### 基础配置文件 `tsconfig.json`
在项目根目录创建此文件。关键在于开启 `allowJs` 和 `checkJs: false`，确保 TS 编译器对现有 JS 文件保持宽容。

```json
{
  "extends": "@vue/tsconfig/tsconfig.dom.json",
  "compilerOptions": {
    "target": "ESNext",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "jsx": "preserve",
    "sourceMap": true,
    "resolveJsonModule": true,
    "esModuleInterop": true,
    "lib": ["ESNext", "DOM"],
    "skipLibCheck": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    },
    // 关键配置：允许处理现有 JS
    "allowJs": true,
    "checkJs": false,
    "noEmit": true
  },
  "include": ["src/**/*.ts", "src/**/*.d.ts", "src/**/*.tsx", "src/**/*.vue"],
  "exclude": ["node_modules", "dist"]
}
```

---

## 3. 第二阶段：分层迁移策略 (Action Plan)

### Level 1: 逻辑层 (Types Definition)

**Before (JS):**
```javascript
// src/api/game.js
export const fetchStats = async () => {
    const res = await fetch('/api/stats');
    return res.json(); // 返回值不透明
};
```

**After (TS):**
在 `src/types/game.ts` 中根据后端 Pydantic 模型定义接口：
```typescript
export interface PlayerStats {
    iq: number;
    eq: number;
    gpa: string;
    energy: number;
    sanity: number;
    efficiency: number;
}

export const fetchStats = async (): Promise<PlayerStats> => {
    const res = await fetch('/api/stats');
    return res.json();
};
```

### Level 2: 状态与测试层

**Before (JS Vitest):**
```javascript
it('updates energy', () => {
    const store = useGameStore();
    store.updateEnergy(10);
});
```

**After (TS Vitest):**
利用 TS 类型强力约束测试数据：
```typescript
import { useGameStore } from '@/stores/gameStore';

it('updates energy', () => {
    const store = useGameStore();
    // 如果 updateEnergy 期待 number 却传了 string，TS 会立即报错
    store.updateEnergy(10); 
});
```

### Level 3: Vue 组件层

**Before (JS):**
```vue
<script setup>
const props = defineProps(['user']);
const energy = ref(100);
</script>
```

**After (TS):**
```vue
<script setup lang="ts">
import { ref } from 'vue';
import type { PlayerStats } from '@/types/game';

// 使用宏定义类型
const props = defineProps<{
  user: { name: string; id: number }
}>();

// 为 Ref 指定类型
const energy = ref<number>(100);
</script>
```

---

## 4. 常见避坑指南 (Troubleshooting)

### 3 个高频报错与对策
1.  **"Cannot find module '@/xxx' or its corresponding type declarations."**
    - **原因**：TS 无法识别 Vite 的路径别名。
    - **对策**：确保 `tsconfig.json` 中的 `compilerOptions.paths` 与 `vite.config.js` 中的 `resolve.alias` 完全同步。
2.  **"Property 'xxx' does not exist on type 'never'."**
    - **原因**：初始化变量（如 `const list = ref([])`）时未定义泛型，TS 默认为空数组且不可变更。
    - **对策**：显式声明为 `ref<Item[]>( [])`。
3.  **"Object is possibly 'null' or 'undefined'."**
    - **原因**：严格模式下的空值检查。
    - **对策**：使用可选链 `?.` 或非空断言 `!`（慎用）。

### 关于 `any` 的团队规范
> [!IMPORTANT]
> - **严禁**：在业务逻辑字段、API 返回值定义中使用 `any`。
> - **容忍**：在迁移现有陈旧复杂的 JS 方法、第三方包缺失声明文件时，短期允许使用 `any` 作为过渡。
> - **强制标记**：所有使用的 `any` 必须带有 `// TODO: [TS] fix any` 标记。

---

## 5. Agent 技能链调整预案 (CI Integration)

为了将 TS 检查纳入审查流程，我们需要对 `Smart Full-Stack Code Review Skill` 的指令进行以下微调：

1.  **新增检查命令**：在流水线中增加执行 `vue-tsc --noEmit`。这可以捕捉到 ESLint 无法发现的组件间 Props 类型不匹配。
2.  **状态机检查**：
    - 旧命令：`npm run lint`
    - 新命令：`npm run lint && npm run type-check` (对应 package.json 中 `"type-check": "vue-tsc --noEmit"`)
3.  **阈值设定**：在迁移初期，允许 type-check 存在一定数量的错误（设置 `--max-warnings` 或忽略特定目录），防止因为个别类型报错阻塞整个 CI。
