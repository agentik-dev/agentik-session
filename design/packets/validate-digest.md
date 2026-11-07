# Packet validate-digest: the bare proof's validate row masks the plugin digest

| item | value |
|---|---|
| from | a reproduced S2: Claude Code 2.1.319 prints a content line `Digest: sha256-<base64>=` in `claude plugin validate <dir>` (on main, `claude plugin validate plugin` prints it before `Validation passed`). `scripts/bare-proof`'s `validate()` runs validate on the unpacked live plugin and on the mock's tree and requires the outputs byte-identical once the path reads `<root>`; the two digests differ, so the row reads `FAIL validate ... the outputs differ; first difference: Digest: sha256-...`, and `tests/test_bare_machine.py::test_the_bare_machine_proof_on_the_moved_tree` fails (a gate of 2026-11-07: 1 failed, 2458 passed). The failure is the environment's, not a branch's |
| pin | `main` at `399e6de`; branch `fix/validate-digest`, worktree `.claude/worktrees/validate-digest`, off main; a hand-run helper |
| wall | this repo only. No push, merge, `--amend`, rebase, network or install; no `make` (the landing runs `make check` through the gate). Never build or run a relay binary; never run `relay` or `agentik relay` `run`, `plan`, `gate`, `stop`, `kill`, `clean` or `resume`; never write inside `~/.local/state/agent-relay`. `.venv` is a symlink to the main checkout's |
| may touch | `scripts/bare-proof`, `design/packets/validate-digest.md`, `history/sittings/*.md`, `history/sessions/NEXT`. Nothing else |
| acceptance | `grep -c -F 'DIGEST = re.compile(r"^Digest: sha256-[A-Za-z0-9+/=]+$")' scripts/bare-proof` reads `1` (on main: `0`); `grep -c -F 'digest lines masked' scripts/bare-proof` reads `1` (on main: `0`); `.venv/bin/python -m pytest tests/test_bare_machine.py::test_the_bare_machine_proof_on_the_moved_tree` passes under Claude Code 2.1.319 (on main: fails) |
| budget | 30 turns, 100k context, `claude-opus-5-5`; one helper sitting; two commits, this packet first |
| verify | `make check` |

## 1. What the source says

- `validate()` (scripts/bare-proof) runs `claude plugin validate` twice, on `$T/live/plugin` (a `git archive HEAD plugin`) and on the mock's root, masks each path as `<root>`, and passes only when both exit 0, count the same warnings and print the same bytes.
- 2.1.319 adds one line, `Digest: sha256-<base64>`, a hash of the plugin directory's contents. The mock's root is not the archive: the proof rewrites its `lib/agentik-session` with the watching runner (design/04 §2), and the hook runs before `validate` leave their own files under it, so its digest is not the live copy's by design.

## 2. Rulings

1. A line that is wholly `Digest: sha256-<base64>` (`DIGEST`, a full-line match) is dropped from each output before the comparison, as the path is masked. Nothing else is masked or loosened.
2. The row stays honest about what it compared: its text names how many digest lines it masked in each output (`digest lines masked N and M`), and the row passes only when the two counts are equal, so a digest printed on one side alone is still a difference.
3. No unit test is added: the repo tests this comparison only through the whole proof (`test_the_bare_machine_proof_on_the_moved_tree`), which is this packet's evidence. No plugin version bump: nothing under `plugin/` changes.

## 3. Interfaces

`scripts/bare-proof`'s flags, exits and other rows are unchanged; the validate row's text gains `, digest lines masked N and M`. An output that differs in any line other than the digest still reads `the outputs differ; first difference: ...` and fails.

## 4. Findings that name this row

None beyond the S2 above. Why 2.1.319 prints a digest in `validate` is the CLI's; this packet only stops it from breaking the comparison.

## 5. Forbidden reads

Transcripts; anything under `~/.local/state` or `~/.claude/projects`; any other repo.

## 6. Report

At most eight lines: the branch and its head; the validate row's text and the proof's last line from `./scripts/bare-proof --transcript tests/fixtures/meter/under-80.jsonl`; `scripts/hygiene`'s result; the cause of the digest difference.
