# Conventions shared by the independent plugins (r1, 2026-09-22)

Binding on session, decisions, respeak and agent-relay; each works alone (R25-91 (3)); these make them consistent, not dependent.

## §1 Layout

```
<repo>/
  <tool>/ or go.mod  the tool (stdlib python or Go), on PATH via `make install`
  plugin/  the plugin subtree, self-contained: names no path outside itself
    .claude-plugin/plugin.json
    skills/<name>/SKILL.md  frontmatter: name, description under 200 chars, allowed-tools; body under 500 lines
    commands/<verb>.md  one verb each, under 30 lines
    agents/<name>.md  only where the plugin owns a lane
    hooks/hooks.json  events, by the shim below or the plugin's own scripts
    hooks/run  optional: execs `<tool> hook <event>` on PATH, else exits 0
    hooks/<name>.ts  optional: the Mod, one `"modules"` entry (§4)
  .claude-plugin/marketplace.json  name = the repo name (exception: `respeak`); one plugin, source "./plugin"
  design/  records `<topic>-rN.md`; packets/ ; readme/source.md
  history/sittings/  charters `<date>-<n>[-<row>].md`, §3.1 shape (§5)
  scripts/hygiene, bounded  the hygiene scan and the gate's breaker (§5); byte-identical, the session's canonical
  scripts/doclint  the doc gate (§5)
  tests/  the suite (§4)
  Makefile  check, test, lint, doclint, hygiene, validate, readme, install, doctor
  README.md LICENSE .hygiene-allow .gitignore
  relay/queue.yaml  only while the relay runs this repo (D4)
```

## §2 plugin.json and marketplace.json

`plugin.json`: `name` (the short id: `session`, `decisions`, `respeak`, `agent-relay`; D8), `version` (semver; §7), `description` (under 200 chars, no owner data), `author {name}`, `homepage`, `repository`, `license`, `keywords`; `dependencies` only where needed, as `{name, version, marketplace}` with an npm range; `userConfig` only for install-time knobs (repo config is §3). `marketplace.json`: `name`, `owner {name}`, `plugins: [{name, source: "./plugin", description, version}]`.

## §3 Configuration layering, the session as optional provider

Each plugin resolves its own configuration, lowest first: shipped defaults; the user's file (`~/.claude/<plugin>/config.yaml`); its section of the repo's `.claude/claude-code-session/config.yaml`; `config.local.yaml` beside it (gitignored); folder and scope files where it has them (respeak); the session's resolved file when present; its session toggles; the invocation.

The resolved file: `${XDG_STATE_HOME:-~/.local/state}/claude-code-session/sessions/<session_id>/resolved.json`, written only by `session` at SessionStart and on `set`, shaped `{"provider": {plugin, version, profile, resolved_at, inputs: [{path, sha256}]}, "<plugin>": {..}}`. A plugin takes `session_id` from hook stdin or `$CLAUDE_CODE_SESSION_ID`, the only session variable it reads, accepts the file only when `provider.version` is in its range, applies its section as the layer above, never writes it, and reports it in `doctor`. Absent, it runs alone.

