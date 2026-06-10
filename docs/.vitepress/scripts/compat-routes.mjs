import { copyFileSync, mkdirSync, readdirSync, statSync } from 'node:fs'
import { dirname, join, relative, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const distRoot = fileURLToPath(new URL('../dist/', import.meta.url))

function walk(dir) {
  for (const entry of readdirSync(dir)) {
    const fullPath = join(dir, entry)
    const stat = statSync(fullPath)
    if (stat.isDirectory()) {
      walk(fullPath)
      continue
    }
    if (!entry.endsWith('.html') || entry === 'index.html' || entry === '404.html') continue

    const routePath = fullPath.slice(0, -'.html'.length)
    const indexPath = join(routePath, 'index.html')
    mkdirSync(dirname(indexPath), { recursive: true })
    mkdirSync(routePath, { recursive: true })
    copyFileSync(fullPath, indexPath)
    const displayPath = relative(distRoot, indexPath).split(sep).join('/')
    console.log(`compat route: /${displayPath}`)
  }
}

walk(distRoot)
