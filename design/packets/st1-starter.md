# Packet st1-starter: a `starter` profile, the shipped default

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-17, brief st1-starter, rulings R1 to R7; the second builder's brief, D1 to D4; the fix of review 1, C1 to C6; hq design/15 §2 row F9 and §10 item 2; this repo's entry 10 |
| pin | `69d0824` on main (su3-start-check's merge, plugin 2.0.0-alpha.137). Worktree `.claude/worktrees/st1-starter`, branch `st1-starter`; the two venvs linked |
| wall | this worktree; no push, `--amend`, rebase, merge, install or plugin update; `make` only through the gate queue; no `claude` started by a test; no relay verb; no test reads the live user file, the live state or the live home (every case in a temp `HOME`); `DECISIONS.md` unchanged |
| may touch | `plugin/lib/claude_session/{profiles.yaml,resolver.py,plug.py,hooks.py,cli.py}`, `plugin/commands/profile.md`, `plugin/skills/session/SKILL.md`, `design/readme/source.md` and its render (`README.md`, `design/readme/rendered.sha256`), `tests/test_st1_starter.py` (new), the existing tests and `scripts/bare-proof`, listed in §3, `.gitattributes` (new, a commit of its own), `NICE_TO_HAVE.md` (the fix's rows), this packet, the three builders' charters under `history/sittings/2026-11-17-1[234]-st1-starter*.md`; the version, the README's count and the sidecar by `make stamp` alone |
| verify | `make stamp`, then `make check`, by the gate queue, once each, last |
| acceptance | §3; `PY -m pytest -q tests/test_st1_starter.py` under `.venv` and `.venv-floor` |
| budget | about 90 tool calls, `claude-opus-5-5`; the packet first, then the tests, then the change |

## 1. What the source says (baseline at `69d0824`)

The owner, asked what a new machine's first session is told: "A starter profile."

The ledger, entry 10, carried verbatim: **A machine with no user file runs the starter profile.** With no user file the plugin runs the `starter` profile, its shipped default: the meter on, no charter asked, and no priority or pacing text. A first session on a new machine is told nothing of the sitting discipline, which a person takes up by naming the `frontier` profile in the user file. (2026-11-17; the owner's answer to decision 10, the owner's answer to hq's decision 52 on 2026-11-17)

Cited: hq entry 6 (the plugin repos' build conventions), hq entry 37 (made-up names in fixtures and in this packet).

Measured at the pin, the SessionStart hook in a temp `HOME` with no user file and an empty repo: the line names `profile 'frontier'`, says the meter "prints CHECKPOINT when it is time to bring the charter current and hand off", carries the priority levels S1 to S4 and the pacing clause, and ends `charter: none open today under history/sittings, run agentik-session charter open "<goal>"` (design/15's F9). A user file whose `defaults` names `profile: frontier` gives the same line.

`resolver.DEFAULT_PROFILE = "frontier"` has four uses at the pin:

| use | meaning | after |
|---|---|---|
| `resolver.resolve`, the name's last fallback | the name used when nothing names one | `starter` (off a launcher, C4) |
| `plug.Facts.__init__`, the `default` body (ak5 R5) and `self.frontier` | the profile that states every field | `frontier`, as `resolver.FULL_PROFILE` |
| `plug.Facts._profile_rows`, the `default` layer's row for `profile` | the name used when nothing names one | `starter` |
| `plug._settings`, the default of the `profile` setting | the name used when nothing names one | `starter` |

## 2. Rulings

- R1, the profile: `starter` is a new shipped profile, the last of `profiles:`, its body in §3: fields a shipped layer already uses (`charter.required` as `scratch`, `priority.enabled`, `pacing.enabled`), and C1's one new field. Its model, effort, tiers, lane, posture (`signal`: the meter on) and ceilings are the shipped `defaults`.
- R2, the fallback: where no launch, local or repo layer and no user file's `defaults.profile` names a profile, the session runs `starter`. A user file with no `defaults.profile` is the same road.
- R3, the constant: `DEFAULT_PROFILE = "starter"`; `FULL_PROFILE = "frontier"`, the table above.
- R4, nothing else resolves differently: every other profile, and a session whose launch, repo, local or user layer names one, resolves as at the pin.
- R5 and D3, what a starter session is told: the start line `START_METER_PLAIN` (the meter, "when it is time to commit and stop"), the checkpoint line ending `commit what is done, then stop` on either road, and at 100% `PLAIN_EXIT` ("the context is full; start a fresh session"), not `EXIT_RULE`; PreCompact, reading the session's resolved file, lets an automatic compaction pass. A file not read blocks as at the pin.
- R6, the pages: the README's source table gains `starter` and says what runs when nothing names a profile and how a person takes up the discipline; `profile.md` and the skill name it; `profile`'s list marks the default with ` (the default)`: the user file's `defaults.profile`, else `starter`. D4: as akt-run's prose change (`5fea6d9`), the source, then `make readme` through the gate. Under the source's 16 KB ceiling a few words go.
- R7, nothing else: no helper's or relay child's profile, no launcher, no ceiling moves.

The fix of review 1:

- C1, one waiver: `charter.discipline` (bool, absent true), set by the shipped `starter` alone, governs everything R5 and D3 turn off and C2's words; `charter.blocks_compaction` folds into it and leaves. `charter.required: false` alone changes no line: D2 is withdrawn, so `scratch` reads as at the pin.
- C2: under the waiver the meter stays on, and each budget line (the prompt's zone line, a spawn's ask or deny, the checkpoint) says the percent and what to do: no handoff, checkpoint verb, owner, winding down, charter, respawn or successor; the cadence line is not given.
- C3: `scripts/bare-proof`'s repo names no profile and expects `starter`'s pass on an automatic compaction; a second step names `frontier` and expects the block.
- C4: with nothing naming a profile, a session a launched chain starts (`CLAUDE_SESSION_CHAIN` set, or `run`'s own resolve) runs `frontier`, as at the pin; a plain one runs `starter`.

Riding this packet, a commit of its own: `.gitattributes` gains `.hygiene-allow merge=union`.

## 3. Interfaces and acceptance

- `resolver.DEFAULT_PROFILE = "starter"`, `resolver.FULL_PROFILE = "frontier"`, `resolver.CHAIN_VAR`, `resolver.CHAIN_RE` (hooks' names are these), `resolver.fallback_profile(env, chain=None)`, `resolve(..., chain=None)`; `hooks.START_METER_PLAIN`, `hooks.PLAIN_TAIL`, `hooks.PLAIN_EXIT`, `hooks.PLAIN_TODO`, `hooks.discipline(session) -> bool`; `hooks._checkpoint_out(m, charter, files)` takes `charter` None for the plain road; `hooks.pre_compact` reads `<session>/resolved.json`; `cli.FALLBACK_MARK`; the session key `charter.discipline` with its `describe config` summary.
- `starter`'s body: `description`, `charter: {required: false, discipline: false}`, `priority: {enabled: false}`, `pacing: {enabled: false}`; the rest is `defaults`'.

| # | line | at the pin |
|---|---|---|
| 1 | no user file, an empty repo: the hook's output names `starter` and holds no `charter`, no priority level and no pacing word | `frontier`, a charter asked |
| 2 | a user file naming `profile: frontier`: the hook's output and the resolved file as at the pin, but for paths and the shipped file's hash | held |
| 3 | a user file with `defaults` and no `profile`: `starter` | `frontier` |
| 4 | a launch, a repo layer and a local layer that each name a profile: that profile; `charter.required: false` there changes no line (C1); a chain with none named runs `frontier` (C4) | held |
| 5 | `profile <name>` for each profile shipped at the pin: byte-equal; the list shows `starter` and marks the default | no `starter` |
| 6 | under `starter`, every budget line from 50% past 100% names none of C2's words; PreCompact passes | names them; blocked |
| 7 | every test the repo held before green, changed only where it asserted the fallback's name (below); `make check` through the gate queue, green | green |

Tests changed, none deleted or skipped. Named `frontier` in the temp home (`conftest.frontier_home`, or the case's own file), since each read frontier's body, charter, priority or pacing with nothing naming one: `test_charter`, `test_cli`, `test_hook_meter`, `test_hooks`, `test_ss1_zero`, `test_fw1a`, `test_hook_session_start`, `test_in2_charter_show`, `test_pl1_prompt_line`, `test_rules` (the texts), `test_resolver` (precedence, c6, s21), `test_mt1_tiers` (f2), `test_ss3_true_lines` (the plain case). Follow the fallback's name: `test_resolver` (defaults alone), `test_mt1_tiers` (f7, r2_f1, r3), `test_ss3_true_lines` (an unlaunched status reads `defaults`). False of `starter` by design: `test_rules` (both off), `test_ak5_plug` (an empty home's off fields and the waiver). `scripts/bare-proof` by C3. New: `test_st1_starter`.

## 4. Findings that name this row

Review 1's F4, F6 and F7: `NICE_TO_HAVE.md` n315 to n317.

## 5. Forbidden reads

The live user file, the live state, any relay ledger.

## 6. Report

The table: each acceptance line, its exit and its last output line on the branch.
