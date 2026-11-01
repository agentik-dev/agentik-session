.PHONY: help test test-floor venv-floor doctor install skill lint clean check check-unlocked tree-note doclint hygiene plugin-version-check validate readme
# The virtualenv first: `python3` and the scripts' shebangs resolve to it, never Apple's.
export PATH := $(CURDIR)/.venv/bin:$(PATH)
# The newest installed respeak renderer, under either marketplace name.
RESPEAK_RENDER ?= $(shell for f in $(HOME)/.claude/plugins/cache/*/respeak/*/scripts/respeak-render.sh; do \
	v=$${f%/scripts/*}; echo "$${v\#\#*/} $$f"; done | sort -V | tail -1 | cut -d' ' -f2-)
export RESPEAK_PYTHON ?= $(CURDIR)/.venv/bin/python
help:
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | sed 's/:.*## /\t/'
test:  ## run the suite (no quota, fake claude), under .venv and then under .venv-floor, test_bounded.py excepted (design/04 §6)
	./.venv/bin/python -m pytest -q
	@if [ -x .venv-floor/bin/python ]; then $(MAKE) --no-print-directory test-floor; else echo "floor: absent"; fi
# The floor (hq entry 6, design/04): .venv-floor is the suite's venv under the one interpreter
# a fresh Mac and this one share. It is built once in the main checkout, and a worktree links
# it there, as with .venv. `make test` runs it when it is there (sc2 ruling 9).
FLOOR_PYTHON ?= /usr/bin/python3
venv-floor:  ## build .venv-floor under /usr/bin/python3 in the main checkout (pytest from pip), and link it from a worktree
	@set -e; main=$$(git worktree list --porcelain | sed -n '1s/^worktree //p'); \
	if [ ! -x "$$main/.venv-floor/bin/pytest" ]; then \
	  $(FLOOR_PYTHON) -m venv "$$main/.venv-floor"; \
	  "$$main/.venv-floor/bin/python" -m pip install -q --disable-pip-version-check 'pytest>=8'; fi; \
	if [ "$$main" != "$(CURDIR)" ] && [ ! -e .venv-floor ]; then ln -s "$$main/.venv-floor" .venv-floor; fi; \
	echo "venv-floor: $$main/.venv-floor, $$("$$main/.venv-floor/bin/python" --version)"
test-floor:  ## run the suite under .venv-floor, test_bounded.py excepted (scripts/bounded is a 3.11 dev tool, never run time)
	@[ -x .venv-floor/bin/python ] || { echo "test-floor: no .venv-floor; run make venv-floor" >&2; exit 2; }
	PATH="$(CURDIR)/.venv-floor/bin:$$PATH" ./.venv-floor/bin/python -m pytest -q --ignore=tests/test_bounded.py
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
lint:  ## byte-compile everything
	python3 -m compileall -q plugin/lib/claude_session
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
