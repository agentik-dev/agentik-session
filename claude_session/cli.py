"""agentik-session — verbs, argument parsing, and all the printing.

Every sys.exit lives in this module; everything below it returns values.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
import time

from . import (admission, charter, doctor, gitinfo, hooks, launch, ledger, measure, meter, mod,
               resolver, rules, sessionconfig, store)
from . import SEMVER
from .yamlsubset import dump
from .sessionconfig import (IN_SESSION_EQUIVALENT, LAUNCH_ONLY, LIVE,
                            SETTABLE, SessionConfig)


def _die(msg: str, code: int = 1):
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(code)


def cmd_budget(args) -> int:
    cfg, zone = hooks.state()
    cadence = (cfg.checkpoint or {}).get(zone, 0)
    print(f"zone       {zone}")
    print(f"posture    {cfg.posture}")
    print("cadence    " + (f"checkpoint every {cadence} prompts" if cadence
                           else "no checkpoint nudge in this zone"))
    for z, n in sorted((cfg.checkpoint or {}).items()):
        print(f"           {z:<10} every {n}")
    return 0


def cmd_hook(args) -> int:
    return hooks.dispatch(args.event)



# --- session configurations -------------------------------------------------

def _positive_int(v: str) -> int:
    if not v.strip().isdigit() or int(v) <= 0:
        raise argparse.ArgumentTypeError(f"{v!r} is not a positive integer")
    return int(v)


def cmd_start(args) -> int:
    configs = sessionconfig.load_configs()
    cfg = configs.get(args.config)
    if not cfg:
        _die(f"unknown configuration {args.config!r}. Known: "
             f"{', '.join(sorted(configs))}  (agentik session config list)")
    here = launch.depth(os.environ)
    if here is None:
        _die(f"{launch.DEPTH_VAR}={os.environ[launch.DEPTH_VAR]!r} is not a depth; "
             "refusing to start (unset it at a terminal).", 2)
    child = here + 1
    if child > launch.MAX_DEPTH and not args.nested:
        _die(f"this would start a session at depth {child} ({launch.DEPTH_VAR}="
             f"{child - 1} here); a started session does not start another. "
             "Pass --nested to allow it.", 2)
    try:
        l = launch.build(cfg, args.claude_args)
    except (launch.LaunchError, ValueError) as e:
        _die(str(e))
    l.env[launch.DEPTH_VAR] = str(child)
    if args.max_turns is not None:
        # review r6 E5: the meter's turn ceiling follows N. claude's own --max-turns works
        # in print mode only and defaults to no limit (Claude Code's "CLI reference", as of
        # 2026-10-14), so in an interactive start only the meter's ceiling and its rule apply.
        l.argv += ["--max-turns", str(args.max_turns)]
        l.env[resolver.MAX_TURNS_VAR] = str(args.max_turns)
    for w in l.warnings:
        print(f"warning: {w}", file=sys.stderr)
    if args.dry_run:
        print(l.shell_preview())
        return 0
    sessionconfig.set_active(cfg.name)
    launch.exec_launch(l)
    return 0            # not reached


def _fmt_value(v):
    if isinstance(v, (dict, list)):
        return json.dumps(v, sort_keys=True)
    return "-" if v is None else str(v)


def cmd_doctor(args) -> int:
    rep = doctor.run()
    print(json.dumps(rep.as_dict(), indent=2) if args.json else doctor.render(rep))
    return 0 if rep.ok else 2


def cmd_status(args) -> int:
    """The session's meter: one line, or meter.json with --json."""
    env = os.environ
    state = resolver.state_dir(env)
    if args.transcript:
        stem = os.path.splitext(os.path.basename(args.transcript))[0]
        limits = meter.limits_for(resolver.session_dir(state, stem), env)
        m = meter.parse(args.transcript, {}, limits)
        if m is None:
            _die(f"transcript unreadable: {args.transcript}", 2)
        d = m.as_dict()
    else:
        sid = sessionconfig.session_id() or resolver.newest_session(state)
        sdir = resolver.session_dir(state, sid) if sid else None
        d = meter.load(sdir) if sdir else None
        if not d:
            print("no meter for this session: PostToolUse has not run (see "
                  "`agentik session doctor`)", file=sys.stderr)
            return 2
        if not args.json:
            print(meter.one_line(d))
            print(f"measure: {measure.line(sdir)}")   # the engine's figure beside it (mod-r1 S2)
            print(f"mod: {mod.line(sdir)}")     # the band's module, seen or not (mod-r1 §4)
            return 0
    print(json.dumps(d, indent=2) if args.json else meter.one_line(d))
    return 0


