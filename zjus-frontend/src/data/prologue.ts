/**
 * Static first-visit prologue copy and image mapping.
 *
 * The text is intentionally bundled in the frontend so the pre-login scene can
 * play before any backend/API/WebSocket dependency is touched.
 */
const baseUrl = import.meta.env.BASE_URL || '/'
const imageUrl = (name: string) => `${baseUrl}images/${name}`

export const PROLOGUE_SEEN_STORAGE_KEY = 'zjus_prologue_seen_v1'

export const PROLOGUE_LINES = [
  '谨以此游戏献给每一位灿若星辰的浙大人。',
  '这是一个关于你，我，和他们的故事。',
  '我延毕第三年的清晨，在心悸中打开窗户，紫金港的阳光灿烂。',
  '导师上午打来电话，“今天去实验室把上次的数据再验证一遍”',
  '这份杂活我已经干了两年了，心里有些烦躁，但还是答应了。',
  '钉钉里传来消息，导师发了新论文，要举办庆功宴。',
  '公众号里学校发布了新推文，标题是“又一篇文章被Nature录用！”',
  '傍晚，我从实验室出来，散步到了启真湖边。',
  '湖边有人在喊“毕业快乐”，笑声被晚风吹散...',
  '他们的笑容被记录在照片上，配文“明天会更好”',
  '而我，我却看不到明天...',
  '天渐渐黑了，启真湖边的人渐渐散去...',
  '今晚的月亮格外明亮，映照在启真湖面，皎洁动人。',
  '我俯身凝视着湖面，看到了自己的脸。',
  '我不禁想，在湖里是否有另一个世界？',
  '或许在那里，明天会更好？',
  '我纵身一跃，漆黑的湖水将我吞没...',
  '......',
  '醒过来时，阳光亮得让我睁不开眼。',
  '十八岁的我背着包，走到了那扇门前。',
  '“求是园欢迎您！”',
] as const

export type PrologueScene = {
  image: string
  tone: 'night' | 'morning' | 'sunset' | 'lake' | 'threshold'
}

const PROLOGUE_SCENES: Array<{ from: number; scene: PrologueScene }> = [
  { from: 0, scene: { image: imageUrl('zjg_night.jpeg'), tone: 'night' } },
  { from: 2, scene: { image: imageUrl('zjg_autumn.jpg'), tone: 'morning' } },
  { from: 6, scene: { image: imageUrl('qizhen_lake.jpg'), tone: 'lake' } },
  { from: 8, scene: { image: imageUrl('sunset.webp'), tone: 'sunset' } },
  { from: 9, scene: { image: imageUrl('qizhen_lake.jpg'), tone: 'lake' } },
  { from: 17, scene: { image: imageUrl('qiushimen.webp'), tone: 'threshold' } },
]

/**
 * Return the most recent scene mapping for the active line index.
 */
export const getPrologueScene = (lineIndex: number): PrologueScene => {
  const matched = PROLOGUE_SCENES
    .slice()
    .reverse()
    .find(({ from }) => lineIndex >= from)

  return matched?.scene || { image: imageUrl('zjg_night.jpeg'), tone: 'night' }
}

export const PROLOGUE_IMAGES = Array.from(
  new Set(PROLOGUE_SCENES.map(({ scene }) => scene.image)),
)
