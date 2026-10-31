#!/bin/sh
# agentik-session launcher, written by `make install` (ADV6-3); `claude-session`, its
# pre-rename name, is a link to it until r2 (agentik-r1 §4.3).
#
# Runs a frozen copy of the package, `CODE`, extracted from one committed tree of
# plugin/lib/claude_session/, under the interpreter baked at install time. `-P` keeps the cwd
# off sys.path and PYTHONPATH is exactly `CODE`, so neither the directory a hook
# fires in nor the live checkout can change what a hook runs. Re-run `make install`
# to pick up a new commit, or when `PYTHON` or `CODE` has gone away: until then a
# `hook` exits 0, so no event fails; `hook SessionStart` says so every session as a
# JSON `systemMessage` on stdout (a hook's stderr is unseen on exit 0: ADV11-5), other
# events once (a marker under the state dir naming the missing path, removed by
# `make install`); other verbs exit 1 (ADV10-5). The marker's folder is agentik-r1 §6.3's
# c1 pick: the new state folder when it exists, else the old one when it exists, else new.
CODE="__CODE__"
PYTHON="__PYTHON__"
# Under the old name, on a terminal, for a verb other than `hook`: one note (§4.3).
if [ "${0##*/}" = claude-session ] && [ -t 2 ] && [ "$1" != hook ]; then
    echo "claude-session: renamed; use 'agentik session …' (ends 2026-12-31)" >&2
fi
gone=
[ -x "$PYTHON" ] || gone="$PYTHON"
[ -n "$gone" ] || [ -d "$CODE" ] || gone="$CODE"
if [ -n "$gone" ]; then
    if [ "$1" = hook ]; then
        state="${XDG_STATE_HOME:-$HOME/.local/state}"
        dir="$state/agentik-session"
        [ -e "$dir" ] || [ ! -e "$state/claude-code-session" ] || dir="$state/claude-code-session"
        marker="$dir/install-needed"
        if [ "$2" = SessionStart ]; then
            esc=$(printf '%s' "$gone" | sed 's/[\\"]/\\&/g')
            printf '{"systemMessage": "agentik-session: %s is gone; run make install"}\n' "$esc"
            mkdir -p "${marker%/*}" && printf '%s\n' "$gone" > "$marker"
        elif [ "$(cat "$marker" 2>/dev/null)" != "$gone" ]; then
            echo "agentik-session: $gone is gone; run make install" >&2
            mkdir -p "${marker%/*}" && printf '%s\n' "$gone" > "$marker"
        fi
        exit 0
    fi
    echo "agentik-session: $gone is gone; run make install" >&2
    exit 1
fi
PYTHONPATH="$CODE" exec "$PYTHON" -P -m claude_session "$@"
