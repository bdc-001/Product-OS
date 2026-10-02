const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const path = require("path");
const ts = require("typescript");
const vm = require("vm");

const source = fs.readFileSync(path.join(__dirname, "../app/editor/markdown.ts"), "utf8");
const sandbox = { exports: {}, module: { exports: {} } };
sandbox.module.exports = sandbox.exports;
vm.runInNewContext(
  ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText,
  sandbox,
);
const { inlineMarkdownToHtml, htmlStringToMarkdown, documentMarkdownToHtml, prefixForLine } = sandbox.exports;

test("bold and italic markdown render as HTML tags, not asterisks", () => {
  assert.equal(inlineMarkdownToHtml("**Decision** locked"), "<strong>Decision</strong> locked");
  assert.equal(inlineMarkdownToHtml("wait *quietly*"), "wait <em>quietly</em>");
  assert.equal(inlineMarkdownToHtml("**bold** and *italic*"), "<strong>bold</strong> and <em>italic</em>");
  assert.ok(!inlineMarkdownToHtml("**Decision**").includes("**"));
});

test("HTML formatting round-trips back to markdown for PDF storage", () => {
  assert.equal(htmlStringToMarkdown("<strong>Decision</strong> locked"), "**Decision** locked");
  assert.equal(htmlStringToMarkdown("<b>A</b> and <em>B</em>"), "**A** and *B*");
  assert.equal(htmlStringToMarkdown('<span style="font-weight: 700">Heavy</span>'), "**Heavy**");
});

test("document headings and lists keep their line kinds", () => {
  const html = documentMarkdownToHtml("# Title\n## Heading\n- item\nBody **yes**");
  assert.match(html, /data-line="title"/);
  assert.match(html, /data-line="heading"/);
  assert.match(html, /data-line="bullet"/);
  assert.match(html, /<strong>yes<\/strong>/);
  assert.equal(prefixForLine("heading", "Goal"), "## Goal");
});