def cmd_mod(args) -> int:
    """`mod start`: the hooks module's one verb; mod.json written, the session dir printed."""
    try:
        sdir = mod.start(args.session, os.environ)
    except mod.ModError as e:
        print(f"agentik-session: {e}", file=sys.stderr)
        return e.code
    print(json.dumps({"dir": str(sdir)}))
    return 0


def _stdin() -> str | None:
    """stdin's text for the two record verbs, or None when it is not UTF-8 (M2's fix round,
    F2): the verb then refuses, exit 2, and writes nothing."""
    try:
        return sys.stdin.read()
    except UnicodeDecodeError:
        print("agentik-session: stdin is not UTF-8; nothing written", file=sys.stderr)
        return None


def cmd_admission(args) -> int:
    """`admission record`: one line on the machine's admission ledger (admission-r1, S25);
    `admission admit`: the verdict on one spawn, its line appended and its answer printed
    as JSON (S26, observe: it never refuses a spawn)."""
    text = _stdin()
    if text is None:
        return 2
    try:
        if args.admission_verb == "admit":
            answer = admission.admit(args.session, text, os.environ)
            print(json.dumps(answer, ensure_ascii=False))
            for note in answer.get("notes", ()):
                print(f"agentik-session: {note}", file=sys.stderr)
        else:
            admission.record(args.session, text, os.environ)
    except admission.AdmissionError as e:
        print(f"agentik-session: {e}", file=sys.stderr)
        return e.code
    except OSError as e:                  # the disk, not the content: retry, as the lock
        msg = " ".join(f"admission: {e}".split())[:200]
        print(f"agentik-session: {msg}; nothing written", file=sys.stderr)
        return 3
    return 0


def cmd_measure(args) -> int:
    """`measure record`: the engine's session.measure as measure.json (mod-r1 S2, packet M2)."""
    text = _stdin()
    if text is None:
        return 2
    try:
        measure.record(args.session, text, os.environ)
    except measure.MeasureError as e:
        print(f"agentik-session: {e}", file=sys.stderr)
        return e.code
    return 0


def cmd_report(args) -> int:
    """The ledger, one row per ended session; then admission's five-hour windows."""
    if args.since:
        try:
            time.strptime(args.since, "%Y-%m-%d")
        except ValueError:
            _die(f"--since wants YYYY-MM-DD, not {args.since!r}")
    if args.chains:
        rows = ledger.read_chains(resolver.state_dir(os.environ), args.since)
        if not rows:
            print("the ledger holds no chain lines" + (f" since {args.since}" if args.since
                                                       else ""), file=sys.stderr)
            return 2
        print(json.dumps(rows, indent=2) if args.json else ledger.chain_table(rows))
        return 0
    rows = ledger.read(resolver.state_dir(os.environ), args.since)
    # The admission section (packet S27b ruling 5) follows the plain table, and stands alone
    # when the session ledger is empty: an idle window is reported, never hidden (§3.6).
    if not rows:
        print("the ledger is empty" + (f" since {args.since}" if args.since else ""),
              file=sys.stderr)
        if not args.json:
            print(admission.report(os.environ))
        return 2
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    print(ledger.table(rows))
    print()
    print(admission.report(os.environ))
    return 0


def _session_section(cwd: str) -> dict:
    """The resolved `session` section: this session's resolved.json, else resolved
    now from `cwd` (nothing written)."""
    state = resolver.state_dir(os.environ)
    sid = sessionconfig.session_id()
    if sid:
        try:
            d = json.loads((resolver.session_dir(state, sid) / "resolved.json").read_text())
            if isinstance(d.get("session"), dict):
                return d["session"]
        except (OSError, ValueError, AttributeError):
            pass
    try:
        r = resolver.resolve(cwd, sid or "unsaved", os.environ,
                             profile=hooks.launch_profile(os.environ))
    except resolver.ResolveError as e:
        _die(str(e), 2)
    return r.sections["session"]


def _charter_dir(section: dict) -> str:
    c = section.get("charter")
    return (c.get("dir") if isinstance(c, dict) else None) or charter.DEFAULT_DIR


def _this_meter() -> dict | None:
    state = resolver.state_dir(os.environ)
    sid = sessionconfig.session_id()
    return meter.load(resolver.session_dir(state, sid)) if sid else None


def _rules_section(cwd: str) -> dict | None:
    """The `session` section resolved from cwd for the charter's warnings (S21); None
    when the resolve fails in any way, as SessionStart's does, so a failed resolve warns
    nothing and the exit is unchanged (round one F1: a layer of the wrong shape)."""
    try:
        return resolver.resolve(cwd, sessionconfig.session_id() or "unsaved", os.environ,
                                profile=hooks.launch_profile(os.environ)).sections["session"]
    except Exception:                                   # noqa: BLE001
        return None


