.PHONY: help test test-floor venv-floor venv doctor install skill lint clean check check-unlocked tree-note doclint hygiene plugin-version-check validate readme stamp
# The virtualenv first: `python3` and the scripts' shebangs resolve to it, never Apple's.
export PATH := $(CURDIR)/.venv/bin:$(PATH)
# The newest installed respeak renderer, under either marketplace name.
RESPEAK_RENDER ?= $(shell for f in $(HOME)/.claude/plugins/cache/*/respeak/*/scripts/respeak-render.sh; do \
	v=$${f%/scripts/*}; echo "$${v\#\#*/} $$f"; done | sort -V | tail -1 | cut -d' ' -f2-)
export RESPEAK_PYTHON ?= $(CURDIR)/.venv/bin/python
help:
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | sed -e 's/:.*## /\t/' \
	  -e 's|\$$(WORKERS)|$(WORKERS)|g' -e 's|\$$(VENV_PYTHON)|$(VENV_PYTHON)|g'
# The workers (ck2): each pass runs on $(WORKERS) pytest-xdist workers where its venv holds the
# runner, else in one process as before, and says `workers: absent in <venv>` after it. A fixed
# number, measured (design/packets/ck2-test-workers.md): two passes share the cores and the gate
# holds a job above a load of 12, so never `auto`. `make test WORKERS=6` overrides it; a WORKERS
# in the caller's environment does not (a plain `=`, review 1's L1).
WORKERS = 4
test:  ## run the suite (no quota, fake claude), under .venv and .venv-floor side by side, each on $(WORKERS) workers where it holds pytest-xdist, test_bounded.py excepted in the floor (design/04 §6)
	@w=$$(./.venv/bin/python -c 'import xdist' >/dev/null 2>&1 && echo "-n $(WORKERS)"); \
	if [ ! -x .venv-floor/bin/python ]; then ./.venv/bin/python -m pytest -q $$w; main=$$?; \
	  [ -n "$$w" ] || echo "workers: absent in .venv"; [ $$main = 0 ] && echo "floor: absent"; exit $$main; fi; \
	log=$$(mktemp -t agentik-floor) || exit 2; \
	$(MAKE) --no-print-directory test-floor > "$$log" 2>&1 & floor=$$!; \
	./.venv/bin/python -m pytest -q $$w; main=$$?; [ -n "$$w" ] || echo "workers: absent in .venv"; \
	wait $$floor; fl=$$?; cat "$$log"; rm -f "$$log"; \
	[ $$main = 0 ] || echo "test: the .venv pass failed, exit $$main" >&2; \
	[ $$fl = 0 ] || echo "test: the .venv-floor pass failed, exit $$fl" >&2; \
	[ $$main = 0 ] && [ $$fl = 0 ]
# The floor (hq entry 6, design/04): .venv-floor is the suite's venv under the one interpreter
# a fresh Mac and this one share. It is built once in the main checkout, and a worktree links
# it there, as with .venv. `make test` runs it when it is there (sc2 ruling 9).
FLOOR_PYTHON ?= /usr/bin/python3
# The runner (ck2 R1): pytest-xdist, installed where a venv holds pytest and not the runner.
RUNNER ?= pytest-xdist>=3
venv-floor:  ## build .venv-floor under /usr/bin/python3 in the main checkout (pytest and pytest-xdist from pip), add pytest-xdist where it holds pytest alone, and link it from a worktree
	@set -e; main=$$(git worktree list --porcelain | sed -n '1s/^worktree //p'); \
	if [ ! -x "$$main/.venv-floor/bin/pytest" ]; then \
	  $(FLOOR_PYTHON) -m venv "$$main/.venv-floor"; \
	  "$$main/.venv-floor/bin/python" -m pip install -q --disable-pip-version-check 'pytest>=8' '$(RUNNER)'; \
	elif ! "$$main/.venv-floor/bin/python" -c 'import xdist' >/dev/null 2>&1; then \
	  "$$main/.venv-floor/bin/python" -m pip install -q --disable-pip-version-check '$(RUNNER)'; fi; \
	if [ "$$main" != "$(CURDIR)" ] && [ ! -e .venv-floor ]; then ln -s "$$main/.venv-floor" .venv-floor; fi; \
	echo "venv-floor: $$main/.venv-floor, $$("$$main/.venv-floor/bin/python" --version)"
# .venv, the same shape: built once in the main checkout under $(VENV_PYTHON) where it is absent.
VENV_PYTHON ?= python3.12
venv:  ## build .venv under $(VENV_PYTHON) in the main checkout (pytest and pytest-xdist from pip), add pytest-xdist where it holds pytest alone, and link it from a worktree
	@set -e; main=$$(git worktree list --porcelain | sed -n '1s/^worktree //p'); \
	if [ ! -x "$$main/.venv/bin/pytest" ]; then \
	  $(VENV_PYTHON) -m venv "$$main/.venv"; \
	  "$$main/.venv/bin/python" -m pip install -q --disable-pip-version-check 'pytest>=8' '$(RUNNER)'; \
	elif ! "$$main/.venv/bin/python" -c 'import xdist' >/dev/null 2>&1; then \
	  "$$main/.venv/bin/python" -m pip install -q --disable-pip-version-check '$(RUNNER)'; fi; \
	if [ "$$main" != "$(CURDIR)" ] && [ ! -e .venv ]; then ln -s "$$main/.venv" .venv; fi; \
	echo "venv: $$main/.venv, $$("$$main/.venv/bin/python" --version)"
test-floor:  ## run the suite under .venv-floor, on $(WORKERS) workers where it holds pytest-xdist, test_bounded.py excepted (scripts/bounded is a 3.11 dev tool, never run time); no .pytest_cache, which the .venv pass beside it writes
	@[ -x .venv-floor/bin/python ] || { echo "test-floor: no .venv-floor; run make venv-floor" >&2; exit 2; }
	@w=$$(./.venv-floor/bin/python -c 'import xdist' >/dev/null 2>&1 && echo "-n $(WORKERS)"); \
	echo "PATH=\"$(CURDIR)/.venv-floor/bin:\$$PATH\" ./.venv-floor/bin/python -m pytest -q -p no:cacheprovider --ignore=tests/test_bounded.py $$w"; \
	PATH="$(CURDIR)/.venv-floor/bin:$$PATH" ./.venv-floor/bin/python -m pytest -q -p no:cacheprovider --ignore=tests/test_bounded.py $$w; \
	fl=$$?; [ -n "$$w" ] || echo "workers: absent in .venv-floor"; exit $$fl
doctor:  ## check the tool, the plugin and its dependencies on this machine
	PYTHONPATH=plugin/lib python3 -m claude_session doctor
# The install's destination; a test overrides HOME or PREFIX. For a developer: the one guard a
# clone can give, then the plugin's own verb, which holds the launcher's template and writes the
# frozen tree, the launcher, its old-name link and the door (design/04 §6).
PREFIX ?= $(HOME)/.local
PYTHON ?= $(CURDIR)/.venv/bin/python
DOCTOR ?= 1
install:  ## refuse a dirty plugin tree, then the plugin's install-cli: freeze under $(PREFIX)/share/agentik-session/<hash>, launcher agentik-session in $(PREFIX)/bin
	@if [ -n "$$(git status --porcelain --ignored=matching -- plugin/lib plugin/bin/agentik plugin/.claude-plugin/plugin.json | grep -vE '/(__pycache__/|\.DS_Store)$$|\.pyc$$')" ]; then \
	  echo "install: plugin/lib, plugin.json or the door is dirty; commit it first (the install is one committed tree)" >&2; exit 2; fi
	@plugin/bin/agentik-session install-cli --prefix "$(PREFIX)"
	@[ "$(DOCTOR)" = 0 ] || { "$(PREFIX)/bin/agentik-session" doctor >/dev/null 2>&1 && echo "doctor: ok" || echo "run: agentik session doctor"; }

skill:  ## symlink the plugin's skill into ~/.claude/skills (without installing the plugin)
	mkdir -p ~/.claude/skills && ln -sfn "$(PWD)/plugin/skills/session" ~/.claude/skills/agentik-session
lint:  ## byte-compile everything, then the README's top (GUIDE §10)
	python3 -m compileall -q plugin/lib/claude_session
	scripts/readme-top
check:  ## the gate, one per tree (.check.lock), walled at 1800 s (the owner's ruling of 2026-11-10; a relay row's own wall, relay.verify_seconds in .claude/agentik/config.yaml, must allow it), held off above load 4 x cores
	scripts/bounded --lock .check.lock --wall 1800 --load 4 -- $(MAKE) check-unlocked
tree-note:
	@[ -z "$$(git status --porcelain)" ] || echo "check: note: the tree is dirty; this result is not a function of HEAD (R6 E1)"
check-unlocked: tree-note test lint doclint hygiene plugin-version-check validate  ## the gate unbounded: test, lint, doclint, hygiene, plugin-version-check, validate, the mod's tests, README freshness
	scripts/bounded --wall 60 -- claude plugin test plugin
	@if [ ! -f design/readme/source.md ]; then echo "readme: skipped, absent design/readme/source.md"; \
	elif shasum -c --status design/readme/rendered.sha256 2>/dev/null; then echo "readme: fresh"; \
	else echo "readme: stale, run make readme"; exit 2; fi
readme:  ## render README.md from design/readme/source.md through respeak, technical mode (scripts/readme-render, walled at 2000 s: its budget)
	RESPEAK_RENDER="$(RESPEAK_RENDER)" scripts/bounded --wall 2000 --load 4 -- scripts/readme-render
doclint:  ## the doc gate (conventions §5), then HANDOFF.md and NICE_TO_HAVE.md against their tables (hq design/05 §4)
	scripts/doclint
	scripts/recordlint
hygiene:  ## the vendored copies' pins, then the public-hygiene scan (conventions §5, §6)
	shasum -a 256 -c --status scripts/vendored.sha256 || { shasum -a 256 -c scripts/vendored.sha256; exit 2; }
	scripts/hygiene
plugin-version-check:  ## a change under plugin/ fails until plugin.json's version moves (GUIDE §7)
	$(PYTHON) scripts/plugin-version-check
# The landing's derived lines, after a branch merges main (hq design/19's land3); check never calls it.
STAMP_BASE ?= main
stamp:  ## after merging $(STAMP_BASE): plugin.json's version, the README's count, the sidecar, NICE rows past the bound; reds a merge whose count lost a test (STAMP_VERSION= names the version)
	$(PYTHON) scripts/stamp --base "$(STAMP_BASE)"$(if $(STAMP_VERSION), --version "$(STAMP_VERSION)")
validate:  ## claude plugin validate on the plugin (the marketplace is agentik-commons')
	scripts/bounded --wall 60 -- claude plugin validate plugin/
clean:
	rm -rf .pytest_cache **/__pycache__
