#!/bin/sh
# claude-session launcher, written by `make install` (ADV6-3).
#
# Runs a frozen copy of the package, `CODE`, extracted from one committed tree of
# claude_session/, under the interpreter baked at install time. `-P` keeps the cwd
# off sys.path and PYTHONPATH is exactly `CODE`, so neither the directory a hook
# fires in nor the live checkout can change what a hook runs. Re-run `make install`
# to pick up a new commit, or when `PYTHON` or `CODE` has gone away: until then a
# `hook` exits 0, so no event fails; `hook SessionStart` says so every session as a
# JSON `systemMessage` on stdout (a hook's stderr is unseen on exit 0: ADV11-5), other
# events once (a marker under the state dir naming the missing path, removed by
# `make install`); other verbs exit 1 (ADV10-5).
CODE="__CODE__"
PYTHON="__PYTHON__"
gone=
[ -x "$PYTHON" ] || gone="$PYTHON"
[ -n "$gone" ] || [ -d "$CODE" ] || gone="$CODE"
if [ -n "$gone" ]; then
    if [ "$1" = hook ]; then
        marker="${XDG_STATE_HOME:-$HOME/.local/state}/claude-code-session/install-needed"
        if [ "$2" = SessionStart ]; then
            esc=$(printf '%s' "$gone" | sed 's/[\\"]/\\&/g')
            printf '{"systemMessage": "claude-session: %s is gone; run make install"}\n' "$esc"
            mkdir -p "${marker%/*}" && printf '%s\n' "$gone" > "$marker"
        elif [ "$(cat "$marker" 2>/dev/null)" != "$gone" ]; then
            echo "claude-session: $gone is gone; run make install" >&2
            mkdir -p "${marker%/*}" && printf '%s\n' "$gone" > "$marker"
        fi
        exit 0
    fi
    echo "claude-session: $gone is gone; run make install" >&2
    exit 1
fi
PYTHONPATH="$CODE" exec "$PYTHON" -P -m claude_session "$@"