def _warn(path, section: dict | None) -> None:
    if section is None:
        return
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return
    for w in charter.warnings(raw, section):
        print(f"{path}: warning: {w}", file=sys.stderr)


def cmd_rules(args) -> int:
    """The priority and pacing this session meets, as resolved (S21)."""
    sys.stdout.write(rules.render(_session_section(os.getcwd())))
    return 0


def cmd_charter(args) -> int:
    """The sitting's charter: open, check, close (the shape of D10)."""
    if args.action == "check":
        if not args.args:
            _die("charter check wants at least one file")
        bad = 0
        section = _rules_section(os.getcwd())
        for f in args.args:
            try:
                refusals = charter.check(f)
            except OSError as e:
                _die(f"{f}: {e.strerror or e}")
            for r in refusals:
                print(f"{f}: refused: {r}", file=sys.stderr)
            bad += bool(refusals)
            _warn(f, section)
        return 2 if bad else 0
    cwd = os.getcwd()
    if args.action == "open":
        if len(args.args) != 1:
            _die('charter open wants one goal: agentik-session charter open "<goal>"')
        section = _session_section(cwd)
        rc, top = gitinfo._git(cwd, "rev-parse", "--show-toplevel")
        rc2, head = gitinfo._git(cwd, "rev-parse", "--short", "HEAD")
        path = charter.open(args.dir or _charter_dir(section), args.args[0], section,
                            head.strip() if rc2 == 0 else None,
                            repo=os.path.basename(top.strip()) if rc == 0 else None,
                            row=os.environ.get("RELAY_ROW"))
        print(path)
        return 0
    if len(args.args) > 1:
        _die("charter close takes at most one file")
    if args.args:
        path = args.args[0]
    else:
        d = args.dir or _charter_dir(_session_section(cwd))
        path = charter.newest_today(d)
        if path is None:
            _die(f"no charter for today under {d}", 2)
    try:
        charter.close(path, args.exit or "goal met", _this_meter())
    except OSError as e:
        _die(f"{path}: {e.strerror or e}")
    except charter.CharterError as e:
        print(f"{path}: refused: {e}", file=sys.stderr)
        return 2
    _warn(path, _rules_section(cwd))
    print(path)
    # Packet S22: the exit line is written, so name what takes it (a commit) and, on a
    # RESPAWN close, the checkpoint that marks it; callers read the path, first.
    if _charter_dirty(str(path)):
        print(f"next: {_commit_line(str(path))}")
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            line = charter.next_act_line(fh.read())
    except OSError:
        line = None
    if line is not None and charter.RESPAWN.match(line):
        print("then: agentik-session checkpoint --respawn --charter "
              + shlex.quote(os.path.abspath(path)))
    return 0


def _commit_line(path: str) -> str:
    """The line that commits the charter, run verbatim from any cwd (S22 fix round, F1
    and F2): `git -C <its dir> add` takes an untracked one, and `-C` the absolute
    directory reaches its own repo from another one."""
    d, name = (shlex.quote(p) for p in os.path.split(os.path.abspath(path)))
    return (f"git -C {d} add -- {name} && "
            f'git -C {d} commit -m "charter: the exit taken" -- {name}')


def _charter_dirty(path: str) -> bool | None:
    """Packet S22: True when `git status --porcelain` reads a line for the charter
    (modified, staged or untracked), False clean, None unknown or outside a work tree."""
    st = gitinfo.path_state(path)
    return None if st is None or st is gitinfo._NOT_A_REPO else bool(st)


def _show_resolved() -> int:
    """This session's resolved file; the newest one when no session id is set."""
    state = resolver.state_dir(os.environ)
    sid = sessionconfig.session_id()
    if not sid:
        sid = resolver.newest_session(state)
        if sid:
            print(f"note: $CLAUDE_CODE_SESSION_ID unset; showing the newest session, {sid}",
                  file=sys.stderr)
    path = resolver.session_dir(state, sid) / "resolved.yaml" if sid else None
    if path and path.exists():
        sys.stdout.write(path.read_text())
        return 0
    try:
        r = resolver.resolve(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd(),
                             sid or "unsaved", os.environ,
                             profile=hooks.launch_profile(os.environ))
    except resolver.ResolveError as e:
        _die(str(e), 2)
    print("note: no resolved file for this session (SessionStart did not write one); "
          "resolved now, not saved", file=sys.stderr)
    sys.stdout.write(dump(r.as_dict()))
    return 0


