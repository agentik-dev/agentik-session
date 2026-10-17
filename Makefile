.PHONY: help test doctor install skill lint clean check check-unlocked tree-note doclint hygiene plugin-version-check validate readme
# The virtualenv first: `python3` and the scripts' shebangs resolve to it, never Apple's.
export PATH := $(CURDIR)/.venv/bin:$(PATH)
# The newest installed respeak renderer, under either marketplace name.
RESPEAK_RENDER ?= $(shell for f in $(HOME)/.claude/plugins/cache/*/respeak/*/scripts/respeak-render.sh; do \
	v=$${f%/scripts/*}; echo "$${v\#\#*/} $$f"; done | sort -V | tail -1 | cut -d' ' -f2-)
export RESPEAK_PYTHON ?= $(CURDIR)/.venv/bin/python
help:
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | sed 's/:.*## /\t/'
test:  ## run the suite (no quota, fake claude)
	./.venv/bin/python -m pytest -q
doctor:  ## check the tool, the plugin and its dependencies on this machine
	python3 -m claude_session doctor
# The install's destination and interpreter; a test overrides HOME (or PREFIX) and PYTHON.
# The launcher bakes PYTHON's own link (its directory resolved), never the link's target,
# which can be a versioned Cellar path a `brew upgrade` deletes; a Cellar path is refused (ADV10-5).
PREFIX ?= $(HOME)/.local
PYTHON ?= $(CURDIR)/.venv/bin/python
DOCTOR ?= 1
# The old trees are pruned by scripts/prune-trees, which keeps every tree a live process
# names (a running launcher's PYTHONPATH) and the newest three, and on doubt keeps all (F8).
# agentik-r1 ruling 2: the launcher is agentik-session, claude-session a relative link to it
# until r2; the front door `agentik` is the vendored scripts/agentik (D3). New trees go under
# share/agentik-session (c8); the old share keeps its trees while a launcher uses them.
install:  ## freeze claude_session/ under $(PREFIX)/share/agentik-session/<tree>, launcher agentik-session in $(PREFIX)/bin
	@if [ -n "$$(git status --porcelain -- claude_session)" ]; then \
	  echo "install: claude_session/ is dirty; commit it first (the install is one committed tree)" >&2; exit 2; fi
	@set -e; tree=$$(git rev-parse HEAD:claude_session); \
	share="$(PREFIX)/share/agentik-session"; code="$$share/$$tree"; bin="$(PREFIX)/bin"; \
	py="$(if $(realpath $(dir $(PYTHON))),$(realpath $(dir $(PYTHON)))/$(notdir $(PYTHON)))"; \
	if [ -z "$$py" ] || [ ! -x "$$py" ]; then py=; \
	  for c in /opt/homebrew/bin/python3 python3; do \
	    p=$$(command -v "$$c" 2>/dev/null) || continue; \
	    if "$$p" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' 2>/dev/null; then py=$$p; break; fi; \
	  done; fi; \
	[ -n "$$py" ] || { echo "install: no python3 >= 3.11 (homebrew's or on PATH)" >&2; exit 2; }; \
	case "$$py" in */Cellar/*) echo "install: $$py is a versioned Cellar path (a brew upgrade deletes it); use a venv's or opt/'s link" >&2; exit 2;; esac; \
	mkdir -p "$$share" "$$bin"; \
	if [ ! -d "$$code" ]; then rm -rf "$$code.tmp"; mkdir "$$code.tmp"; \
	  git archive HEAD claude_session | tar -x -C "$$code.tmp"; mv "$$code.tmp" "$$code"; fi; \
	sed -e "s|__CODE__|$$code|" -e "s|__PYTHON__|$$py|" install-wrapper.sh > "$$bin/agentik-session.tmp"; \
	chmod 755 "$$bin/agentik-session.tmp"; mv -f "$$bin/agentik-session.tmp" "$$bin/agentik-session"; \
	rm -f "$$bin/.claude-session.tmp"; ln -s agentik-session "$$bin/.claude-session.tmp"; mv -f "$$bin/.claude-session.tmp" "$$bin/claude-session"; \
	cp scripts/agentik "$$bin/.agentik.tmp"; chmod 755 "$$bin/.agentik.tmp"; mv -f "$$bin/.agentik.tmp" "$$bin/agentik"; \
	"$$py" scripts/prune-trees --share "$$share" --new "$$tree" || echo "install: the prune failed; every old tree kept" >&2; \
	state="$${XDG_STATE_HOME:-$$HOME/.local/state}"; dir="$$state/agentik-session"; \
	[ -e "$$dir" ] || [ ! -e "$$state/claude-code-session" ] || dir="$$state/claude-code-session"; \
	rm -f "$$dir/install-needed"; \
	echo "installed $$bin/agentik-session -> $$code ($$py); $$bin/claude-session links to it; $$bin/agentik"
	@[ "$(DOCTOR)" = 0 ] || { "$(PREFIX)/bin/agentik-session" doctor >/dev/null 2>&1 && echo "doctor: ok" || echo "run: agentik session doctor"; }
skill:  ## symlink the plugin's skill into ~/.claude/skills (without installing the plugin)
	mkdir -p ~/.claude/skills && ln -sfn "$(PWD)/plugin/skills/session" ~/.claude/skills/agentik-session
lint:  ## byte-compile everything
	python3 -m compileall -q claude_session
check:  ## the gate, one per tree (.check.lock), walled at 840 s (inside the relay's 900), held off above load 4 x cores
	scripts/bounded --lock .check.lock --wall 840 --load 4 -- $(MAKE) check-unlocked
tree-note:
	@[ -z "$$(git status --porcelain)" ] || echo "check: note: the tree is dirty; this result is not a function of HEAD (R6 E1)"
check-unlocked: tree-note test lint doclint hygiene plugin-version-check validate  ## the gate unbounded: test, lint, doclint, hygiene, plugin-version-check, validate, the mod's tests, README freshness
	scripts/bounded --wall 60 -- claude plugin test plugin
	@if [ ! -f design/readme/source.md ]; then echo "readme: skipped, absent design/readme/source.md"; \
	elif shasum -c --status design/readme/rendered.sha256 2>/dev/null; then echo "readme: fresh"; \
	else echo "readme: stale, run make readme"; exit 2; fi
readme:  ## render README.md from design/readme/source.md through respeak, technical mode (scripts/readme-render, walled at 2000 s: its budget)
	RESPEAK_RENDER="$(RESPEAK_RENDER)" scripts/bounded --wall 2000 --load 4 -- scripts/readme-render
doclint:  ## the doc gate (conventions §5)
	scripts/doclint
hygiene:  ## the vendored copies' pins, then the public-hygiene scan (conventions §5, §6)
	shasum -a 256 -c --status scripts/vendored.sha256 || { shasum -a 256 -c scripts/vendored.sha256; exit 2; }
	scripts/hygiene
plugin-version-check:  ## a change under plugin/ fails until plugin.json's version moves (GUIDE §7)
	$(PYTHON) scripts/plugin-version-check
validate:  ## claude plugin validate on the plugin (the marketplace is agentik-commons')
	scripts/bounded --wall 60 -- claude plugin validate plugin/
clean:
	rm -rf .pytest_cache **/__pycache__
