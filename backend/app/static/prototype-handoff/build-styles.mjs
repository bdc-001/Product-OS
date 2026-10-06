import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';

const cwd = process.cwd();
const require = createRequire(path.join(cwd, 'package.json'));
const { compile } = await import(pathToFileURL(require.resolve('@tailwindcss/node')).href);
const { Scanner } = await import(pathToFileURL(require.resolve('@tailwindcss/oxide')).href);
const { default: postcss } = await import(pathToFileURL(require.resolve('postcss')).href);
const manifest = JSON.parse(await fs.readFile('handoff/manifest.json', 'utf8'));
const rootPx = Number(process.argv.find(a => a.startsWith('--root-px='))?.split('=')[1] || manifest.reference_root_px);
if (!Number.isFinite(rootPx) || rootPx < 8 || rootPx > 32) throw Error('Invalid reference root size');
if (!/^[0-9]+$/.test(String(manifest.prototype_id))) throw Error('Invalid prototype id');
// Refuse to label stale CSS as matching the exported source.
for (const [name, hash] of Object.entries(manifest.files)) {
  if (name === 'PORTING.md') continue; // replaced by this handoff's authoritative guide
  const resolved = path.resolve(cwd, name);
  if (!resolved.startsWith(cwd + path.sep)) throw Error('Invalid manifest path');
  const actual = createHash('sha256').update(await fs.readFile(resolved)).digest('hex');
  if (actual !== hash) throw Error(`Source changed: ${name}. Re-export the prototype before compiling.`);
}
const input = path.resolve(cwd, await fs.stat(path.join(cwd, 'src/index.css')).then(() => 'src/index.css', () => 'src/styles.css'));
const compiler = await compile(await fs.readFile(input, 'utf8'), { base: path.dirname(input), from: input, onDependency() {} });
const scanner = new Scanner({ sources: [...compiler.sources, { base: cwd, pattern: 'src/**/*.{js,jsx,ts,tsx,html}', negated: false }] });
const css = compiler.build(scanner.scan());
await fs.writeFile('handoff/reference.css', css);
const scope = `[data-prototype-ui="${manifest.prototype_id}"]`;
const prefix = `prototype-${manifest.prototype_id}-`;
const ast = postcss.parse(css.replaceAll('--tw-', `--${prefix}tw-`));
// Normal production Tailwind 3 utilities are unlayered. Leaving Tailwind 4 in layers
// would put every prototype utility below them in the cascade, regardless of import order.
ast.walkAtRules('layer', rule => { if (rule.nodes) rule.replaceWith(...rule.nodes); else rule.remove(); });
const keyframes = new Map();
ast.walkAtRules(/keyframes$/, rule => { const old = rule.params; keyframes.set(old, prefix + old); rule.params = prefix + old; });
const remToPx = value => value.replace(/url\([^)]*\)|"[^"]*"|'[^']*'|(-?(?:\d*\.)?\d+)rem\b/g,
  (match, number) => number == null ? match : `${Math.round(Number(number) * rootPx * 10000) / 10000}px`);
ast.walkDecls(decl => {
  decl.value = remToPx(decl.value);
  if (/animation|--animate-/.test(decl.prop)) for (const [old, next] of keyframes) {
    decl.value = decl.value.replace(new RegExp(`\\b${old.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'g'), next);
  }
});
ast.walkAtRules(/^(media|container)$/, rule => { rule.params = remToPx(rule.params); });
ast.walkRules(rule => {
  let parent = rule.parent;
  while (parent && parent.type !== 'root') {
    if (parent.type === 'rule' || (parent.type === 'atrule' && /keyframes$/.test(parent.name))) return;
    parent = parent.parent;
  }
  rule.selectors = rule.selectors.flatMap(selector => {
    const s = selector.trim();
    if ([':root', ':host', 'html', 'body'].includes(s)) return [scope];
    if (s === '.dark') return [`${scope}.dark`, `.dark ${scope}`];
    if (s === '*') return [scope, `${scope} *`];
    if (/^html\b|^body\b|^:root\b|^:host\b/.test(s)) return [s.replace(/^html\b|^body\b|^:root\b|^:host\b/, scope)];
    return [`${scope} ${s}`];
  });
});
ast.append(postcss.rule({ selector: scope, nodes: [postcss.decl({ prop: 'font-size', value: `${rootPx}px` })] }));
await fs.writeFile('handoff/production-scoped.css', `/* Source ${manifest.source_fingerprint}; reference root ${rootPx}px. */\n${ast}`);
await fs.writeFile('handoff/styles-build.json', JSON.stringify({ source_fingerprint: manifest.source_fingerprint, reference_root_px: rootPx,
  bytes: Buffer.byteLength(css), verification: 'compiled; browser comparison still required' }, null, 2));
console.log('Built reference.css and production-scoped.css. Compare rendered layouts before production acceptance.');