def cmd_profile(args) -> int:
    try:
        defaults, profiles = resolver.load_profiles(os.environ)
    except resolver.ResolveError as e:
        _die(str(e), 2)
    if not args.name:
        for name, body in profiles.items():
            eff = {**defaults, **(body or {})}
            print(f"{name:<17} {str(eff.get('model')):<14} {str(eff.get('effort')):<7} "
                  f"sub={str(eff.get('subagents')):<14} {str(eff.get('posture')):<7} "
                  f"{eff.get('description') or ''}")
        return 0
    if args.name not in profiles:
        _die(f"unknown profile {args.name!r}. Known: {', '.join(profiles)}")
    try:
        r = resolver.resolve(os.getcwd(), "profile", os.environ, profile=args.name,
                             overlay={})
    except resolver.ResolveError as e:
        _die(str(e), 2)
    sys.stdout.write(dump({k: v for k, v in r.sections.items()}))
    return 0


def cmd_config(args) -> int:
    if args.action == "show" and args.resolved:
        return _show_resolved()
    configs = sessionconfig.load_configs()

    if args.action == "list":
        active = sessionconfig.get_active()
        for name, c in sorted(configs.items()):
            mark = "*" if name == active else " "
            lane = c.lane if c.lane != "seat" else ""
            print(f"{mark} {name:<12} {(c.model or 'inherit'):<14} "
                  f"{(c.effort or '-'):<7} sub={(c.subagent_model or '-'):<14} "
                  f"{c.posture:<7} {lane:<10} {c.description}")
        if active:
            print(f"\n* = active in this session")
        return 0

    if args.action == "show":
        # With no name, show what is actually in force for this session --
        # config plus overlay. With an explicit name, show that stored config,
        # and still apply the overlay when it is the one running.
        active = sessionconfig.get_active() or "balanced"
        name = args.name or active
        cfg = configs.get(name)
        if not cfg:
            _die(f"unknown configuration {name!r}. Known: "
                 f"{', '.join(sorted(configs))}")
        ov = {} if args.stored else (
            sessionconfig.load_overlay() if name == active else {})
        eff = cfg.merged(ov)
        print(f"{eff.name}: {eff.description}")
        for f in sorted(SessionConfig.__dataclass_fields__):
            if f in ("name", "description"):
                continue
            base_v, eff_v = getattr(cfg, f), getattr(eff, f)
            flag = ("" if base_v == eff_v else
                    f"   <- session only; stored: {_fmt_value(base_v)}")
            print(f"  {f:<16} {_fmt_value(eff_v)}{flag}")
        try:
            print(f"\n`start {cfg.name}` launches as (stored config; a session-only "
                  "overlay never reaches a launch):\n  " + launch.build(cfg).shell_preview())
        except (launch.LaunchError, ValueError) as e:
            print(f"\ncannot launch: {e}")
        live_ov = {k for k in ov if k in LIVE}
        if live_ov:
            print(f"\nin force for THIS session only: {', '.join(sorted(live_ov))}")
        return 0

    if args.action == "delete":
        if not args.name:
            _die("which configuration?")
        if args.name not in configs:
            _die(f"unknown configuration {args.name!r}")
        del configs[args.name]
        sessionconfig.save_configs(configs)
        print(f"deleted {args.name}"
              + (" (a shipped default of that name will reappear)"
                 if args.name in {c.name for c in sessionconfig.DEFAULTS} else ""))
        return 0

    if args.action == "new":
        if not args.name:
            _die("name the new configuration")
        base = configs.get(args.From) if args.From else None
        if args.From and not base:
            _die(f"unknown configuration {args.From!r} to copy from")
        from dataclasses import replace as _replace
        cfg = _replace(base, name=args.name) if base else SessionConfig(name=args.name)
        if args.description:
            cfg.description = args.description
        configs[args.name] = cfg
        sessionconfig.save_configs(configs)
        print(f"created {args.name}"
              + (f" from {args.From}" if args.From else "")
              + f"; adjust it with `agentik session set <key> <value> --config {args.name}`")
        return 0
    return 0


def _coerce(key: str, raw: str):
    field = SessionConfig.__dataclass_fields__.get(key)
    if field is None:
        return raw
    if key == "reserve_pct":
        try:
            return float(raw)
        except ValueError:
            _die("reserve_pct must be a number")
    if key in ("plugins", "add_dirs"):
        return [x.strip() for x in raw.split(",") if x.strip()]
    if key in ("settings", "env", "checkpoint"):
        try:
            v = json.loads(raw)
        except json.JSONDecodeError:
            _die(f"{key} must be JSON, e.g. '{{\"clear\": 20}}'")
        if not isinstance(v, dict):
            _die(f"{key} must be a JSON object")
        return v
    nullable = {"model", "effort", "subagent_model", "tools", "permission_mode",
                "setting_sources", "fallback_model"}
    if key in nullable and raw.lower() in ("none", "null", "-"):
        return None
    return raw


