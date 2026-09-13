const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const window = {};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../../demo-ui/dist/diff.js'), 'utf8'), { window });
const parse = value => JSON.parse(JSON.stringify(window.PRGuardDiff.parse(value)));

test('unified hunks show separate old and new line numbers', () => {
  const [file] = parse('diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -3,2 +3,3 @@ f\n keep\n-old\n+new\n+extra\n');
  assert.equal(file.name, 'a.py');
  assert.equal(file.added, 2);
  assert.equal(file.removed, 1);
  assert.deepEqual(file.rows.slice(-4).map(({ old, new: next }) => [old, next]), [[3, 3], [4, null], [null, 4], [null, 5]]);
});

test('added and deleted files retain their real paths and zero-count hunks', () => {
  const files = parse('diff --git a/new b/new\n--- /dev/null\n+++ b/new\n@@ -0,0 +1 @@\n+x\ndiff --git a/old b/old\n--- a/old\n+++ /dev/null\n@@ -1 +0,0 @@\n-y\n\\ No newline at end of file\n');
  assert.deepEqual(files.map(({ name, added, removed }) => [name, added, removed]), [['new', 1, 0], ['old', 0, 1]]);
  assert.equal(files[1].rows.at(-1).kind, 'meta');
});

test('hunk resets and content resembling headers are not misclassified', () => {
  const [file] = parse('--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n--- old string\n+++ new string\n@@ -20 +25 @@\n keep\n');
  assert.equal(file.name, 'a.py');
  assert.equal(file.added, 1);
  assert.equal(file.removed, 1);
  assert.equal(file.rows.at(-1).new, 25);
});

test('empty, binary and unrecognized patches stay lossless as display data', () => {
  assert.deepEqual(parse(''), []);
  const text = 'diff --git a/logo b/logo\nBinary files differ\n<script>alert(1)</script>';
  const [file] = parse(text);
  assert.equal(file.rows.map(row => row.text).join('\n'), text);
  assert.equal(file.added, 0);
});
