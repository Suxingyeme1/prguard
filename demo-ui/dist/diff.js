/* Presentation only: preserve the original patch for copying and delivery. */
(() => {
  "use strict";

  function parse(patch) {
    const files = [];
    let file = null;
    let oldLine = null;
    let newLine = null;
    let inHunk = false;
    const lines = String(patch).split("\n");
    if (lines.at(-1) === "") lines.pop();
    for (const line of lines) {
      if (!file || line.startsWith("diff --git ")) {
        file = { name: line.startsWith("diff --git ") ? line.slice(11) : "diff", added: 0, removed: 0, rows: [] };
        files.push(file);
        oldLine = newLine = null;
        inHunk = false;
      }
      if (!inHunk && line.startsWith("--- ") && line.slice(4) !== "/dev/null") file.name = line.slice(4).replace(/^a\//, "");
      if (!inHunk && line.startsWith("+++ ") && line.slice(4) !== "/dev/null") file.name = line.slice(4).replace(/^b\//, "");
      const hunk = line.match(/^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
      const row = { kind: "meta", old: null, new: null, text: line };
      if (hunk) {
        oldLine = Number(hunk[1]);
        newLine = Number(hunk[2]);
        inHunk = true;
        row.kind = "hunk";
      } else if (inHunk && line.startsWith("+")) {
        row.kind = "add";
        row.new = newLine++;
        file.added++;
      } else if (inHunk && line.startsWith("-")) {
        row.kind = "remove";
        row.old = oldLine++;
        file.removed++;
      } else if (inHunk && line.startsWith(" ")) {
        row.kind = "context";
        row.old = oldLine++;
        row.new = newLine++;
      }
      file.rows.push(row);
    }
    return files;
  }

  window.PRGuardDiff = Object.freeze({ parse });
})();
