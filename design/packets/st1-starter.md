# Packet st1-starter: a `starter` profile, the shipped default

| item | value |
|---|---|
| from | the hq coordinator, 2026-11-17, brief st1-starter, rulings R1 to R7, and the second builder's brief, rulings D1 to D4; hq design/15 §2 row F9 and §10 item 2; this repo's entry 10 |
| pin | `69d0824` on main (su3-start-check's merge, plugin 2.0.0-alpha.137). Worktree `.claude/worktrees/st1-starter`, branch `st1-starter`; the two venvs linked |
| wall | this worktree; no push, `--amend`, rebase, merge, install or plugin update; `make` only through the gate queue; no `claude` started by a test; no relay verb; no test reads the live user file, the live state or the live home (every case in a temp `HOME`); `DECISIONS.md` unchanged |
| may touch | `plugin/lib/claude_session/{profiles.yaml,resolver.py,plug.py,hooks.py,cli.py}`, `plugin/commands/profile.md`, `plugin/skills/session/SKILL.md`, `design/readme/source.md` and its render (`README.md`, `design/readme/rendered.sha256`), `tests/test_st1_starter.py` (new), the existing tests and `scripts/bare-proof`, listed in §3, `.gitattributes` (new, a commit of its own), this packet, `history/sittings/2026-11-17-12-st1-starter.md` and `history/sittings/2026-11-17-13-st1-starter-2.md` (the second builder's); the version, the README's count and the sidecar by `make stamp` alone |
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
| `resolver.resolve`, the name's last fallback | the name used when nothing names one | `starter` |
| `plug.Facts.__init__`, the `default` body (ak5 R5) and `self.frontier` | the profile that states every field | `frontier`, as `resolver.FULL_PROFILE` |
| `plug.Facts._profile_rows`, the `default` layer's row for `profile` | the name used when nothing names one | `starter` |
| `plug._settings`, the default of the `profile` setting | the name used when nothing names one | `starter` |

## 2. Rulings

- R1, the profile: `starter` is a new shipped profile, the last of `profiles:`, its body in §3: fields a shipped layer already uses (`charter.required` as `scratch`, `priority.enabled`, `pacing.enabled`), and D3's one new field. Its model, effort, tiers, lane, posture (`signal`: the meter on) and ceilings are the shipped `defaults`.
- R2, the fallback: where no launch, local or repo layer and no user file's `defaults.profile` names a profile, the session runs `starter`. A user file with no `defaults.profile` is the same road.
- R3, the constant: `DEFAULT_PROFILE = "starter"`; `FULL_PROFILE = "frontier"`, the table above.
- R4, nothing else resolves differently: every other profile, and a session whose launch, repo, local or user layer names one, resolves as at the pin.
- R5, what a starter session is told: a profile whose `charter.required` is false is told `START_METER_PLAIN` (the meter, "when it is time to commit and stop") and its checkpoint line ends `commit what is done, then stop` on either road, no charter named. Keyed on the field, not the name (R1). D2: `scratch`'s start line loses its charter words too, the one change another profile sees (its meter is off by posture).
- D3: at 100% the plain road's last line is `PLAIN_EXIT` ("the context is full; start a fresh session"), not `EXIT_RULE` ("respawn, never compact"), keyed on `charter.required` as R5. No field held the compaction block, so one is new: `charter.blocks_compaction`, absent true; `starter` sets it false, and PreCompact, reading the session's resolved file, lets an automatic compaction pass. A file not read blocks as at the pin, as does every other profile.
- R6, the pages: the README's source table gains `starter` and says what runs when nothing names a profile and how a person takes up the discipline; `profile.md` and the skill name it; `profile`'s list marks the default with ` (the default)`: the user file's `defaults.profile`, else `starter`. D4: as akt-run's prose change (`5fea6d9`), the source, then `make readme` through the gate. Under the source's 16 KB ceiling, `balanced` loses "the everyday default", and a few repeated words go.
- R7, nothing else: no helper's or relay child's profile, no launcher, no ceiling moves.

Riding this packet, a commit of its own: `.gitattributes` gains `.hygiene-allow merge=union`, so two rows that each add an allow row beside the same kin merge with no conflict.

## 3. Interfaces and acceptance

- `resolver.DEFAULT_PROFILE = "starter"`, `resolver.FULL_PROFILE = "frontier"`; `hooks.START_METER_PLAIN`, `hooks.PLAIN_TAIL`, `hooks.PLAIN_EXIT`, `hooks.asks_charter(session) -> bool`, `hooks.blocks_compaction(session) -> bool`; `hooks._checkpoint_out(m, charter, files)` takes `charter` None for the plain tail and last line; `hooks.pre_compact` reads `<session>/resolved.json`; `cli.FALLBACK_MARK`; the session key `charter.blocks_compaction` (bool, absent true) with its `describe config` summary. No other interface moves.
- `starter`'s body: `description`, `charter: {required: false, blocks_compaction: false}`, `priority: {enabled: false}`, `pacing: {enabled: false}`; the rest is `defaults`', so no `plugins` or `notes` (frontier's), and its ceilings' source reads `defaults`.

| # | line | at the pin |
|---|---|---|
| 1 | no user file, an empty repo: the hook's output names `starter` and holds no `charter`, no priority level and no pacing word | `frontier`, a charter asked |
| 2 | a user file with `defaults` naming `profile: frontier`: the hook's output and the resolved file as at the pin, but for the session's paths and the shipped file's input hash | held |
| 3 | a user file with `defaults` and no `profile`: `starter` | `frontier` |
| 4 | a launch, a repo layer and a local layer that each name a profile: that profile | held |
| 5 | `profile <name>` for each profile shipped at the pin: byte-equal; the list shows `starter` and marks the default | no `starter` |
| 6 | under `starter`, the meter's line at its checkpoint names no charter; at 100% it says start a fresh session, and PreCompact lets an automatic compaction pass (D3) | names one; respawn, never compact; blocked |
| 7 | every test the repo held before green, changed only where it asserted the fallback's name (below); `make check` once through the gate queue, green | green |

Tests changed, none deleted or skipped. Named `frontier` in the temp home (`conftest.frontier_home`, or the case's own user or repo file), since each read frontier's body, charter, priority or pacing with nothing naming one: `test_charter`, `test_cli`, `test_hook_meter`, `test_hooks`, `test_ss1_zero`, `test_fw1a`, `test_hook_session_start`, `test_in2_charter_show`, `test_pl1_prompt_line`, `test_rules` (the texts), `test_resolver` (precedence, c6, s21), `test_mt1_tiers` (f2), `test_ss3_true_lines` (the plain case), `test_ak5_plug` (user effort), `scripts/bare-proof` (its repo, for PreCompact's block). Follow the fallback's name: `test_resolver` (defaults alone), `test_mt1_tiers` (f7, r2_f1, r3, whose user layer writes `profiles.starter`), `test_ss3_true_lines` (the chain; an unlaunched status reads `defaults` as its limits source). False of `starter` by design, said by name: `test_rules` (both off), `test_ak5_plug` (an empty home's charter, priority, pacing, plugins, notes and `blocks_compaction` against frontier's default; effort's source the defaults' line). New: `test_st1_starter`, lines 1 to 6 and D3.

## 4. Findings that name this row

None at the pin.

## 5. Forbidden reads

The live user file, the live state, any relay ledger.

## 6. Report

The table: each acceptance line, its exit and its last output line on the branch.
