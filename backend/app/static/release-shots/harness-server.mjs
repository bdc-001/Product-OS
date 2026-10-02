// Serves one real product component on its own page so Playwright can screenshot it.
// Uses the product checkout's own Vite, React plugin, Tailwind and PostCSS config.
// Nothing is written inside that checkout: the dep cache lives under --cache.
//
// node harness-server.mjs --ui <frontend-build/static> --cache <dir> --port <n>
// Prints "READY http://127.0.0.1:<n>" once the dep optimizer is warm.
import path from 'node:path'
import fs from 'node:fs'
import { createRequire } from 'node:module'
import { pathToFileURL } from 'node:url'

const arg = (name, fallback = '') => {
  const i = process.argv.indexOf(name)
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback
}
const ui = path.resolve(arg('--ui'))
const cache = path.resolve(arg('--cache', path.join(process.cwd(), '.release-shots-vite')))
const port = Number(arg('--port', '5199'))
if (!fs.existsSync(path.join(ui, 'package.json'))) throw Error(`No package.json in ${ui}`)
process.chdir(ui) // tailwind.config content globs are relative to cwd
// Keep API calls same-origin so Playwright fixtures answer them; the checkout's .env may point at a real backend.
process.env.VITE_BACKEND_URL = ''

const require = createRequire(path.join(ui, 'package.json'))
const load = async (id) => import(pathToFileURL(require.resolve(id)).href)
const { createServer } = await load('vite')

const HTML = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link href="https://fonts.googleapis.com/css2?family=Figtree:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
      html, body { margin: 0; background: #ffffff; }
      #shot-stage { box-sizing: border-box; background: #f9fafb; }
      *, *::before, *::after { caret-color: transparent !important; }
    </style>
  </head>
  <body>
    <div id="shot-stage"><div id="shot-root"></div></div>
    <script type="module">import 'virtual:release-shot'</script>
  </body>
</html>`

// Mounts window.__RELEASE_SHOT__.module inside the requested providers.
const ENTRY = `
import React from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import '/src/index.css'

const spec = window.__RELEASE_SHOT__ || {}
const report = (state, detail = '') => { window.__SHOT_STATUS__ = { state, detail: String(detail).slice(0, 4000) } }
window.addEventListener('error', (e) => report('error', (e.error && e.error.stack) || e.message))
window.addEventListener('unhandledrejection', (e) => report('error', (e.reason && e.reason.stack) || e.reason))

class Boundary extends React.Component {
  constructor(props) { super(props); this.state = { failed: false } }
  static getDerivedStateFromError() { return { failed: true } }
  componentDidCatch(error) { report('error', (error && error.stack) || error) }
  render() { return this.state.failed ? null : this.props.children }
}

const pick = (mod, name) => (!name || name === 'default' ? mod.default : mod[name])

async function main() {
  const stage = document.getElementById('shot-stage')
  stage.style.width = (Number(spec.width) || 1200) + 'px'
  stage.style.padding = (spec.padding ?? 24) + 'px'
  if (spec.background) stage.style.background = spec.background
  const mod = await import(/* @vite-ignore */ spec.module)
  const Component = pick(mod, spec.export)
  if (!Component) throw new Error('No export ' + (spec.export || 'default') + ' in ' + spec.module)
  const props = { ...(spec.props || {}) }
  for (const name of spec.noop_props || []) props[name] = () => {}
  let tree = React.createElement(Component, props)
  for (const provider of [...(spec.providers || [])].reverse()) {
    const Provider = pick(await import(/* @vite-ignore */ provider.module), provider.export)
    if (!Provider) throw new Error('No provider ' + provider.export + ' in ' + provider.module)
    tree = React.createElement(Provider, provider.props || {}, tree)
  }
  if (spec.router !== false) {
    const route = React.createElement(Route, { path: spec.route_path || '/tenant/:tenantId/*', element: tree })
    tree = React.createElement(MemoryRouter, { initialEntries: [spec.route || '/tenant/acme-demo'] },
      React.createElement(Routes, null, route))
  }
  if (spec.redux !== false) {
    const [{ Provider }, { store }] = await Promise.all([import('react-redux'), import('/src/store/store')])
    tree = React.createElement(Provider, { store }, tree)
  }
  createRoot(document.getElementById('shot-root')).render(React.createElement(Boundary, null, tree))
  report('mounted')
}

main().catch((error) => report('error', (error && error.stack) || error))
`

const harness = () => ({
  name: 'release-shot-harness',
  resolveId(id) {
    if (id === 'virtual:release-shot') return '\0virtual:release-shot'
  },
  load(id) {
    if (id === '\0virtual:release-shot') return ENTRY
  },
  configureServer(server) {
    // Apps that derive the tenant from /tenant/<id>/... need the harness mounted there.
    server.middlewares.use(async (req, res, next) => {
      const url = req.url || ''
      if (!url.startsWith('/tenant/') || !(req.headers.accept || '').includes('text/html')) return next()
      try {
        const html = await server.transformIndexHtml(url, HTML)
        res.setHeader('Content-Type', 'text/html')
        res.end(html)
      } catch (error) {
        next(error)
      }
    })
  },
})

const inline = {
  root: ui,
  cacheDir: cache,
  logLevel: 'error',
  clearScreen: false,
  plugins: [harness()],
  server: { host: '127.0.0.1', port, strictPort: true, hmr: false, watch: null, fs: { strict: true, allow: [ui] } },
}

const configFile = path.join(ui, 'vite.config.js')
let server
try {
  server = await createServer({ ...inline, configFile: fs.existsSync(configFile) ? configFile : false })
} catch (error) {
  console.error('activate vite config failed; using React defaults:', error && error.message)
  const react = (await load('@vitejs/plugin-react')).default
  server = await createServer({ ...inline, configFile: false, plugins: [react(), harness()] })
}
await server.listen()
console.log(`READY http://127.0.0.1:${port}`)

const stop = async () => {
  await server.close().catch(() => {})
  process.exit(0)
}
process.on('SIGTERM', stop)
process.on('SIGINT', stop)
process.stdin.on('end', stop)
process.stdin.resume()
