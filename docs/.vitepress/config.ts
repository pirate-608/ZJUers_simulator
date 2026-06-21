/**
 * VitePress configuration for the documentation site.
 *
 * The docs theme imports selected frontend components for the homepage demo, so
 * this config keeps aliases and dependency dedupe aligned with the app.
 */
import { defineConfig } from 'vitepress'
import { fileURLToPath, URL } from 'node:url'

const fromRoot = (path: string) => fileURLToPath(new URL(`../../${path}`, import.meta.url))
const fromDocs = (path: string) => fileURLToPath(new URL(`../${path}`, import.meta.url))

const worldCourseItems = [
  { text: '总览', link: '/world/courses' },
  { text: 'TIER1 / 计算机科学与技术', link: '/world/courses/TIER1/CS' },
  { text: 'TIER1 / 人工智能', link: '/world/courses/TIER1/AI' },
  { text: 'TIER1 / 软件工程', link: '/world/courses/TIER1/SE' },
  { text: 'TIER1 / 临床医学（5+3）', link: '/world/courses/TIER1/MD' },
  { text: 'TIER1 / 机器人工程', link: '/world/courses/TIER1/RE' },
  { text: 'TIER2 / 电气工程及其自动化', link: '/world/courses/TIER2/EEA' },
  { text: 'TIER2 / 光电信息科学与工程', link: '/world/courses/TIER2/OE' },
  { text: 'TIER2 / 自动化（控制）', link: '/world/courses/TIER2/AUT' },
  { text: 'TIER2 / 微电子科学与工程', link: '/world/courses/TIER2/MISE' },
  { text: 'TIER2 / 信息安全', link: '/world/courses/TIER2/IS' },
  { text: 'TIER2 / 数学与应用数学', link: '/world/courses/TIER2/MAM' },
  { text: 'TIER2 / 电子信息工程', link: '/world/courses/TIER2/EIE' },
  { text: 'TIER2 / 电子科学与技术', link: '/world/courses/TIER2/EST' },
  { text: 'TIER2 / 数字金融', link: '/world/courses/TIER2/DF' },
  { text: 'TIER3 / 机械工程', link: '/world/courses/TIER3/ME' },
  { text: 'TIER3 / 物理学', link: '/world/courses/TIER3/PHY' },
  { text: 'TIER3 / 能源与环境系统工程', link: '/world/courses/TIER3/NEE' },
  { text: 'TIER3 / 口腔医学', link: '/world/courses/TIER3/DEN' },
  { text: 'TIER3 / 飞行器设计与工程', link: '/world/courses/TIER3/ADE' },
  { text: 'TIER3 / 建筑学', link: '/world/courses/TIER3/ARCH' },
  { text: 'TIER3 / 化学工程与工艺', link: '/world/courses/TIER3/CHE' },
  { text: 'TIER3 / 材料科学与工程', link: '/world/courses/TIER3/MSE' },
  { text: 'TIER3 / 化学', link: '/world/courses/TIER3/CHEM' },
  { text: 'TIER3 / 经济学', link: '/world/courses/TIER3/ECON' },
  { text: 'TIER3 / 法学', link: '/world/courses/TIER3/LAW' },
  { text: 'TIER3 / 药学', link: '/world/courses/TIER3/PHAR' },
  { text: 'TIER3 / 生物医学工程', link: '/world/courses/TIER3/BME' },
  { text: 'TIER3 / 工商管理', link: '/world/courses/TIER3/BA' },
  { text: 'TIER4 / 汉语言文学', link: '/world/courses/TIER4/CL' },
  { text: 'TIER4 / 历史学', link: '/world/courses/TIER4/HIS' },
  { text: 'TIER4 / 哲学', link: '/world/courses/TIER4/PHI' },
  { text: 'TIER4 / 新闻学', link: '/world/courses/TIER4/JOUR' },
  { text: 'TIER4 / 英语', link: '/world/courses/TIER4/ENG' },
  { text: 'TIER4 / 农学', link: '/world/courses/TIER4/AGR' },
  { text: 'TIER4 / 茶学', link: '/world/courses/TIER4/TEA' },
  { text: 'TIER4 / 动物科学', link: '/world/courses/TIER4/AS' },
  { text: 'TIER4 / 环境科学', link: '/world/courses/TIER4/ENV' },
  { text: 'TIER4 / 心理学', link: '/world/courses/TIER4/PSY' },
  { text: 'TIER4 / 社会学', link: '/world/courses/TIER4/SOC' },
  { text: 'TIER4 / 地质学', link: '/world/courses/TIER4/GEO' },
]

