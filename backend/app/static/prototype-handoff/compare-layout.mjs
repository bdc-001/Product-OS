import fs from 'node:fs/promises';
const [referencePath, actualPath] = process.argv.slice(2);
if (!referencePath || !actualPath) throw Error('Usage: node handoff/compare-layout.mjs reference.json production.json');
const reference = JSON.parse(await fs.readFile(referencePath, 'utf8'));
const actual = JSON.parse(await fs.readFile(actualPath, 'utf8'));
const failures = [];
for (const key of ['viewport', 'devicePixelRatio', 'scroll', 'fonts']) {
  if (JSON.stringify(reference[key]) !== JSON.stringify(actual[key])) failures.push(`Different comparison condition: ${key}`);
}
if (!Object.keys(reference.elements || {}).length) failures.push('Reference has no measured landmarks');
for (const [key, expected] of Object.entries(reference.elements || {})) {
  const received = actual.elements?.[key];
  if (!received) { failures.push(`Missing landmark: ${key}`); continue; }
  for (const dim of ['x', 'y', 'width', 'height']) {
    if (!Number.isFinite(expected.rect?.[dim]) || !Number.isFinite(received.rect?.[dim]) || Math.abs(expected.rect[dim] - received.rect[dim]) > 1)
      failures.push(`${key}.${dim}: expected ${expected.rect?.[dim]}, got ${received.rect?.[dim]}`);
  }
  for (const [prop, value] of Object.entries(expected.style || {})) {
    if (value !== received.style?.[prop]) failures.push(`${key}.${prop}: expected ${value}, got ${received.style?.[prop]}`);
  }
}
console.log(failures.length ? failures.join('\n') : 'Geometry and captured styles match. Screenshot and interaction checks still required.');
process.exitCode = failures.length ? 1 : 0;
