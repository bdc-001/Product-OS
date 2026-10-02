const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
function client() {
  let calls = 0;
  let fail = false;
  const session = { clerkEnabled: false, signInUrl: () => '/sign-in' };
  const sandbox = { exports: {}, require: (name) => (name === '@/lib/session' ? session : require(name)), fetch: async () => {
    calls++;
    return { ok: !fail, status: fail ? 503 : 200, statusText: 'Unavailable',
      text: async () => 'Internal server error', json: async () => ({ revision: calls }) };
  }};
  const source = fs.readFileSync(require('node:path').join(__dirname, '../lib/http.ts'), 'utf8');
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText, sandbox);
  return { api: sandbox.exports, calls: () => calls, fail: () => { fail = true; } };
}
test('live campaign review bypasses cached data and updates the workspace cache', async () => {
  const { api, calls } = client();
  assert.equal((await api.httpJson('/api/marketing')).revision, 1);
  assert.equal((await api.httpJson('/api/marketing')).revision, 1);
  assert.equal(calls(), 1);
  assert.equal((await api.httpJson('/api/marketing', { cache: 'no-store' })).revision, 2);
  assert.equal(api.peekGet('/api/marketing').revision, 2);
});
test('explicit review retry surfaces failure instead of returning old success', async () => {
  const { api, fail } = client();
  await api.httpJson('/api/marketing/campaigns/1');
  fail();
  await assert.rejects(api.httpJson('/api/marketing/campaigns/1', { cache: 'no-store' }), /Please retry/);
});
test('switching workspace drops cached responses from the previous one', async () => {
  const { api, calls } = client();
  api.setHttpScope('acme');
  await api.httpJson('/api/marketing');
  api.setHttpScope('acme');
  await api.httpJson('/api/marketing');
  assert.equal(calls(), 1);
  api.setHttpScope('acme');
  assert.equal(api.peekGet('/api/marketing'), undefined);
  assert.equal((await api.httpJson('/api/marketing')).revision, 2);
});