The session's own, no dependent's: `CLAUDE_SESSION_DEPTH` (`start` sets parent plus one past its scrub, refuses 2 without `--nested`; the relay sets 1 for its children) and `CLAUDE_SESSION_MAX_TURNS` (set by `start --max-turns`; the turn ceiling is the smaller of it and the profile's).

Config files are YAML in the strict subset (D12): mappings, scalars, flat lists, comments. Unknown keys: reported by `doctor`, never fatal.

## §4 The test standard

- **Go** (agent-relay, example-app): table tests over every transition of a state machine; every effect (git, spawn, clock, files) behind a faked interface; an end-to-end test against a fake `claude` of canned stream-json; `go vet` and the race detector in `check`; no network in tests.
- **python** (session, decisions, respeak): stdlib, from `tests/`; a fake `claude` on a temporary PATH, never quota; every hook tested per event from a stdin fixture, exact stdout and exit; the resolver tested per layer pair; byte ceilings tested, not assumed.
- **Mod** (`plugin/hooks/*.ts`): one module per plugin holds every concern (2.1.296: one unmatched hook per event, `$` into no import); `.test.ts` beside it, effects faked, run in `check` by `claude plugin test plugin` (no model); pytest never reads it.
- Every invariant in a design's provability section is one named test; one that can also be a runtime guard is both, the test naming the guard.

## §5 `make check` and the doc gate

`check` runs under `scripts/bounded --lock .check.lock --wall 840 --load 4`: `test`, `lint`, `doclint`, `hygiene`, `validate` (60 s), README freshness (§6). The wall includes the load wait (the relay allows 900 s), held only while the CPU's idle share confirms it (≤ 25%); the lock is a `flock` held by a guardian that kills the command's group when `bounded`'s pipe closes, SIGKILL too. A last stderr line `bounded: stop: lock|load|wall` (exits 2, 2, 124) is unrun, never red; under another `bounded` (`BOUNDED_DEPTH` above 0) it is `bounded: nested stop:`, a plain red. `doclint`'s rules are its docstring: byte ceilings (this file 9,216), `NEXT` only as `history/sessions/NEXT`. A packet's `verify` row is the gate line (`make check`); acceptance lines are targeted, rerun by the gate on the branch; doclint's suite rule fails closed from any runner word, passing only a test file, `::`, a `-k`, `go test <pkg> -run <Name>`, `make -n`, or `make` of `MAKE_TARGETED` targets. Packet prompts keep the turns line (`Your --max-turns is N`) until the doctor reads the meter hook live. `pluginlint` is retired at each repo's next re-sync.

## §6 README via respeak, and hygiene

`design/readme/source.md` holds the facts in the technical lane; `make readme` renders `README.md` in respeak's technical mode (`claude -p` or respeak's own script); the invariant is the sidecar `design/readme/rendered.sha256`, not the renderer: two `shasum -a 256` lines (source, README), both from `make readme`. Edit the source, never the README. A README names dependencies by id and range, nothing else outside the repo; no owner path, address, domain, private repo or person in any tracked file. `scripts/hygiene` scans each line, path and link target for its generic groups (home, lan, sibling, secret, email) and the private list's, owner terms kept outside the repo (`$AGENTIK_HYGIENE_PRIVATE` or `~/.config/agentik/hygiene-private.tsv`); absent: one warning, exit 2 under `--require-private`. `.hygiene-allow` has exceptions (`secret` only under `tests/fixtures/`; `sibling` skipped under `history/sittings/`); counts only, no match or private regex; exit 2 on a hit. Every copy of `scripts/hygiene` has sha256 `acc3498d4ad3555b095f7f12b22c1c1257fc7d8f2f2f6055c34bd0a21ec34421`, of `scripts/doclint` `26eaf2c84aadb822f8d63a0257b063afcc0ba6d9bbcf1d2d856abe4c6388341f`, of `scripts/bounded` `4fdfdc1df94364d72fdc378acfade979f7be32342c262687931fe49752ac40b2`. Nothing is pushed red; the owner pushes (R25-91 (4)).

## §7 Versioning and the sitting record

Semver; `0.x` may break on a minor and says so in the tag message; a change to a config key, a hook's output, or the resolved-file contract bumps the major; a release's tag `v<semver>` equals `plugin.json` `version`; a `-alpha.N` version needs no tag (and matches no `^` range); the session widens a dependency range only once its suite passes against it. Sittings carry a charter, commit per act, never `--amend` or push, builders in worktrees (at open, before `make`, `.venv` a symlink to the main checkout's; `make venv` only where it has none); a worktree never writes under `.venv` (no `pip install -e`: E7). `make install` freezes the committed `<tool>/` by tree hash and runs it with `python -P` (floor 3.11): no checkout runs hooks (T5). The launcher bakes the venv's `bin/python` link (its directory resolved), never the link's target; a `/Cellar/` path is refused. When that interpreter or the frozen tree is gone, a hook says `run make install` once and exits 0; other verbs exit 1. Scripts keep `#!/usr/bin/env python3` (T3: the owner's global line names the exception); gate lines run under `make` or `.venv/bin/python`, never a shim.

## §8 Citing a record

Packets and sitting prompts' read lists cite a record as `record <file> --section SPEC` lines (overhaul-r1 §2.7), never a prose range; READMEs cite sections likewise.

## §9 Packet authoring

- **may touch** is a closed list of full paths from the repo root; it always admits `history/sittings/*.md` and `history/sessions/NEXT`.
- The `verify` row is required (doclint's GRANDFATHERED excepted: 11 here, 17 in agent-relay); each **acceptance** line is targeted (§5; agent-relay's `packet.Unbounded` takes the same cells), with a measured baseline. SPENT (agent-relay's `spent`, ar21) keeps the row, skips the suite rule. In the table every pipe is `\|` (the gate unescapes), so alternation is `grep -E` with a plain `|`; fixed strings, `grep -qF`.
- Six sections, six header rows plus `verify`, under 9,216 bytes.
- A packet's charter opens with doclint's five rows; the budget row says so.
- The builder decides inside the design of record, records each choice in the charter's handover with its consumer, and names at most one open fork for the owner.
