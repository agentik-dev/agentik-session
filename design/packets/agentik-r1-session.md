# Packet agentik-r1-session: `agentik-session`, its alias, the `session@agentik` plugin, the new folders

| item | value |
|---|---|
| from | agentik-commons `design/agentik-r1.md` §2.4, §4.1, §4.3, §5.1–§5.3, §6.1–§6.3, §8.1–§8.4, §10; step 0 landed in the owner's ledger (2026-10-13). The builder reads THIS packet, those sections and §5 |
| pin | `main` at `e7f0723` or later; agentik-commons `main` after agentik-r1-commons merges; branch and worktree `agentik-r1-session`, off main; a hand-run builder |
| wall | this repo only; agentik-commons read-only (its `scripts/sync` writes here). No push, `--amend`, rebase, network. Merged without installing (§8.1 step 2): `make install` only with a `mktemp -d` PREFIX and XDG_STATE_HOME; no `claude` beyond `make check`'s; never start a launcher. Never write in `~/.local/state` or `~/.config`, read a transcript, or build or run a relay binary or verb |
| may touch | `claude_session/*`, `install-wrapper.sh`, `Makefile`, `pyproject.toml`, `scripts/{prune-trees,readme-render}`, `plugin/**`, `tests/**`, `RUNBOOK.md`, `.hygiene-allow`, `design/readme/source.md` then `make readme`, `scripts/{agentik,hygiene,bounded,vendored.sha256}` by sync, `NICE_TO_HAVE.md`; delete `.claude-plugin/marketplace.json`; under `design/`, only the §6 report |
| acceptance | `test -e .claude-plugin/marketplace.json; echo $?` reads `1`; `grep -c '^agentik-session = ' pyproject.toml` reads `1`; `test -f tests/fixtures/repo/.claude/agentik/config.yaml; echo $?` reads `0` |
| budget | 150 turns, 150k context; commit per act; checkpoint at 80% |
| verify | `make check` |

## 1. What the source says

- **§4.1, §4.3.** The tool is `agentik-session` (`make install`); `claude-session` stays as a symlink until 2026-12-31. Verbs stay, plus `--version`. Under the old name, stderr a terminal, verb not `hook`: one line `claude-session: renamed; use 'agentik session …' (ends 2026-12-31)`. Start lines read `agentik session run --chain <name>`.
- **§2.4, §8.4.** `test_readme` requires the old CLI today; a running launcher keeps its tree and state path until restarted.
- **§5.1–§5.2.** The plugin becomes `session@agentik`, namespace unchanged; plugin code calls the dash name; `allowed-tools: Bash(agentik-session *)`; shims try new, then old. This repo's `marketplace.json` is deleted.
- **§6.3.** c1 state folder (`config.py:13`); c4 repo folder → `.claude/agentik/` (`resolver.py:63`), doctor flags the old; c5 user profiles → `~/.claude/agentik/` (`resolver.py:241`); c6 section `agent-relay` → `relay`, `relay` wins with a warning (`doctor.py:384`, `profiles.yaml:51,72`); c7 IDs → `<p>@agentik`, doctor warns on the old (`doctor.py:21,36–40`); c8 share → `agentik-session`, old trees stay while used; c11 `plugin/hooks/{run,session.ts}`; c13 `launch.py:29`. Folders move only in the cold window.
- **§6.2.** (a) messages in seven `claude_session/*.py`, `RUNBOOK.md`; (b) `mkt.json`, `pyproject.toml`, `cli.py`, `chain.py`, the commands, `SKILL.md`, `scripts/readme-render`, `README.md`; (c) above; tests: 25 plus 2 `*.test.ts`.
- **§8.2, D3.** Vendor `scripts/{agentik,hygiene,bounded}` by sync; `renamed` reads 0; the install also installs `agentik`. Fails before: install writes `agentik-session` and the old link.

**Live hits** (lines per file). Clear 39: `README.md` 40, `RUNBOOK.md` 45, `pyproject.toml` 2, `marketplace.json` 1, `claude_session/{admission 1, chain 5, cli 19, measure 1, mod 1, models 2, profiles.yaml 4, rules 3, sessionconfig 4}`, the commands 14, `SKILL.md` 25, 19 files under `tests/` 50. Allow 21 (ruling 12): `Makefile` 8, `install-wrapper.sh` 5, `scripts/{doclint,readme-render}` 3, `claude_session/{config 1, doctor 13, hooks 11, launch 8, resolver 9}`, `plugin/hooks/*` 31, 8 tests 74 (doclint, hygiene, doctor, hook_session_start, hooks, install, launch, resolver). Plus 40 charters (ruling 13).

## 2. Rulings (decided inside the record, one sentence each)