def cmd_set(args) -> int:
    key = args.key.replace("-", "_")
    # `set checkpoint 8` is the common case: one number for every zone.
    if key == "checkpoint" and args.value.isdigit():
        n = int(args.value)
        value = {z: n for z in ("clear", "notice", "wind-down", "reserve")}
    elif key not in SessionConfig.__dataclass_fields__:
        _die(f"unknown key {args.key!r}. Settable: "
             f"{', '.join(sorted(LAUNCH_ONLY | LIVE))}")
    else:
        value = _coerce(key, args.value)

    if key not in SETTABLE:
        _die(f"{args.key!r} is not a settable key. Settable: "
             f"{', '.join(sorted(SETTABLE))}")

    configs = sessionconfig.load_configs()
    target = args.config or sessionconfig.get_active() or "balanced"

    if args.config and not args.save:
        # An overlay is keyed to THIS session, not to a config name. Writing a
        # session-only change "for" another config silently applies it here.
        _die(f"--config {args.config} only makes sense with --save. A session-only "
             "change always applies to the session you are in "
             f"(currently '{sessionconfig.get_active() or 'balanced'}').")

    if args.save:
        cfg = configs.get(target)
        if not cfg:
            _die(f"unknown configuration {target!r}")
        setattr(cfg, key, value)
        try:
            cfg.validate()
        except ValueError as e:
            _die(str(e))
        configs[target] = cfg
        sessionconfig.save_configs(configs)
        print(f"{target}.{key} = {_fmt_value(value)}  (saved)")
    else:
        probe = configs.get(target) or SessionConfig(name=target)
        from dataclasses import replace as _replace
        try:
            _replace(probe, **{key: value}).validate()
        except ValueError as e:
            _die(str(e))
        if not sessionconfig.save_overlay({key: value}):
            _die("not inside a Claude Code session ($CLAUDE_CODE_SESSION_ID is "
                 "unset), so there is no session to scope this to. Use --save to "
                 "change the stored configuration instead.")
        print(f"{key} = {_fmt_value(value)}  (this session only; "
              f"add --save to keep it in '{target}')")
        _rewrite_resolved(model_set=key == "model" and value is not None)

    if key in LAUNCH_ONLY and not args.save:
        # An overlay dies with this session and `start` reads the STORED
        # config, so a session-only launch key can never reach a launch. Say
        # so, and say what does work.
        tmpl = IN_SESSION_EQUIVALENT.get(key)
        now_hint = (f" To change it in this session right now, run  "
                    f"{tmpl.format(value=value)}." if tmpl and value else "")
        print(f"note: {key} is a launch-time setting. This session-only record "
              "is informational -- it will NOT be applied by the next `start`, "
              f"because the overlay ends with this session.{now_hint} "
              f"To change what `start {target}` launches, add --save.")
    return 0


def _rewrite_resolved(model_set: bool = False) -> None:
    """`set` is the one other writer of resolved.json (§2.3): same request, new overlay.
    A model set here is newer than the SessionStart payload's (round 2 F1): the request
    drops that model, so the declared one (the overlay's) decides the window until the
    next SessionStart names the model in force."""
    sid = sessionconfig.session_id()
    state = resolver.state_dir(os.environ)
    sdir = resolver.session_dir(state, sid) if sid else None
    req = resolver.load_request(sdir) if sdir else None
    if not req:
        return                      # no SessionStart resolved this session; nothing to rewrite
    if model_set:
        req["model"] = None
    try:
        r = resolver.resolve(req["cwd"], sid, os.environ, profile=req.get("profile"),
                             transcript_path=req.get("transcript_path"),
                             session_model=req.get("model"),
                             session_model_source=req.get("model_source"))
        resolver.write(r, state)
        if model_set:
            resolver.save_request(sdir, req["cwd"], req.get("profile"),
                                  req.get("transcript_path"), None)
    except (resolver.ResolveError, OSError, KeyError) as e:
        print(f"note: resolved.json not rewritten: {e}", file=sys.stderr)


