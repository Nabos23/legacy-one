// Produces the CommonJS entry from the ESM build — the module is a single
// self-contained file, so a light transform beats adding a bundler dependency.
import { readFileSync, writeFileSync } from 'node:fs'

const esm = readFileSync(new URL('./dist/index.js', import.meta.url), 'utf8')
const cjs = esm
  .replace(/export async function (\w+)/g, 'async function $1')
  .replace(/export function (\w+)/g, 'function $1')
  + '\nmodule.exports = { initWidget, destroyWidget };\n'
writeFileSync(new URL('./dist/index.cjs', import.meta.url), cjs)
console.log('dist/index.cjs written')