1. A c-item reader takes the new path when it exists, else the old when it exists, else the new; a writer writes where its reader resolved; one `config.py` helper serves c1, c4, c5, c8.
2. `make install` writes the launcher as `$(PREFIX)/bin/agentik-session`, links `claude-session` to it (relative), copies `scripts/agentik` to `$(PREFIX)/bin/agentik`, freezes trees under `$(PREFIX)/share/agentik-session/`, prunes only that share, and clears the install-needed marker where ruling 1 resolves.
3. The launcher prints the note when `${0##*/}` is `claude-session`, `[ -t 2 ]` holds and `$1` is not `hook`.
4. `--version` prints `agentik-session 2.0.0-alpha.14`; `prog` and lines for a person use `agentik session …` (the start line too); lines a model runs (skill, hook hints) use `agentik-session …`; message prefixes read `agentik-session:`.
5. c6: the resolver reads `relay`, else `agent-relay`; the resolved file carries the section as `relay` and, until r2, a copy as `agent-relay` (§8.6); `profiles.yaml` ships `relay:`.
6. c7: `PLUGIN_ID` is `session@agentik` and each sibling is `<p>@agentik` (relay's plugin is `relay`, D2); an old ID alone is a warn naming the switch.
7. c11: `plugin/hooks/run` and `session.ts` run `agentik-session` when it is on PATH, else `claude-session`.
8. c13: the plugin search takes the `agentik-*` folder names first, then the old ones; the local lane runs `agentik-agents local` when on PATH, else the old script.
9. The respawn match (`hooks.py:398–404`) accepts `agentik-session checkpoint`, `agentik session checkpoint` and the old spelling (load-bearing, though the row lists it as (a)).
10. `pyproject.toml`: name `agentik-session`, one script `agentik-session` (the launcher is the install); the version stays (r2 bumps the major).
11. `validate` drops the `.` line; `hygiene` first checks `shasum -a 256 -c --status scripts/vendored.sha256`; `test_hygiene.py` only swaps its exits (1 hit, 2 usage); `scripts/doclint` stays byte-identical (others pin it).
12. Each allowed file gets one row `<path>: renamed  # <reason>`: §6.1's exceptions (the vendored hygiene too), the alias note, the fallbacks (rulings 1, 5–9) and their tests; old names in their prose still go.
13. `history/sittings/*: renamed  # per-packet records (§5.3)`, since commons' newest-per-suffix rule counts each as live.
14. The two fixtures move by `git mv` to `.claude/agentik/config.yaml`, with `relay:`; old-path cases are built in a temp dir.

Further forks: decide inside the record; log in §6.

## 3. Interfaces

- install: ruling 2, still refused on a dirty `claude_session/`; doctor: the c4 old folder, the c6 old key and each old ID are warn rows naming the move.
- `test_readme` requires `agentik session report`, `agentik session doctor`, `claude plugin marketplace add agentik-dev/agentik-commons` and `session@agentik`.

## 4. Findings that name this row

None. The table is the whole acceptance (the header holds its read-only subset; `verify` the gate line), run in the worktree after the last commit.

| # | line | reads |
|---|---|---|
| 1 | `make check >/dev/null 2>&1; echo $?` | `0` |
| 2 | `scripts/hygiene --json \| python3 -c 'import json,sys;print(sum(f["group"]=="renamed" for f in json.load(sys.stdin)["files"]))'` | `0` |
| 3 | `d=$(mktemp -d); XDG_STATE_HOME=$d/s make install PREFIX=$d DOCTOR=0 >/dev/null 2>&1; $d/bin/agentik-session --version; readlink $d/bin/claude-session; ls $d/share; test -x $d/bin/agentik && echo front; $d/bin/claude-session --version 2>&1 >/dev/null \| wc -l; rm -rf $d` | `agentik-session 2.0.0-alpha.14`, `agentik-session`, `agentik-session`, `front`, `0` |
| 4 | `d=$(mktemp -d); for n in agentik-session claude-session; do printf '#!/bin/sh\necho "%s $*"\n' $n > $d/$n; chmod +x $d/$n; done; PATH=$d:/usr/bin:/bin sh plugin/hooks/run SessionStart </dev/null; rm $d/agentik-session; PATH=$d:/usr/bin:/bin sh plugin/hooks/run SessionStart </dev/null; rm -r $d` | `agentik-session hook SessionStart`, `claude-session hook SessionStart` |
| 5 | `git ls-files tests/fixtures \| grep -c '/.claude/agentik/config.yaml$'` | `2` |
| 6 | `grep -rlF 'Bash(agentik-session *)' plugin/commands \| wc -l` | `6` |
| 7 | `shasum -a 256 -c scripts/vendored.sha256 \| grep -c ': OK$'` | `3` |
| 8 | `C="$(git rev-parse --path-format=absolute --git-common-dir)/../../agentik-commons"; cmp -s scripts/hygiene "$C/scripts/hygiene" && cmp -s scripts/agentik "$C/bin/agentik" && echo same` | `same` |
| 9 | `test -e .claude-plugin/marketplace.json; echo $?` | `1` |
| 10 | `git status --short \| wc -l` | `0` |

Fails before: line 3 (no `agentik-session`, no link); lines 2, 4–7, 9.

## 5. Forbidden reads

Read-only outside: `$C` (line 8): `design/agentik-r1.md`, `GUIDE.md`; run `"$C/scripts/sync" .` once.

Forbidden: transcripts, `~/.local/state`, `~/.config` (hygiene reads its private list; never print it), the owner's ledger, other repos.

## 6. Report (under 1,500 words)

Each line's output; commits; rulings beyond §2; `NICE_TO_HAVE.md` adds.