def _respawn_check(args) -> tuple[str, str, str] | None:
    """respawn-r1 §3.2's steps 1 to 3, before anything is written: (session id, the
    charter's absolute path, the sha256 of the bytes read), or None without either flag.
    Every refusal exits 2 with one line and writes nothing."""
    if not (args.respawn or args.charter):
        return None
    if not args.charter:
        _die("checkpoint --respawn needs --charter FILE, the sitting's charter "
             "(there is no default)", 2)
    if not args.respawn:
        _die("checkpoint --charter FILE is read only with --respawn; add --respawn", 2)
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID") or ""
    if not hooks._SID.match(sid):
        _die("checkpoint --respawn: $CLAUDE_CODE_SESSION_ID is not a session id; "
             "only a sitting marks its own close", 2)
    if os.environ.get("CLAUDE_SESSION_HELPER") == "1":
        _die("checkpoint --respawn is refused in a helper (CLAUDE_SESSION_HELPER=1); "
             "only the sitting marks its own close", 2)
    path = os.path.abspath(args.charter)
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as e:
        _die(f"checkpoint --respawn: cannot read the charter {path}: "
             f"{e.strerror or type(e).__name__}", 2)
    text = raw.decode("utf-8", "replace")
    line = charter.next_act_line(text)
    if line is None:
        found = any(l.rstrip() == charter.NEXT_ACT for l in text.splitlines())
        _die(f"checkpoint --respawn: {path}: "
             + ("the '## Next act' section is empty" if found else "no '## Next act' section")
             + "; a RESPAWN close opens it on RESPAWN", 2)
    if not charter.RESPAWN.match(line):
        _die(f"checkpoint --respawn: {path}: the Next act opens on "
             f"{' '.join(line.split())[:80]!r}, not RESPAWN", 2)
    # Packet S22 ruling 2, in one git call: an uncommitted charter is refused (the
    # launcher's successor reads the commit, and a dirty main holds its siblings);
    # `--commit` takes a tracked one, never an untracked one. Unknown goes on, loudly.
    st = gitinfo.path_state(path)
    if st is None:
        print(f"note: checkpoint --respawn: {path}: the charter's commit state is unknown "
              "(git status failed or timed out); the respawn goes on", file=sys.stderr)
    elif st and st is not gitinfo._NOT_A_REPO and (st == "??" or not args.commit):
        _die(f"checkpoint --respawn: {path} is not committed; commit it first: "
             f"{_commit_line(path)}", 2)
    return sid, path, hashlib.sha256(raw).hexdigest()


def _respawn_mark(sid: str, path: str, sha: str) -> str:
    """Write `sessions/<sid>/respawn.json` (exactly its five keys); return the line to print."""
    chain = os.environ.get(hooks.CHAIN_VAR) or ""
    chain = chain if hooks.CHAIN_RE.match(chain) else None
    marker = {"session": sid, "charter": path, "charter_sha256": sha,
              "written": time.time(), "chain": chain}
    sdir = resolver.session_dir(resolver.state_dir(os.environ), sid)
    try:
        store._write_private(sdir / hooks.MARKER, json.dumps(marker) + "\n")
    except OSError as e:
        _die(f"checkpoint recorded, but the respawn marker was not written: {e}")
    if chain:
        return "respawn marked; the launcher restarts this sitting after this turn ends"
    return "respawn marked; no launcher runs this sitting: print your start line and stop"


def cmd_checkpoint(args) -> int:
    mark = _respawn_check(args)
    cfg, _ = sessionconfig.effective()
    workdir = os.getcwd()
    if not sessionconfig.session_id():
        _die("not inside a Claude Code session ($CLAUDE_CODE_SESSION_ID unset); "
             "there is no session to checkpoint.")
    if args.commit:
        if not gitinfo.is_repo(workdir):
            _die("not a git repository, so there is nothing to commit")
        msg = args.message or ("checkpoint" if not sessionconfig.get_active()
                               else f"checkpoint ({cfg.name})")
        # Tracked files only. `add -A` is repo-wide and would sweep up a
        # plaintext .env, a tfstate, or an age key copied in for a test --
        # the wind-down nudge makes an autonomous agent the likeliest caller.
        subprocess.run(["git", "-C", workdir, "add", "-u"], check=False)
        _, porcelain = gitinfo._git(workdir, "status", "--porcelain")
        new_files = [l[3:] for l in porcelain.splitlines() if l.startswith("?? ")]
        if new_files:
            print(f"note: {len(new_files)} untracked file(s) NOT committed "
                  f"({', '.join(new_files[:4])}{'…' if len(new_files) > 4 else ''}). "
                  "Add them yourself if they belong in the repo.", file=sys.stderr)
        r = subprocess.run(["git", "-C", workdir, "commit", "-m", msg],
                           capture_output=True, text=True)
        if r.returncode != 0 and "nothing to commit" not in (r.stdout + r.stderr):
            _die(f"commit failed: {(r.stderr or r.stdout).strip()}")
        print((r.stdout or "").strip() or "nothing to commit")
    if not sessionconfig.save_overlay({hooks.COUNTER: 0,
                                       hooks.LAST_CHECKPOINT: time.time()}):
        _die("could not record the checkpoint (no session overlay path)")
    # One `git status` (ADV6-5); a failed or timed-out one reads unknown, never
    # clean (review r6 E2). Outside a repository there is no tree line at all.
    st = gitinfo.tree_state(workdir)
    line = "checkpoint recorded"
    if st is not None:
        head, branch, dirty = st
        line += f" at {head[:8]} on {branch}" if head else ""
        line += ("  (tree state unknown: git status failed or timed out)" if dirty is None
                 else "  (tree is dirty)" if dirty else "  (tree is clean)")
    print(line)
    if mark:
        print(_respawn_mark(*mark))
    return 0



