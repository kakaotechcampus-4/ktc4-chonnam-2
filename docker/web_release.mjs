// Public source identity only. Never read runtime configuration or .env files.
import { createHash } from 'node:crypto'
import { lstatSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join, relative } from 'node:path'

try {
  const [directory, revision] = process.argv.slice(2)
  if (!directory || !/^(local|[0-9a-f]{40})$/.test(revision)) throw new Error()
  writeFileSync(join(directory, 'version.json'), JSON.stringify({ revision }) + '\n')
  const files = {}
  function walk(dir) {
    for (const name of readdirSync(dir).sort()) {
      const path = join(dir, name)
      const info = lstatSync(path)
      if (info.isDirectory()) walk(path)
      else if (info.isFile()) {
        const key = relative(directory, path).replaceAll('\\', '/')
        if (key !== 'manifest.json') files[key] = createHash('sha256').update(readFileSync(path)).digest('hex')
      } else throw new Error()
    }
  }
  walk(directory)
  if (!files['index.html']) throw new Error()
  writeFileSync(join(directory, 'manifest.json'), JSON.stringify({ revision, files }) + '\n')
} catch {
  console.error('rt14-web: build identity failed')
  process.exitCode = 1
}
