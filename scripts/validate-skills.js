#!/usr/bin/env node
// Validate every skills/<name>/SKILL.md frontmatter so a malformed or over-long
// description can't silently break a skill's keyword auto-triggering.
//
// Guards the two real failure modes (see memories skill-budget-truncation / yide-dev-repo):
//   1. YAML-breaking description — a leading quote, or a "word: " (colon+space) inside the
//      value — makes some parsers drop the skill's metadata, so it never auto-triggers
//      (the skill stays manually invokable by name, which masks the bug).
//   2. Over-long descriptions — Claude Code shares ONE char budget (~15000 by default) across
//      all skill + slash-command descriptions, built-ins included; long plugin descriptions get
//      truncated out of context in fresh sessions. Raise it via SLASH_COMMAND_TOOL_CHAR_BUDGET,
//      and keep descriptions lean so they fit even on machines that haven't.
//
// Zero dependencies. `node scripts/validate-skills.js` — exit 1 on any error.

const fs = require('fs');
const path = require('path');

const skillsDir = path.join(__dirname, '..', 'skills');
const PER_SKILL_MAX = 1024; // chars; longer descriptions are budget hogs -> error

let errors = 0;
let totalChars = 0;
const names = fs.readdirSync(skillsDir).filter(n => fs.existsSync(path.join(skillsDir, n, 'SKILL.md')));

for (const name of names.sort()) {
  const text = fs.readFileSync(path.join(skillsDir, name, 'SKILL.md'), 'utf8');
  const m = text.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (!m) { console.error(`✗ ${name}: no --- frontmatter block`); errors++; continue; }

  const lines = m[1].split(/\r?\n/);
  const valueOf = key => {
    const line = lines.find(l => l.startsWith(key + ':'));
    return line ? line.slice(key.length + 1).trim() : null;
  };

  if (!valueOf('name')) { console.error(`✗ ${name}: missing 'name'`); errors++; }

  const desc = valueOf('description');
  if (!desc) { console.error(`✗ ${name}: missing 'description'`); errors++; continue; }

  // 1a. leading quote -> parser reads a closed quoted scalar, then chokes on the trailing text
  if (/^["']/.test(desc)) {
    console.error(`✗ ${name}: description starts with a quote — drop it (write a plain scalar).`);
    errors++;
  }
  // 1b. "word: " colon+space -> parser sees a nested mapping; skill won't auto-trigger
  const colon = desc.match(/\S*:\s/);
  if (colon) {
    console.error(`✗ ${name}: description has "${colon[0].trim()} " (colon+space) — use " — " or reword.`);
    errors++;
  }

  // 2. budget
  const len = [...desc].length;
  totalChars += len;
  if (len > PER_SKILL_MAX) {
    console.error(`✗ ${name}: description is ${len} chars (> ${PER_SKILL_MAX}) — trim it (shared budget).`);
    errors++;
  }
}

console.log(`\n${names.length} skills · total description chars: ${totalChars}`);
console.log('(Claude Code default budget ~15000, shared with built-ins; raise via SLASH_COMMAND_TOOL_CHAR_BUDGET.)');

if (errors) {
  console.error(`\n✗ ${errors} problem(s) — fix before commit.`);
  process.exit(1);
}
console.log('✓ all skill descriptions are auto-trigger-safe.');
