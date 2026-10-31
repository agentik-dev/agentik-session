# Packet S47, Amendment 1: the refuter's round 1 on 61fd2ad

| item | value |
|---|---|
| from | the refuter's round 1 on 61fd2ad, the coordinator's rulings; parent `design/packets/s47-gate-key.md`, whose rulings stand but where this moves them |
| pin | 61fd2ad (branch `s47-gate-key`, alpha.32); worktree `.claude/worktrees/s47-gate-key` |
| wall | this worktree only; no push, `--amend`, rebase, merge, device, `make check`, `make install`, `make readme`; never write under `~/.local/state`; never run a real `gate run` or `gate serve` against the live state root; never run a relay verb, or build or run a relay binary; commit by explicit path; stay at `nice -n 10`; this repo is public, so no private repo names |
| may touch | `claude_session/gate.py`, `claude_session/cli.py` (its `gate` help, only if one string), `tests/test_s47.py`, `tests/test_gate.py`, `NICE_TO_HAVE.md`, `RUNBOOK.md` section 5; the README count and its sidecar (`README.md`, `design/readme/source.md`, `design/readme/rendered.sha256`, by hand), since `test_status_line_matches_manifest_and_suite` counts the suite; this packet; the parent's charter, `history/sittings/2026-10-30-4-s47.md`, no new one. Nothing under `plugin/` and no version bump: alpha.32 stands |
| acceptance | `.venv/bin/python -B -m pytest tests/test_s47.py tests/test_gate.py -q 2>&1 \| tail -1` reads `passed`, no `failed`; `.venv/bin/python -B -m pytest tests/test_readme.py tests/test_install.py tests/test_doctor.py -q 2>&1 \| tail -1` reads `passed`, no `failed`; doclint, hygiene and the version check pass |
| verify | the gate, by the coordinator |
| budget | acts: 0 this packet; 1 the tests, red; 2 the code; 3 NICE, RUNBOOK and the count. 45 tool calls, stop at 80% (commit the act in flight), `claude-opus-5-5`; one commit per act |

## 1. What the source says (the refuter's round 1 on 61fd2ad)

- F1, block, `gate.py:227, 297-310`: lock paths compare as strings after `abspath`, so one lock spelled two ways (`/tmp/x/tlc.lock`, `/private/tmp/x/tlc.lock`) runs concurrently before it exists.
- F2, block, `gate.py:206, 170`: on case-insensitive APFS `realpath` keeps the typed case, so one repo gets two keys (`main/.git`, `MAIN/.git`).
- F3, the fallback: an entry with no `key`, or git failing, keys on the repo's realpath while its siblings key on the common dir, so the two run together.
- F4, `gate.py` `_start`: a runner dying between the spawn and the runner.json write leaves the entry queued with no record of its child, and the next runner runs it again; a double run can be two TLC jobs.
- F6, `gate.py` `_reap`: a finished child's group may still hold a background process, which now overlaps the next start of the same key.
- Surviving mutants: `seen` never reset; `repo_key` with no timeout; `entry_key` with no canonical step; a wall of exactly the limit (`>=` to `>`).

## 2. Rulings

1. **F1.** Canonicalise a lock's path at enqueue and again where running entries are compared, so an older entry compares too. A lock's parent may exist while the lock does not: resolve what exists. On this Mac's case-insensitive disk, ruling 2's fix applies to a lock's parent as well.
2. **F2.** The key is the common dir's `(st_dev, st_ino)` when it can be read, written as a string in the entry, with `repo`'s basename beside it for `status`, since the status line names the repo. A path that cannot be statted keeps the realpath form.
3. **F3, the fallback.** This amends the parent's ruling 1. An entry with no `key`, or git failing or timing out, computes the key the same way from `<repo>/.git` when that exists, else from the repo itself, so a fallback and its siblings share a key. A worktree's `.git` is a file: read its `gitdir:` no further than is needed to find the common dir, or fall back to the repo itself and say so in the report.
4. **F4.** Write the entry's id to runner.json before the spawn. `_recover` closes an entry named there with no child as 125, as it does a dead child. Say how the pgid slot reads between the write and the spawn, and pin that recovery cannot kill a wrong group (no pgid means no kill). Pin the crash with the Fx fakes.
5. **F6.** On a normal finish, kill the child's process group before freeing the key, ignoring ESRCH, and close the entry as before: the exit code is the command's, unchanged. Test with a fake, plus one real child that leaves a background grandchild, in a temp state root, killed by the test.
6. **Pins for the survivors that matter.** `seen` never reset (Amendment 1's reset of S38 has no test); `repo_key` with no timeout; `entry_key` with no canonical step; a wall of exactly the limit (`>=` to `>`).
7. **RUNBOOK section 5.** A downgrade while a set runs is unsafe, since an alpha.31 `_recover` cannot read the list form: let the queue drain first. The install note: an alpha.31 runner keeps serving until it idles out, and its `status` may misread a wait.
8. **To `NICE_TO_HAVE.md`, level S4, one line each, keeping the file's shape.** A crash after the result and before the inbox loses the inbox line, though the result stays readable (same on main); a finish's ntfy POST blocks the poll up to its 5 s timeout, against the parent's ruling 5's letter; `start_settle` with a clock set back an hour waits that hour while something runs; a corrupt runner.json with a live child double-runs (same on main); a stale pgid after a reboot could hit another group, by reading only; `gate` help in `cli.py` and `plugin/commands/gate.md` still say one at a time (touch them here only if `cli.py`'s help is one string; a plugin edit needs a version step, so leave it and file it).
9. **The version.** No bump: alpha.32 stands, and nothing moves under `plugin/`.

## 3. Interfaces

`gate run`, `wait` and `status` keep their flags and their exit codes. An entry's `key` is `<st_dev>:<st_ino>` or, when the path cannot be statted, a realpath; an entry gains `key_name`, its repo's basename. An entry's `locks` hold realpaths. `runner.json`'s `running` is `[{id, pgid}]`, and `pgid` reads null for an entry written before its spawn.

## 4. Findings that name this row

F1, F2, F3, F4, F6 and the four mutants of §1; the S4s of ruling 8.

## 5. Forbidden reads

Transcripts; `~/.local/state`; every other repo, but `GUIDE.md`.

## 6. Report (under 10 lines)

Commits; the acceptance lines; forks; anything unmet.

**Amendment 2**, the last review round's rulings on a1a5e69, no further review, same wall and may-touch; budget 20 tool calls; acts: 1 the tests, red; 2 the code; 3 NICE, this paragraph and the count. F2: a lock that is a live symlink at enqueue was stored as its target and waited on it for good, exit 126, so `enqueue` and `lock_key` resolve the parent only and keep the leaf as typed; this moves section 3's `locks` from realpaths to that form. F1: in `lock_key` only, what lies below the deepest existing directory reads NFC and casefolded when `os.pathconf(<that directory>, 11)` reads 0 (`_PC_CASE_SENSITIVE` on Darwin); on OSError or another platform it compares as typed; the stored path and the exists test are unchanged. F7: `_named` also holds the raw strings, so a parent made mid-pass cannot read one spelling as free. Five S4s to `NICE_TO_HAVE.md`, and its line on a lock's case goes. No version bump.
