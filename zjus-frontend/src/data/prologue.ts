const baseUrl = import.meta.env.BASE_URL || '/'
const imageUrl = (name: string) => `${baseUrl}images/${name}`

export const PROLOGUE_SEEN_STORAGE_KEY = 'zjus_prologue_seen_v1'

export const PROLOGUE_LINES = [
  '我被毕业卡住了...',
  '晚上喝了杯冰美式，结果是又失眠了',
  '早上顶着黑眼圈打开窗户，紫金港的阳光灿烂',
  '导师上午打来电话，“今天去实验室把上次的数据再验证一遍”',
  '那个被我反复修改的图表，怎么看都像一个笑话。',
  '钉钉里传来消息，导师发了新论文，要举办庆功宴。',
  '傍晚，我从实验室出来，散步到了启真湖边。',
  '湖边有人在喊“毕业快乐”，笑声被晚风吹散...',
  '他们的笑容被记录在照片上，“明天会更好”',
  '我的名字从未出现在论文上，看不到明天...',
  '天渐渐黑了，启真湖边的人渐渐散去...',
  '今晚的月亮格外明亮，映照在启真湖面，皎洁动人。',
  '我俯身凝视着湖面，看到了自己的脸。',
  '我不禁想，在湖里是否有另一个世界？',
  '或许在那里，明天会更好？',
  '我纵身一跃...',
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
