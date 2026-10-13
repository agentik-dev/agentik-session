# Packet S7: conventions (items 23 to 27), checkpoint, RUNBOOK and doctor (41 to 43)

| item | value |
|---|---|
| from | `design/conventions.md` whole (the record amended); plan row 19; items 23 to 27, 41 to 43 and 21 (optional) of the decisions brief as ruled 2026-09-22 16:30, quoted in §1; the STANDING WORD: decide inside the design, record the choice, escalate only a real fork. The builder reads THIS packet and those only |
| pin | `main` at 4901b1b or later; branch and worktree `s7-conventions-and-doctor`, off main |
| wall | this repo only. No push, no `--amend`, no rebase, no device; no network |
| may touch | `design/conventions.md`, `scripts/doclint` (the ceiling only), `Makefile`, `design/readme/rendered.sha256`, `design/readme/source.md`, `README.md` (by `make readme` only), `tests/test_readme.py`, `claude_session/cli.py` (line 513), `tests/test_cli.py`, `claude_session/doctor.py`, `tests/test_doctor.py`, `RUNBOOK.md`, `claude_session/charter.py`, `tests/test_charter.py`, `plugin/skills/session/SKILL.md` (one line, item 21), `design/plan.md` (row 19's cell), `history/sittings/*.md`, `history/sessions/NEXT`. Nothing else |
| acceptance | `make check; echo $?` reads 0; `make test 2>&1 \| tail -1` reads 321 passed or more; `grep -c 'Packet authoring' design/conventions.md` reads 1; `grep -c 'CONVENTIONS_CEILING = 8192' scripts/doclint` reads 1; `shasum -c --status design/readme/rendered.sha256; echo $?` reads 0; `cat design/conventions.md Makefile \| grep -c 'shasum -c'` reads 2 or more; `git grep -l 'CLAUDE_SESSION_ID' -- claude_session plugin README.md design/conventions.md design/readme \| wc -l` reads 0; `grep -c 'the only session variable' design/conventions.md` reads 1; `for f in hygiene doclint; do grep -qF "$(shasum -a 256 scripts/$f \| cut -c1-64)" design/conventions.md \|\| echo $f; done \| wc -l` reads 0; `python3 -m claude_session checkpoint --help \| grep -c 'add -A'` reads 0; `python3 -m claude_session checkpoint --help \| grep -c 'tracked'` reads 1; `grep -c 'tracked' design/readme/source.md` reads 1 or more; `grep -o 'claude-session [a-z-]\+' RUNBOOK.md \| sort -u \| grep -c -E 'reset\|statusline'` reads 0; `grep -c -i -E 'schedul\|usage window\|six named\|fork' RUNBOOK.md` reads 0; `python3 -m claude_session doctor --json 2>/dev/null \| python3 -c 'import json,sys;c=[c for c in json.load(sys.stdin)["checks"] if c["name"]=="python"][0];print(c["ok"],"newest" in c["detail"])'` reads `True True`; `grep -c '/usr/bin/python3' claude_session/doctor.py` reads 0; `git status --short \| wc -l` reads 0 after the last commit. Item 21, only when built: `d=$(mktemp -d); RELAY_ROW=s7 python3 -m claude_session charter open --dir $d probe >/dev/null 2>&1; ls $d; rm -r $d` reads `<today>-1-s7.md` |
| budget | 80 turns (item 46 says 60: nine acts), 100k context; 100 with a reason in the charter; commit per act; checkpoint at 80%; never push, amend or rebase |

## 1. What the source says (quoted)

Item 23: "may touch spans must be full paths"; "`\|` is the table's escape ... alternation uses `-E` or a plain `|`"; "`grep -qF` for fixed strings". Item 24: "the session's sidecar `design/readme/rendered.sha256` checked by `shasum -c`". Item 25: "`CLAUDE_CODE_SESSION_ID` only". Item 27: "§3 as S6 wrote it is the contract; add the path there". Item 41: "tracked files only, never `add -A` unattended". Item 42: "prunes RUNBOOK or folds it into the README". Item 43: "doctor does not yet suggest newer python versions". The owner, 12:55: "never Apple's /usr/bin/python3 ... doctor suggests newer versions as they release". Conventions §5: "research and conventions under 6,144 bytes".

## 2. Rulings (decided inside the design; the charter records each with its consumer)

- Conventions is 6,136 bytes of a 6,144 ceiling, so §9 cannot fit: `design/conventions*.md` goes under 8,192 (`CONVENTIONS_CEILING` in doclint; research keeps 6,144) and §5 says so.
- Item 24: the sidecar holds the full `shasum -a 256 design/readme/source.md` line (hash, two spaces, path); `make readme` writes it; `check` runs `shasum -c --status` from the repo root; `test_readme.py` follows. §5 names the sidecar and `shasum -c`; §6: the other repos align in their own rows.
- Items 25 and 27 are true on main: the code reads `CLAUDE_CODE_SESSION_ID` only; `resolver.py` writes the path §3 carries (`<state>/sessions/<id>/resolved.json`, `config.py` line 13). §3 gains the clause "the only session variable a plugin reads", nothing else.
- Item 26: `scripts/hygiene` is not touched; doclint changes once (the ceiling) and §6 carries both scripts' shas after the last doclint edit; the copies in decisions, respeak and agent-relay re-sync in their own rows (the handover names them, with the new sha).
- Item 41: `cli.py` already stages with `add -u` and reports the untracked; `tests/test_cli.py` line 116 proves it; SKILL.md and `commands/checkpoint.md` say tracked only. The act: the `--commit` help (line 513) says "git add -u (tracked files only) && git commit first"; one clause in `source.md` Commands; a test asserts the help text.
- Item 42: prune, not fold (`source.md` is 5,786 of 6,144 bytes). RUNBOOK keeps what the README does not say (setup, modes, the local-only numbers, config); every verb it names exists (`reset` and `statusline` do not); no scheduling, window or "six named" text; §4's zone table says what SKILL.md says or goes.
- Item 43: doctor's python check reads the interpreter it runs under (`sys.version_info`, `sys.executable`), never `/usr/bin/python3`; ok at 3.10+. Newer versions, offline-safe: `pyenv install --list` when `pyenv` is on PATH (local definitions, no network), else a dated tuple `KNOWN_PYTHONS` in `doctor.py`; the detail reads `X.Y.Z (<exe>); newest known A.B.C (pyenv's list)` or `(the shipped list of <date>)`. Tests fake `pyenv` on a temporary PATH.
- Item 21, optional and last: `charter open` names the file `<date>-<n>-$RELAY_ROW.md` when set, else as today; `_numbered` accepts the suffix; the title line is unchanged, so doclint is not touched. Past 70 turns, skip it and hand it on.
- `make readme` only when a section it describes changed (Commands, item 41); count the rounds in the charter.

## 3. Interfaces (signatures, not prose)

- Conventions §9 "Packet authoring", under 900 bytes: may touch is a closed list of full paths from the repo root and always admits `history/sittings/*.md` and `history/sessions/NEXT`; every acceptance line is a shell line with a measured baseline in the plan's table; in the table every pipe is `\|` (the gate unescapes), so alternation is `grep -E` with a plain `|` and fixed strings are `grep -qF`; the six sections, the six header rows, under 9,216 bytes; `record --section` citations (§8); the builder decides inside the design of record, records each choice in the charter's handover with its consumer, and names at most one open fork for the owner.
- §5: "research under 6,144 and conventions under 8,192 bytes"; the sidecar and `shasum -c` in a clause. §6: both shas. §3: the clause.
- `scripts/doclint`: `CONVENTIONS_CEILING = 8192` beside `RECORD_CEILING`; `check_sizes` picks by glob.
- `Makefile` `readme`: `shasum -a 256 design/readme/source.md > design/readme/rendered.sha256`; `check`: `shasum -c --status design/readme/rendered.sha256` or `readme: stale, run make readme` and exit 2.
- `doctor.py`: `_check_python(env, version=sys.version_info, exe=sys.executable) -> Check`; `newest_known(env) -> tuple[str, str]` (version, source); the list parsed with `^\s*3\.\d+\.\d+$`, `_run`'s timeout.
- `cli.py` line 513; `tests/test_cli.py`: `test_checkpoint_help_names_tracked_only`.
- `charter.py`: `open(..., row: str | None = None)`, the caller passes `os.environ.get("RELAY_ROW")`; `_numbered`'s pattern `^<date>-(\d+)(-[A-Za-z0-9._-]+)?\.md$`.

## 4. Findings that name this row

On main 4901b1b: `make check` 0, `make test` 319 passed; conventions 6,136 bytes; doclint's sha absent from §6; the sidecar is the bare hash, `shasum -c` exits 1 on it; `checkpoint --help` says `git add -A` while the code runs `add -u`; RUNBOOK names `reset` and `statusline`, verbs `--help` lacks, and hits the stale words four times; `doctor` reports `/usr/bin/python3 is 3.9.6; needs 3.10+` where the virtualenv runs 3.14.7; `pyenv 2.8.4` is on PATH and `pyenv install --list` works offline (newest 3.14.7); `charter open` ignores `RELAY_ROW`; `CLAUDE_SESSION_ID` appears in records and one test, never in the code or the plugin.

## 5. Forbidden reads

Every other repo; `~/.claude/projects/`; `history/relay/`; `bugs/`; `design/research.md`; `design/overhaul-r1.md`; `design/plan.md` beyond row 19 and its baselines; the other packets; `RUNBOOK.md` whole (`grep -n`, then `sed -n` ranges); any file over 8 KB whole.

## 6. Report (capped: one table, at most five bullets, under 1,500 words)

The table: each acceptance line, its exit and its last output line on the branch. Bullets: every choice made inside the design, with its consumer; the new sha of `scripts/doclint` and the sidecar shape, for D2, R2 and AR2; the `make readme` count; what was skipped; at most one open fork for the owner. The last line: the branch name and its head sha.
