import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'

export default [
    {
        ignores: ['dist/**'],
    },
    js.configs.recommended,
    ...pluginVue.configs['flat/recommended'],
    {
        files: ['*.vue', '**/*.vue', '**/*.js', '**/*.jsx', '**/*.cjs', '**/*.mjs'],
        rules: {
            'vue/multi-word-component-names': 'off',
            'no-console': process.env.NODE_ENV === 'production' ? 'warn' : 'off',
            'no-unused-vars': 'warn', // 改为警告，方便开发
        },
    },
    {
        languageOptions: {
            globals: {
                // 原生浏览器全局变量
                window: 'readonly',
                document: 'readonly',
                navigator: 'readonly',
                localStorage: 'readonly',
                sessionStorage: 'readonly',
                fetch: 'readonly',
                console: 'readonly',
                setTimeout: 'readonly',
                setInterval: 'readonly',
                clearTimeout: 'readonly',
                clearInterval: 'readonly',
                WebSocket: 'readonly',
                alert: 'readonly',
                confirm: 'readonly',
                performance: 'readonly',
                requestAnimationFrame: 'readonly',
                cancelAnimationFrame: 'readonly',
                MutationObserver: 'readonly',
                process: 'readonly',
                // Vitest globals
                describe: 'readonly',
                it: 'readonly',
                expect: 'readonly',
                beforeEach: 'readonly',
                afterEach: 'readonly',
                beforeAll: 'readonly',
                afterAll: 'readonly',
                vi: 'readonly'
            }
        }
    }
]
