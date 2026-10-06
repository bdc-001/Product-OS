const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
const path = require('node:path');
const sandbox = { exports: {}, Promise };
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, '../lib/single-flight.ts'), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText, sandbox);
const { singleFlight } = sandbox.exports;

test('autosave and explicit save share the initial creation, then save later edits with its ID', async () => {
  const slot = { current: null };
  let finish, calls = [], id;
  const create = () => { calls.push(id); return new Promise(resolve => { finish = () => { id = 17; resolve(id); }; }); };
  const auto = singleFlight(slot, create);
  const explicit = singleFlight(slot, create);
  await Promise.resolve();
  assert.equal(auto, explicit);
  assert.deepEqual(calls, [undefined]);
  finish();
  assert.equal(await auto, 17);
  await singleFlight(slot, async () => { calls.push(id); return id; });
  assert.deepEqual(calls, [undefined, 17]);
});

test('a failed save can be retried without retaining the rejected request', async () => {
  const slot = { current: null };
  await assert.rejects(singleFlight(slot, async () => { throw new Error('Offline'); }), /Offline/);
  assert.equal(slot.current, null);
  assert.equal(await singleFlight(slot, async () => 18), 18);
});
