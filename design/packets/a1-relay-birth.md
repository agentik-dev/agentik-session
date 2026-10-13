# Packet A1: the agent-relay repo is born

| item | value |
|---|---|
| from | the brief's R25-91 (2) (the names) and "How we trust it" (the types, the invariants), `design/conventions.md` §1 to §5 and §7, `design/overhaul-r1.md` §2.5 (what is the relay plugin's) and §2.6 (the dependency the session declares). The builder reads THIS packet and those sections; the brief's two paragraphs are quoted below and are the only brief text it needs |
| pin | conventions at claude-code-session `main` after S1 merged (the hygiene script is copied from there at that sha). The new repo has no pin: `git init` in `agent-relay`, default branch `main`, first commit by this packet |
| wall | `agent-relay` only, new. No remote is added; nothing is pushed; no other repo is written. example-mac `scripts/sitting-relay` may be read for its verb names only |
| may touch | everything under `agent-relay`, created by this packet: `go.mod` (`module github.com/owner/agent-relay`, the Go version example-app pins), `cmd/relay/main.go`, `internal/relay/{types.go,machine.go,machine_test.go}`, `plugin/.claude-plugin/plugin.json`, `plugin/hooks/hooks.json`, `plugin/hooks/run`, `.claude-plugin/marketplace.json`, `Makefile`, `scripts/hygiene` (byte-identical copy), `scripts/doclint` (copy), `.hygiene-allow`, `.gitignore`, `LICENSE` (MIT, the siblings' text with the same author line), `README.md` (a stub, under 600 bytes: name, one sentence, "design in progress", install line), `design/packets/.keep`, `history/sittings/.keep` |
| acceptance | in the new repo: `go build ./... && go vet ./... && go test ./...; echo $?` reads 0; `make check; echo $?` reads 0; `claude plugin validate plugin/; echo $?` reads 0; `git remote \| wc -l` reads 0; `git log --oneline \| wc -l` reads 3 or more; `cmp scripts/hygiene scripts/hygiene; echo $?` reads 0; `git grep -c -i push -- '*.go' \| wc -l` reads 0; `relay version` prints `relay 0.1.0-dev`; `relay plan --json; echo $?` prints `{"error":"not implemented","verb":"plan"}` and reads 3 |
| budget | 60 turns, 80k context; commit per item (init, module and verbs, plugin and marketplace, checks); checkpoint at 80%; never push, amend or rebase |

## 1. What the source says (quoted)

The brief, R25-91 (2): "The Go relay is the repo `agent-relay`; its plugin is `claude-code-agent-relay`, bundled under `plugin/`. D3 is closed." The brief, "How we trust it": "The driver is Go, and its core is a pure state machine: types `Night`, `Sitting`, `Packet`, `Gate`, and `StopReason`, with every transition a function of (state, event), covered by table tests over the full transition matrix. Effects (git, spawning and streaming claude, tmux, notify, the clock, the filesystem) sit behind interfaces with fakes". "the binary has no push path at all (grep-tested: the string 'push' appears only inside the guard itself)". The brief, the CLI: `relay plan`, `run`, `attach`, `status`, `stop`, `kill`, `resume`, `gate`, `report`, `doctor`, "every verb with `--json`". conventions §1: the layout block; §2: the manifest fields; §4: "table tests over the full matrix of a state machine's transitions; every effect ... behind an interface with a fake"; §7: "`0.x` may break on a minor".

## 2. Rulings

R25-91 (2) as quoted: the repo name is `agent-relay`. D8 is open: the plugin.json `name` is `agent-relay` (the recommendation) unless `design/overhaul-r1.md` §7 D8 reads otherwise at the pin; the marketplace `name` is `agent-relay` either way. R25-91 (4): hygiene in `check` from the first commit. D5: this is an Opus packet. The design (A2) is not this packet's: no state machine logic beyond compiling types and one trivially true table test; no effect implemented.

## 3. Interfaces (signatures, not prose)

- `cmd/relay/main.go`: `relay <verb> [--json] [args]`; verbs `plan run attach status stop kill resume gate report doctor version`; every verb except `version` and `doctor` returns exit 3 and, under `--json`, `{"error":"not implemented","verb":"<verb>"}` on stdout, the same sentence on stderr otherwise. `doctor` checks only: `claude` on PATH, `git` on PATH, `tmux` on PATH; prints one line each, `--json` gives `{"checks":[{"name","ok","detail"}],"ok":bool}`; exit 0 all ok, 2 otherwise. `version` prints `relay 0.1.0-dev`.
- `internal/relay/types.go`: `type Night struct{}`, `type Sitting struct{}`, `type Packet struct{}`, `type Gate struct{}`, `type StopReason string` with the constants the brief lists (`QueueEmpty, CountReached, UntilReached, StreamError, NoProgress, DirtyTree, NoCommit, GateFailedDependency, CeilingKill, OriginMoved, TmuxGone`); `type Event string`; `type State string`; `func Step(s State, e Event) (State, error)` returning `ErrNotImplemented` for every input. `machine_test.go`: one table test asserting `Step` returns `ErrNotImplemented` for a matrix of every declared state and event (the table exists; A2 fills it).
- `plugin/.claude-plugin/plugin.json`: `{"name":"agent-relay","version":"0.1.0","description":"...","author":{"name":"<the siblings' author line>"},"license":"MIT"}`; `plugin/hooks/hooks.json`: `{"hooks":{}}`; `plugin/hooks/run`: the conventions §1 shim, execs `relay hook "$1"` when `relay` is on PATH, else exit 0. `.claude-plugin/marketplace.json`: `{"name":"agent-relay","owner":{"name":"..."},"plugins":[{"name":"agent-relay","source":"./plugin","description":"...","version":"0.1.0"}]}`.
- `Makefile`: `check: test vet doclint hygiene validate`; `test: go test ./...`; `vet: go vet ./...`; `build: go build -o bin/relay ./cmd/relay`; `install: go install ./cmd/relay`; `hygiene`, `doclint`, `validate` as conventions §5.
- `.hygiene-allow` seed: `LICENSE: person`, `go.mod: person` (the module path carries the public handle), `**/*.go: person` (import paths), `design/**: sibling,private`, `history/**: sibling`.

## 4. Findings that name this row

research §2: decisions puts the plugin under `plugin/` with a root marketplace `source: "./plugin"` (the model); respeak's is at the root (not the model). research §3: `claude plugin validate` exists locally; a marketplace may name a relative subdirectory source. The prototype `sitting-relay` (example-mac) has no subcommands (`main()` only): the verb list comes from the brief, not from it.

## 5. Forbidden reads

`example-app` beyond `head -3 go.mod` (for the Go version line), `example-ops`, `example-mac` beyond `scripts/sitting-relay`'s docstring, the other plugin repos beyond `scripts/hygiene`, `scripts/doclint`, `LICENSE` and `.claude-plugin/marketplace.json` in claude-code-session and claude-code-decisions; `~/.claude/projects/`; the brief beyond the paragraphs quoted in §1.

## 6. Report (capped: one table, at most five bullets, under 1,500 words)

The table: each acceptance line, its exit and last output line. Bullets: the commit list with shas; the Go version pinned and why; the hygiene counts of the new repo (numbers); anything `claude plugin validate` complained about and the fix; what was left undone. The last line: `agent-relay` and its head sha; the reminder "no remote; the owner creates it after hygiene is green".
