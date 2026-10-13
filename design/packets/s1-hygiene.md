# Packet S1: conventions and the hygiene scan land in claude-code-session

| item | value |
|---|---|
| from | `design/overhaul-r1.md` §4 and §5, `design/conventions.md` §1, §5, §6, `design/research.md` §1 (the session row). The builder reads THIS packet and the three files named, not the brief |
| pin | claude-code-session `main` at the sha `design/plan.md` was committed at (or later on main); branch `s1-hygiene`, worktree `../claude-code-session-wt-s1` |
| wall | this repo only. No other repo is read or written; no push; no `--amend` |
| may touch | `scripts/hygiene` (new), `scripts/doclint` (new), `.hygiene-allow` (new), `.gitignore` (add `config.local.yaml`, `__pycache__`), `Makefile` (add `check`, `doclint`, `hygiene`, `validate`; keep every existing target), `tests/test_hygiene.py` and `tests/test_doclint.py` (new), `design/conventions.md` (ONE line: the sha256 in §6). Nothing else; anything else is a report line |
| acceptance | `make test 2>&1 \| tail -1` reads 184 passed or more; `make check; echo $?` reads 0; `scripts/hygiene --json \| /usr/bin/python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["hits_outside_allowlist"])'` reads 0; `scripts/doclint; echo $?` reads 0; `wc -c design/conventions.md` under 6,144; `git status --short \| wc -l` reads 0 after the last commit |
| budget | 80 turns, 100k context; commit per item; checkpoint at 80%; never push, amend or rebase |

## 1. What the source says (quoted)

conventions §6: "`scripts/hygiene` (overhaul-r1 §5) scans `git ls-files` for the six groups with `.hygiene-allow` exceptions (`path: group`), prints counts only, exits 2 on a hit, and runs in `check`." conventions §5: "`check` runs, in order: `test`, `lint` (byte-compile or `go vet`), `doclint`, `hygiene`, `validate` (`claude plugin validate plugin/`), and refuses a `README.md` older than `design/readme/source.md`." and "`doclint` enforces: charters under 4,096 bytes in the §3.1 shape; packets under 9,216 bytes with the six sections and the header table's six rows; research and conventions under 6,144 bytes; links resolve; no `NEXT` file." overhaul-r1 §5: "one file, copied byte-identical into each of the four repos; the canonical copy is this repo's". research §1, the session row: home path 1 line in 1 file; names 2 lines in 2 files (the author fields); siblings named: example-app 3/2, respeak 9/6, session (self) 14/8, agents 3/2.

## 2. Rulings

R25-91 (4): a public-hygiene scan is part of every repo's check; nothing is pushed until it is green; the owner pushes. R25-87: the two ceilings, the budget row above. Conventions §5 and §6 as quoted. `validate` and the README freshness rule apply only when `plugin/` and `design/readme/source.md` exist: on this pin neither does, so `check` skips them with a printed "skipped: absent" line, never a silent pass.

## 3. Interfaces (signatures, not prose)

- `scripts/hygiene [--json] [--allow .hygiene-allow] [--repo DIR]`: stdlib python 3.10+, `#!/usr/bin/python3`, one file, no import of anything in this repo. Scans `git ls-files -z` of `--repo`, text files only (skips a file with a NUL in its first 8 KB). Six groups, case-insensitive, as regexes in one table at the top: `home` (`/Users/[a-z]+`, `~/cod[e]/`), `lan` (`192\.168\.`, `10\.\d+\.\d+\.\d+`), `domain` (the owner's domains), `private` (the owner's private repo names), `person` (the owner's names), `sibling` (`respeak`, `decisions`, `claude-code-session`, `claude-code-agents`, and the owner's private product). Since public-r1 (2026-10-13) the owner's terms are not in this record or the file: `domain`, `private` and `person` are read from the private list outside the repo, conventions §6. Output: a table `group  lines  files` and, under it, `path  group  lines` for every hit outside the allowlist; NEVER a matched line. `--json`: `{"groups": {...}, "hits_outside_allowlist": N, "files": [{"path","group","lines"}]}`. Exit 0 when `hits_outside_allowlist` is 0, 2 otherwise, 1 on usage or when `git ls-files` fails.
- `.hygiene-allow`: one entry per line, `<path-glob>: <group>[,<group>]`, `#` comments. Seed: `LICENSE: person`, `pyproject.toml: person`, `design/packets/*.md: sibling,private`, `design/*.md: sibling,private,home` (the design records name the siblings and quote the research; they are the exception the README is not), `history/sittings/*.md: sibling`.
- `scripts/doclint [--repo DIR]`: the rules of conventions §5, each a function returning a list of `path: rule: detail` lines; exit 0 when the list is empty, 2 otherwise; the charter shape check is the five parts and the five table rows of example-ops's `charter-close` (the builder reads that script's docstring only if it needs the exact refusals; it is at `example-ops/example-app-v2/scripts/charter-close`, read-only, the one permitted read outside the wall).
- `Makefile`: `check: test lint doclint hygiene validate`; `hygiene: ; scripts/hygiene`; `doclint: ; scripts/doclint`; `validate:` runs `claude plugin validate plugin/` when `plugin/` exists, else prints `validate: skipped, no plugin/`. Existing targets unchanged.
- Tests: `tests/test_hygiene.py` builds a temporary git repo with fixtures per group, an allowlisted file and a binary file, asserts the counts, the exit codes and that no output line contains a fixture's matched text; `tests/test_doclint.py` fixtures a charter over 4,096 bytes, a packet missing a section, a NEXT file, a dangling link.

## 4. Findings that name this row

research §1: the session repo is near clean; the two `person` lines are the author fields (allowlisted by design); the `sibling` lines in README and SKILL.md stay red until S6 rewrites the README, so `.hygiene-allow` carries `README.md: sibling` and `SKILL.md: sibling` with a `# until S6` comment, and the report says so. The 1 `home` line: find it, and if it is documentation, rewrite it as `~` or a placeholder; if it is a test fixture, allowlist it and say why.

## 5. Forbidden reads

`example-app`, `example-ops` (except the one script named in §3), `example-mac`, the other plugin repos, `~/.claude/projects/` (transcripts hold secrets), `bugs/`, `RUNBOOK.md` and `README.md` beyond `grep -n` for the hygiene hits. The brief. Any file over 8 KB whole: `sed -n` ranges only.

## 6. Report (capped: one table, at most five bullets, under 1,500 words)

The table: each acceptance line, its exit and its last output line on the branch. Bullets: the hygiene counts per group before and after (numbers only); the allowlist entries and why each; anything `doclint` refused in the existing `design/` and `history/` files and what was done; the sha256 written to conventions §6; what was left undone. The last line: the branch name and its head sha.
