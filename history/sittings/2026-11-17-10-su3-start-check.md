# Sitting 2026-11-17-10: agentik-session, su3-start-check

| item | value |
|---|---|
| goal | SessionStart says, in one line on both channels, a declared watcher the launcher's `status --check` finds not running (entry 12); silence otherwise |
| budget | about 90 tool calls, `claude-opus-5-5`; checkpoint at 80% |
| pin | `accf29f` on main |
| branch | `su3-start-check`, worktree `.claude/worktrees/su3-start-check`, the two venvs linked |
| level | S3, packet `design/packets/su3-start-check.md` |
| window | 200k |
| agents | 0 |

## Done-ness
- [x] the packet, the baseline at the pin, and the four NICE rows that ride it
- [x] R1 to R7: `hooks.session_start`'s watcher line; `tests/test_su3_start_check.py`, green under both venvs
- [ ] `make stamp` through the gate, committed
- [ ] `make check` through the gate, once, last

## Handover
- If this sitting is cut: the first unticked line above.
- Note: `NICE_TO_HAVE.md` is past recordlint's size bound with the four rows (25,514 B); `make stamp` moves the oldest S4 rows, as its target says.
- Choice: no cap on the plugin's own SessionStart words (none at the pin); the share alone is cut at its first line's end to fit `MAX_OUT` as an output's only context, its ` and N more` tail kept.
- Choice: lines are stdout split on newline, control characters (C0, DEL, C1) taken out, ends stripped, blank lines not counted; only blank lines is silence.
- Choice: on the screen the share comes first, then the hook's own message (`FOLLOW_NOTE` or the refresh's failure) after a newline.
- Choice: the child runs in its own process group with the hook's environment, stdin empty, stderr dropped; a wall cut kills the group and reaps the child; at most 64 KiB of stdout is kept, the rest drained.
- Choice: a start that raises outside its own `{}` road reads as `{}` plus the line when there is one; with no line it raises as at the pin.
- decide, owner: coordinator, for hq design/18 item 7. It says SessionStart's additions run "under the hook's one cap (`MAX_OUT`)"; at `accf29f` no SessionStart road reads `MAX_OUT` and the output is 760 to 850 bytes.

## Next act
`make stamp` through the gate, then the one check.