def _respawn_flag(key: str, raw: str) -> int:
    """A `run --cap/--floor/--settle` value: a non-negative integer, else exit 2 naming
    the key (packet S20 ruling 8)."""
    if not (raw.isascii() and raw.isdigit()):          # A-F7: ASCII digits only
        _die(f"respawn.{key} must be a non-negative integer (--{key} {raw!r})", 2)
    return int(raw)


def cmd_run(args) -> int:
    """`agentik session run`: start claude, and restart it at each confirmed RESPAWN
    close (respawn-r1 §3). Every refusal before the first start exits 2 with one line."""
    from . import chain
    env = dict(os.environ)
    flags = {k: _respawn_flag(k, getattr(args, k)) for k in resolver.RESPAWN_KEYS
             if getattr(args, k) is not None}
    if not chain.on_tty():
        _die("agentik-session run: stdin and stdout must be a TTY; the launcher runs in "
             "the owner's terminal", 2)
    why = chain.refusal(args.claude_args, env)
    if why:
        _die(f"agentik-session run: {why}", 2)
    cwd = os.getcwd()
    name = args.chain if args.chain is not None else chain.default_name(cwd, env)
    if not hooks.CHAIN_RE.match(name):
        _die(f"agentik-session run: refusing the chain name {name[:80]!r}: a chain name is "
             "1 to 64 of A-Z a-z 0-9 . _ -", 2)
    try:
        chain.guards(cwd, env, flags)
    except resolver.ResolveError as e:
        _die(f"agentik-session run: {e}", 2)
    minutes = chain.long_loop(args.claude_args)
    if minutes is not None:
        print(f"warning: the first prompt is a /loop of {minutes:g} minutes; a /loop of 60 "
              "minutes or more asks its question (cloud or session) before it arms, so "
              "every restarted sitting waits there: give an interval under 60m, or none",
              file=sys.stderr)
    return chain.Chain(name, list(args.claude_args), resolver.state_dir(env),
                       chain.Effects(), lambda: chain.guards(cwd, env, flags),
                       argv=["agentik", "session", *args.raw_argv]).run()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agentik session",
        description="Launch Claude Code with a named configuration, and keep "
                    "the session handoff-ready.",
    )
    p.add_argument("--version", action="version", version=f"agentik-session {SEMVER}")
    sub = p.add_subparsers(dest="cmd", required=True, metavar="<command>")


    st2 = sub.add_parser("start", help="launch claude with a named configuration")
    st2.add_argument("config")
    st2.add_argument("-n", "--dry-run", action="store_true",
                     help="print the command instead of running it")
    st2.add_argument("--nested", action="store_true",
                     help="allow a start from inside a started session (depth 2 or more)")
    st2.add_argument("--max-turns", type=_positive_int, metavar="N",
                     help="pass --max-turns N to claude; the meter's turn ceiling "
                          "becomes the smaller of N and the profile's")
    st2.add_argument("claude_args", nargs="*",
                     help="extra arguments passed through to claude")
    st2.set_defaults(func=cmd_start)

    cf = sub.add_parser("config", help="manage named session configurations")
    cf.add_argument("action", choices=["list", "show", "new", "delete"])
    cf.add_argument("name", nargs="?")
    cf.add_argument("--from", dest="From", metavar="CONFIG")
    cf.add_argument("--description")
    cf.add_argument("--stored", action="store_true",
                    help="show the saved configuration, ignoring session overrides")
    cf.add_argument("--resolved", action="store_true",
                    help="show this session's resolved file, provider block first")
    cf.set_defaults(func=cmd_config)

    dr = sub.add_parser("doctor", help="check the tool, the plugin and its dependencies")
    dr.add_argument("--json", action="store_true")
    dr.set_defaults(func=cmd_doctor)

    pf = sub.add_parser("profile", help="list the profiles, or show one resolved here")
    pf.add_argument("name", nargs="?")
    pf.set_defaults(func=cmd_profile)

    se = sub.add_parser("set", help="adjust a setting for this session only")
    se.add_argument("key")
    se.add_argument("value")
    se.add_argument("--save", action="store_true",
                    help="persist it to the configuration instead")
    se.add_argument("--config", metavar="NAME")
    se.set_defaults(func=cmd_set)

    cp = sub.add_parser("checkpoint", help="mark a handoff-ready point")
    cp.add_argument("-m", "--message")
    cp.add_argument("-c", "--commit", action="store_true",
                    help="git add -u (tracked files only) && git commit first")
    cp.add_argument("--respawn", action="store_true",
                    help="mark a RESPAWN close, the sitting's last act: the charter's "
                         "Next act must open on RESPAWN (needs --charter)")
    cp.add_argument("--charter", metavar="FILE",
                    help="the sitting's charter, read for --respawn")
    cp.set_defaults(func=cmd_checkpoint)

    sm = sub.add_parser("status", help="this session's meter: context, turns, zone")
    sm.add_argument("--json", action="store_true", help="print meter.json")
    sm.add_argument("--transcript", metavar="PATH",
                    help="parse this transcript once; write nothing")
    sm.set_defaults(func=cmd_status)

    md = sub.add_parser("mod", help="the session plugin's hooks module's verb: start")
    msub = md.add_subparsers(dest="mod_verb", required=True, metavar="start")
    ms = msub.add_parser("start", help="write mod.json in the session's directory and print "
                         "the directory as JSON (run by plugin/hooks/session.ts)")
    ms.add_argument("--session", required=True, metavar="ID", help="the session id")
    ms.set_defaults(func=cmd_mod)

    ad = sub.add_parser("admission", help="the admission module's verbs: record one line "
                        "on the machine's admission ledger, or admit one spawn")
    asub = ad.add_subparsers(dest="admission_verb", required=True, metavar="record|admit")
    ar = asub.add_parser("record", help="append stdin's one JSON object {kind, ...} to "
                         "admission/ledger.jsonl (run by plugin/hooks/session.ts); "
                         "exit 2 refused, 3 the lock or the disk")
    ar.add_argument("--session", required=True, metavar="ID", help="the session id")
    ar.set_defaults(func=cmd_admission)
    aa = asub.add_parser("admit", help="decide one spawn from stdin's JSON object (observe: "
                         "never refuses), append its verdict line and print {verdict, mode, "
                         "text, peak}; exit 2 refused, 3 the lock or the disk")
    aa.add_argument("--session", required=True, metavar="ID", help="the session id")
    aa.set_defaults(func=cmd_admission)

    me = sub.add_parser("measure", help="the hooks module's measure verb: record the engine's "
                        "session.measure beside the meter")
    mesub = me.add_subparsers(dest="measure_verb", required=True, metavar="record")
    mr = mesub.add_parser("record", help="write stdin's one JSON object {context, rateLimits, "
                          "cost, changed} as the session's measure.json (run by "
                          "plugin/hooks/session.ts); exit 1 no session, 2 refused")
    mr.add_argument("--session", required=True, metavar="ID", help="the session id")
    mr.set_defaults(func=cmd_measure)

    rp = sub.add_parser("report", help="the ledger: one row per ended session")
    rp.add_argument("--since", metavar="YYYY-MM-DD")
    rp.add_argument("--json", action="store_true")
    rp.add_argument("--chains", action="store_true",
                    help="the launcher's restart and stop lines instead (--since reads their at)")
    rp.set_defaults(func=cmd_report)

    ch = sub.add_parser("charter", help="the sitting's charter: open, check, close")
    ch.add_argument("action", choices=["open", "check", "close"])
    ch.add_argument("args", nargs="*", metavar="GOAL|FILE")
    ch.add_argument("--dir", metavar="D", help="the charter directory (open, close)")
    ch.add_argument("--exit", metavar="TEXT", help="the exit taken (close)")
    ch.set_defaults(func=cmd_charter)

    ru = sub.add_parser("rules", help="the priority and pacing this session meets, "
                                       "as resolved")
    ru.set_defaults(func=cmd_rules)

    b = sub.add_parser("budget", help="the budget zone and checkpoint cadence")
    b.set_defaults(func=cmd_budget)

    rn = sub.add_parser("run", help="start claude, and restart it at each RESPAWN "
                                     "close (the chain)")
    rn.add_argument("--chain", metavar="NAME",
                    help="the chain's name (default: <cwd name>-<profile or none>)")
    rn.add_argument("--cap", metavar="N", help="restarts in any 24 h (respawn.cap)")
    rn.add_argument("--floor", metavar="S",
                    help="seconds a sitting runs before it may restart (respawn.floor)")
    rn.add_argument("--settle", metavar="S",
                    help="seconds the turn's end stands before the signal (respawn.settle)")
    rn.add_argument("claude_args", nargs="*",
                    help="claude's arguments after --, sent the same at every start")
    rn.set_defaults(func=cmd_run)

    hk = sub.add_parser("hook")   # internal: invoked by Claude Code hooks
    hk.add_argument("event", choices=sorted(hooks.HANDLERS))
    hk.set_defaults(func=cmd_hook)
    return p


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(raw)
    args.raw_argv = raw             # `run` prints its own start line from it
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
