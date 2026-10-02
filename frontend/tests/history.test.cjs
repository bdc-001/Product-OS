const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const path = require("path");
const ts = require("typescript");
const vm = require("vm");

const source = fs.readFileSync(path.join(__dirname, "../app/editor/history.ts"), "utf8");
const sandbox = { exports: {}, module: { exports: {} } };
sandbox.module.exports = sandbox.exports;
vm.runInNewContext(
  ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText,
  sandbox,
);
const { createValueStack, historyAction } = sandbox.exports;

test("value stack undoes and redoes in order without dropping the baseline", () => {
  const stack = createValueStack();
  assert.equal(stack.has(), false);
  stack.reset("");
  assert.equal(stack.has(), true);
  stack.push("a");
  stack.push("ab");
  stack.push("abc");
  assert.equal(stack.undo(), "ab");
  assert.equal(stack.undo(), "a");
  assert.equal(stack.undo(), "");
  assert.equal(stack.undo(), null);
  assert.equal(stack.redo(), "a");
  stack.push("az");
  assert.equal(stack.redo(), null);
  assert.equal(stack.undo(), "a");
});

test("cmd/ctrl z and shift-z map to undo and redo", () => {
  assert.equal(historyAction({ metaKey: true, ctrlKey: false, altKey: false, shiftKey: false, key: "z", code: "KeyZ" }), "undo");
  assert.equal(historyAction({ metaKey: true, ctrlKey: false, altKey: false, shiftKey: true, key: "z", code: "KeyZ" }), "redo");
  assert.equal(historyAction({ metaKey: false, ctrlKey: true, altKey: false, shiftKey: false, key: "y", code: "KeyY" }), "redo");
  assert.equal(historyAction({ metaKey: true, ctrlKey: false, altKey: false, shiftKey: false, key: "b", code: "KeyB" }), "");
});
