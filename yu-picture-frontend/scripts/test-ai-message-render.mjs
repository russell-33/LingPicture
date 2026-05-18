import assert from 'node:assert/strict'
import { mkdtemp, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'
import { build } from 'esbuild'

const tempDir = await mkdtemp(join(tmpdir(), 'ai-render-'))
const outfile = join(tempDir, 'aiMessageRender.mjs')

await build({
  entryPoints: [new URL('../src/utils/aiMessageRender.ts', import.meta.url).pathname],
  outfile,
  bundle: true,
  platform: 'node',
  format: 'esm',
  logLevel: 'silent',
})

const { renderAiMessageContent, MAX_AI_THUMBNAILS } = await import(pathToFileURL(outfile).href)

const lines = []
for (let i = 1; i <= 9; i += 1) {
  lines.push(`${i}. ![赛车${i}](https://example.com/car-${i}.webp)  ID: ${i}  [查看详情](/picture/${i})`)
}

const html = renderAiMessageContent(lines.join('\n'))
const imageCount = (html.match(/<img /g) || []).length

assert.equal(MAX_AI_THUMBNAILS, 7)
assert.equal(imageCount, 7)
assert.match(html, /赛车8/)
assert.match(html, /赛车9/)
assert.match(html, /\/picture\/8/)
assert.match(html, /\/picture\/9/)
assert.doesNotMatch(html, /car-8\.webp[^<]*<img/)

await writeFile(join(tempDir, 'result.html'), html)