export default defineConfig({
  title: '折姜大学学生手册',
  description: 'ZJUers Simulator 的玩家手册与开发手册',
  lang: 'zh-CN',
  cleanUrls: true,
  lastUpdated: true,
  outDir: '.vitepress/dist',
  head: [
    ['link', { rel: 'icon', href: '/assets/images/favicon.ico' }],
    ['meta', { name: 'theme-color', content: '#020817' }],
  ],
  markdown: {
    theme: {
      light: 'github-light',
      dark: 'github-dark',
    },
    config(md) {
      const defaultFence = md.renderer.rules.fence
      md.renderer.rules.fence = (tokens, idx, options, env, self) => {
        const token = tokens[idx]
        if (token.info.trim() === 'mermaid') {
          const code = encodeURIComponent(token.content)
          return `<MermaidDiagram code="${code}" />`
        }
        return defaultFence
          ? defaultFence(tokens, idx, options, env, self)
          : self.renderToken(tokens, idx, options)
      }
    },
  },
  themeConfig: {
    logo: '/assets/images/logo.svg',
    siteTitle: 'ZJUers Simulator',
    search: { provider: 'local' },
    outline: {
      level: [2, 3],
      label: '本页目录',
    },
    nav: [
      { text: '首页', link: '/' },
      { text: '用户指南', link: '/user/online_guide' },
      { text: '游戏设定', link: '/world/majors' },
      { text: '开发指南', link: '/dev/setup' },
      { text: '开始游戏', link: 'https://67656.fun' },
    ],
    sidebar: {
      '/user/': [
        {
          text: '用户指南',
          items: [
            { text: '折姜大学招生减章', link: '/user/notice' },
            { text: '折姜大学校规', link: '/user/rules' },
            { text: '在线游戏', link: '/user/online_guide' },
            { text: '钉钉私聊', link: '/user/dingtalk' },
            { text: '内容生成模式', link: '/user/content_modes' },
            { text: '本地部署', link: '/user/local_deploy' },
            { text: '原生本地部署', link: '/user/local_deploy_bare' },
            { text: '模型配置', link: '/user/models' },
          ],
        },
      ],
      '/world/': [
        {
          text: '游戏设定',
          items: [
            { text: '角色', link: '/world/characters' },
            { text: '成就', link: '/world/achievements' },
            { text: '数值', link: '/world/game_balance' },
            { text: '属性定义', link: '/world/stat_definitions' },
            { text: '关键词', link: '/world/keywords' },
            { text: '专业', link: '/world/majors' },
          ],
        },
        { text: '培养方案', collapsed: true, items: worldCourseItems },
      ],
      '/dev/': [
        {
          text: '开发人员指南',
          items: [
            { text: '开发环境搭建', link: '/dev/setup' },
            { text: 'API 文档', link: '/dev/api' },
            { text: '接手研究报告', link: '/dev/handoff' },
            { text: '测试', link: '/dev/test' },
            { text: '开发者常见问题', link: '/dev/faq_dev' },
          ],
        },
        {
          text: '框架说明',
          collapsed: true,
          items: [
            { text: '后端', link: '/dev/framework/backend_framework' },
            { text: '前端', link: '/dev/framework/frontend_framework' },
          ],
        },
        {
          text: '开发计划',
          collapsed: true,
          items: [
            { text: '总览', link: '/dev/plans/' },
            { text: 'TypeScript 迁移', link: '/dev/plans/migrate_js_to_ts' },
            { text: 'Vue 组件迁移至 TS', link: '/dev/plans/completely_ts' },
            { text: 'UI 设计优化', link: '/dev/plans/ui_design' },
            { text: '2C2G 生产资源优化', link: '/dev/plans/production-resource-optimization' },
          ],
        },
      ],
      '/about/': [
        {
          text: '关于',
          items: [
            { text: '更新日志', link: '/about/release-notes' },
            { text: '许可', link: '/about/LICENSE' },
            { text: '贡献', link: '/about/contributing' },
          ],
        },
      ],
    },
    socialLinks: [
      { icon: 'github', link: 'https://github.com/pirate-608/ZJUers_simulator' },
    ],
    footer: {
      message: 'ZJUers Simulator 仅供娱乐，与真实教学、考试、行政系统无关。',
      copyright: '浙ICP备2026007685号 · 浙公网安备33010602014394号',
    },
  },
  vite: {
    resolve: {
      alias: {
        '@': fromRoot('zjus-frontend/src'),
      },
      dedupe: ['vue', 'pinia'],
    },
    build: {
      chunkSizeWarningLimit: 700,
    },
    server: {
      fs: {
        allow: [fromRoot(''), fromDocs('')],
      },
    },
  },
})
