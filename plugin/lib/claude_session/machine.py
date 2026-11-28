"""The machine's meter (hq design/34 items 15 to 18; packet hw3-machine, M1 to M5).

One module, standard library alone, that imports nothing of the plugin, so it can be lifted
out whole. Four parts:

- `snapshot()`: cores by kind, the load, memory total and free and its pressure level, the
  volumes of the home, the state root and the Go build cache, and the count and resident
  memory of a few known process names.
- `budget(snapshot, grants, config, request)`: pure arithmetic over a snapshot and the grants
  the caller passes; the module reads no queue.
- `consumers(roots)`: the known disk consumers, each marked `auto`, `idle` or `person`. It
  removes nothing.
- `backoff(attempt, retry_after)`: a capped exponential delay with full jitter, a
  `Retry-After` honoured first.

Every reader is bounded (a subprocess by `RUN_BOUND`, a `du` by `DU_BOUND`) and never
raises: a part it cannot read is null, and the `faults` list names it. Each platform's
parser takes recorded text, so the Linux reader is tested on any machine.
"""
from __future__ import annotations

import math
import os
import random
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

SCHEMA = "agentik.machine/1"
RUN_BOUND = 5.0             # seconds, any subprocess but `du`
DU_BOUND = 20.0             # seconds, one `du -sk`
READ_MOST = 1 << 16         # bytes, one file of /proc
ATTEMPTS = 3                # tries of one call, the first included (SRE's three)
LOAD_SHARE = 0.75           # the load ceiling, as a share of the cores (the gate's LOAD_SHARE)
DISK_FLOOR_GB = 25.0        # the least free disk a start leaves
MEM_RESERVE_SHARE = 0.25    # the memory the budget leaves to everything else (hw6 B3, R2)
MEM_RESERVE_LEAST = 4096    # and at least this many MB of it
DEFAULT_CLASS = {"cpu": 4, "mem_mb": 2048}      # a job that declares nothing (design/34 item 8)
LIGHT_CLASS = {"cpu": 1, "mem_mb": 512}         # a light job that names none (hw6 B1)
PARTS = ("grant", "load", "pressure", "disk")   # `budget`'s named parts (hw6 R3)
GATE_KEEP_DAYS = 14         # the gate's own retention (gate.KEEP)
RETRY_AFTER_MOST = 3600.0   # a Retry-After past an hour is not honoured
DU_WORKERS = 4
KINDS = ("auto", "idle", "person")
PROCESS_NAMES = ("java", "go", "make", "python", "claude")
PRESSURES = ("normal", "warn", "critical", "unknown")
MB = 1024 ** 2
GB = 1024 ** 3
_GATE_ID = re.compile(r"^\d{8}-\d{6}-[1-9]\d{0,11}\Z")
_MAC_PRESSURE = {1: "normal", 2: "warn", 4: "critical"}
_SYSCTL = ("hw.memsize", "kern.memorystatus_vm_pressure_level",
           "hw.perflevel0.physicalcpu", "hw.perflevel1.physicalcpu")


# ---- the effects, one object a test replaces -----------------------------------------------

class Probe:
    """What the readers touch. A test passes a subclass fed with recorded text."""

    def run(self, argv, timeout=RUN_BOUND, cwd=None, env=None):
        """(exit code, stdout) or None for a command that did not start or ran past `timeout`."""
        try:
            p = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, timeout=timeout, cwd=cwd, env=env,
                               universal_newlines=True, errors="replace")
        except (OSError, ValueError, subprocess.SubprocessError):
            return None
        return p.returncode, p.stdout

    def read(self, path):
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                return fh.read(READ_MOST)
        except (OSError, ValueError):
            return None

    def cpu_count(self):
        return os.cpu_count()

    def loadavg(self):
        return os.getloadavg()

    def env(self, name):
        return os.environ.get(name)

    def now(self):
        return time.time()

    def platform(self):
        return sys.platform


def default_probe() -> Probe:
    return Probe()


# ---- parsers of recorded text --------------------------------------------------------------

def _num(text):
    try:
        x = float(text)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _digits(word):
    """ASCII digits alone: `str.isdigit` is true of `"²"`, which `int()` refuses."""
    return isinstance(word, str) and word.isascii() and word.isdigit()


def _finite(x):
    """`x` where it is an int or a float, no bool, and finite; else None."""
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    try:
        return x if math.isfinite(x) else None
    except OverflowError:                       # an int past a float's range
        return None


def parse_sysctl(text) -> dict:
    """`sysctl a b` output, `name: value` a line, as {name: value}; a line that is no pair is
    skipped (sysctl names an unknown name on stderr and goes on)."""
    out = {}
    for line in (text or "").splitlines():
        name, sep, value = line.partition(":")
        name = name.strip()
        if sep and "." in name and " " not in name:
            out[name] = value.strip()
    return out


def parse_vm_stat(text) -> dict:
    """macOS `vm_stat`: {"page": bytes, "free": pages, "inactive": ..., ...}, lower case,
    the words after `Pages `; a count's trailing dot dropped."""
    out = {}
    lines = (text or "").splitlines()
    m = re.search(r"page size of (\d+) bytes", lines[0]) if lines else None
    if m:
        out["page"] = int(m.group(1))
    for line in lines[1:]:
        name, sep, value = line.partition(":")
        name = name.strip().strip('"')
        if not sep or not name.startswith("Pages "):
            continue
        n = value.strip().rstrip(".")
        if _digits(n):
            out[name[len("Pages "):].strip().lower().replace(" ", "_")] = int(n)
    return out


def parse_meminfo(text) -> dict:
    """Linux `/proc/meminfo`: {name: kB}."""
    out = {}
    for line in (text or "").splitlines():
        name, sep, value = line.partition(":")
        words = value.split()
        if sep and words and _digits(words[0]):
            out[name.strip()] = int(words[0])
    return out


def parse_psi(text) -> dict:
    """Linux `/proc/pressure/memory`: {"some": avg10, "full": avg10}."""
    out = {}
    for line in (text or "").splitlines():
        words = line.split()
        if not words or words[0] not in ("some", "full"):
            continue
        for w in words[1:]:
            k, _, v = w.partition("=")
            if k == "avg10" and _num(v) is not None:
                out[words[0]] = _num(v)
    return out


def parse_df(text) -> list:
    """`df -Pk` lines after the header: [{mount, total_kb, used_kb, free_kb}]; the mount is
    the rest of the line, so it may hold spaces."""
    out = []
    for line in (text or "").splitlines()[1:]:
        words = line.split(None, 5)
        if len(words) < 6 or not all(_digits(w) for w in words[1:4]):
            continue
        out.append({"mount": words[5], "total_kb": int(words[1]), "used_kb": int(words[2]),
                    "free_kb": int(words[3])})
    return out


def _proc_kind(comm):
    base = os.path.basename(comm.strip()).lower()
    if base in ("java", "go", "make", "gmake", "claude"):
        return "make" if base == "gmake" else base
    if re.match(r"python(\d+(\.\d+)?)?\Z", base):
        return "python"
    return None


def parse_ps(text) -> dict:
    """`ps -A -o rss= -o comm=`: {name: {count, rss_mb}} for each of PROCESS_NAMES, by the
    command's base name (`python3.12` and `Python` are python, `gmake` is make)."""
    out = {name: {"count": 0, "rss_mb": 0} for name in PROCESS_NAMES}
    kb = dict.fromkeys(PROCESS_NAMES, 0)
    for line in (text or "").splitlines():
        words = line.strip().split(None, 1)
        if len(words) != 2 or not _digits(words[0]):
            continue
        kind = _proc_kind(words[1])
        if kind:
            out[kind]["count"] += 1
            kb[kind] += int(words[0])
    for name in PROCESS_NAMES:
        out[name]["rss_mb"] = round(kb[name] / 1024)
    return out


def parse_du(text):
    """`du -sk <path>`: the size in kB, from the last line's first word; None for none."""
    lines = [x for x in (text or "").splitlines() if x.strip()]
    if not lines:
        return None
    word = lines[-1].split()[0]
    return int(word) if _digits(word) else None


def linux_pressure(psi: dict, meminfo: dict) -> str:
    """PSI's 10-second averages where the kernel has them, then the share available:
    `critical` at a full stall of 10% or under 5% available, `warn` at a partial stall of
    10% or under 10% available, else `normal`; `unknown` with neither to read."""
    total, avail = meminfo.get("MemTotal"), meminfo.get("MemAvailable")
    share = (avail / total) if total and avail is not None else None
    if not psi and share is None:
        return "unknown"
    if psi.get("full", 0) >= 10 or (share is not None and share < 0.05):
        return "critical"
    if psi.get("some", 0) >= 10 or (share is not None and share < 0.10):
        return "warn"
    return "normal"


# ---- the snapshot --------------------------------------------------------------------------

def _gb(kb):
    return None if kb is None else round(kb * 1024 / GB, 1)


def _exists_above(path):
    p = os.path.abspath(path)
    while p != os.path.dirname(p) and not os.path.exists(p):
        p = os.path.dirname(p)
    return p


def _df(probe, path):
    r = probe.run(["df", "-Pk", _exists_above(path)])
    rows = parse_df(r[1]) if r and r[0] == 0 else []
    return rows[0] if rows else None


def gocache(probe, faults=None):
    """The Go build cache's folder: `$GOCACHE`, else `go env GOCACHE` (from `/`, with
    `GOTOOLCHAIN=local`, so no module asks for a download); None where neither answers or
    the cache is off."""
    path = probe.env("GOCACHE")
    if not path:
        env = dict(os.environ, GOTOOLCHAIN="local")
        r = probe.run(["go", "env", "GOCACHE"], cwd="/", env=env)
        path = r[1].strip() if r and r[0] == 0 else None
    return path if path and path != "off" and os.path.isabs(path) else None


def _cores(probe, plat, ctl, faults):
    n = probe.cpu_count()
    cores = {"total": n if isinstance(n, int) and n > 0 else None,
             "performance": None, "efficiency": None}
    if cores["total"] is None:
        faults.append("cores: the count did not answer")
    if plat == "darwin":
        p, e = ctl.get("hw.perflevel0.physicalcpu"), ctl.get("hw.perflevel1.physicalcpu")
        if _digits(p):
            cores["performance"] = int(p)
            cores["efficiency"] = int(e) if _digits(e) else 0
        else:
            faults.append("cores: hw.perflevel0.physicalcpu did not answer")
    return cores


def _load(probe, faults):
    try:
        a = probe.loadavg()
        return [round(float(x), 2) for x in a[:3]] if len(a) >= 3 else None
    except (OSError, TypeError, ValueError, AttributeError):
        faults.append("load: getloadavg failed")
        return None


def _memory_mac(probe, ctl, faults):
    mem = {"total_mb": None, "free_mb": None, "pressure": "unknown"}
    total = ctl.get("hw.memsize")
    if _digits(total):
        mem["total_mb"] = int(total) // MB
    else:
        faults.append("memory: hw.memsize did not answer")
    r = probe.run(["vm_stat"])
    vm = parse_vm_stat(r[1]) if r and r[0] == 0 else {}
    if "page" in vm and "free" in vm:
        pages = vm["free"] + vm.get("inactive", 0) + vm.get("speculative", 0)
        mem["free_mb"] = pages * vm["page"] // MB
    else:
        faults.append("memory: vm_stat did not answer")
    level = ctl.get("kern.memorystatus_vm_pressure_level")
    if _digits(level) and int(level) in _MAC_PRESSURE:
        mem["pressure"] = _MAC_PRESSURE[int(level)]
    else:
        faults.append("memory: kern.memorystatus_vm_pressure_level did not answer")
    return mem


def _memory_linux(probe, faults):
    mem = {"total_mb": None, "free_mb": None, "pressure": "unknown"}
    info = parse_meminfo(probe.read("/proc/meminfo"))
    if "MemTotal" in info:
        mem["total_mb"] = info["MemTotal"] // 1024
    if "MemAvailable" in info:
        mem["free_mb"] = info["MemAvailable"] // 1024
    if "MemTotal" not in info or "MemAvailable" not in info:
        faults.append("memory: /proc/meminfo did not answer")
    psi = parse_psi(probe.read("/proc/pressure/memory"))
    mem["pressure"] = linux_pressure(psi, info)
    if mem["pressure"] == "unknown":
        faults.append("memory: no pressure to read")
    return mem


def _disks(probe, paths, faults):
    out = []
    for name, path in paths.items():
        if not path:
            continue
        row = _df(probe, path)
        if row is None:
            faults.append(f"disk {name}: df did not answer")
            continue
        same = next((d for d in out if d["mount"] == row["mount"]), None)
        if same:
            same["holds"].append(name)
            continue
        out.append({"mount": row["mount"], "total_gb": _gb(row["total_kb"]),
                    "free_gb": _gb(row["free_kb"]), "holds": [name]})
    return out


def snapshot(paths=None, probe=None, platform=None) -> dict:
    """The machine now. `paths` names the folders whose volumes are read (`home`, `state`;
    `gocache` is added from `go env GOCACHE` where it answers and is not given). Never
    raises."""
    probe = probe or default_probe()
    plat = platform or probe.platform()
    faults = []
    paths = dict(paths or {"home": os.path.expanduser("~")})
    if "gocache" not in paths:
        paths["gocache"] = gocache(probe)
    ctl = {}
    if plat == "darwin":
        r = probe.run(["sysctl"] + list(_SYSCTL))
        ctl = parse_sysctl(r[1]) if r else {}      # an unknown name exits 1 and prints the rest
    snap = {"schema": SCHEMA, "platform": plat, "at": round(probe.now(), 3),
            "cores": _cores(probe, plat, ctl, faults), "load": _load(probe, faults)}
    if plat == "darwin":
        snap["memory"] = _memory_mac(probe, ctl, faults)
    elif plat.startswith("linux"):
        snap["memory"] = _memory_linux(probe, faults)
    else:
        snap["memory"] = {"total_mb": None, "free_mb": None, "pressure": "unknown"}
        faults.append(f"memory: no reader for {plat}")
    snap["disks"] = _disks(probe, paths, faults)
    r = probe.run(["ps", "-A", "-o", "rss=", "-o", "comm="])
    if r and r[0] == 0:
        snap["processes"] = parse_ps(r[1])
    else:
        snap["processes"] = None
        faults.append("processes: ps did not answer")
    snap["paths"] = {k: v for k, v in paths.items() if v}
    snap["faults"] = faults
    return snap


# ---- the budget, pure ----------------------------------------------------------------------

def _short(x):
    return repr(x)[:40]


def _reading(x, name, unread):
    """`x` where it is a finite number of 0 or more; else None, and `name` in `unread`."""
    v = _finite(x)
    if v is None or v < 0:
        unread.append(f"{name} {_short(x)}")
        return None
    return v


def _part_of(d, key):
    v = d.get(key) if isinstance(d, dict) else None
    return v if isinstance(v, dict) else {}


def budget(snapshot, grants, config=None, request=None, volume=None) -> dict:
    """What is free of cores and memory against `grants` (a list of {cpu, mem_mb}), and for a
    `request` ({cpu, mem_mb}) `fit`, {ok, why}, and `parts` (hw6 R3): `grant`, `load`,
    `pressure` and `disk`, each {state, reading, why}, the state `ok`, `held` or `unread`, so
    a caller bounds each apart. The disk part reads the volume whose `holds` names `volume`
    (R4), else the least free. A request fits where its grant fits what is
    not granted, the 1-minute load is under the ceiling, the pressure is `normal` and the
    least free disk is over the floor. A request over the whole budget is clamped to it and
    fits only with no grant out. `config` may give `load_ceiling` (a load, else LOAD_SHARE of
    the cores), `disk_floor_gb`, `mem_reserve_mb` (else the larger of MEM_RESERVE_LEAST and
    MEM_RESERVE_SHARE of the memory; a negative one reads as 0). A value it cannot read as a
    finite number (a NaN, an infinity, a string, None, a bool) in the config, a grant, the
    request or the snapshot's load and disks is named in `unread`, and a request's `fit` is
    then held; its `parts` name each such part `unread`. Never raises."""
    unread: list = []
    if config is not None and not isinstance(config, dict):
        unread.append(f"the config {_short(config)}")
    cfg = config if isinstance(config, dict) else {}
    snap = snapshot if isinstance(snapshot, dict) else {}

    def setting(name):
        if name not in cfg:
            return None
        v = _finite(cfg[name])
        if v is None:
            unread.append(f"the config's {name} {_short(cfg[name])}")
        return v
    cores = _finite(_part_of(snap, "cores").get("total"))
    cores = cores if cores is not None and cores > 0 else None
    total_mb = _finite(_part_of(snap, "memory").get("total_mb"))
    total_mb = total_mb if total_mb is not None and total_mb >= 0 else None
    reserve = setting("mem_reserve_mb")
    mem_mb = None
    if total_mb is not None:
        reserve = max(MEM_RESERVE_LEAST, int(total_mb * MEM_RESERVE_SHARE)) if reserve is None \
            else max(0, reserve)
        mem_mb = max(0, int(total_mb - reserve))
    if grants is not None and not isinstance(grants, (list, tuple)):
        unread.append(f"the grants {_short(grants)}")
    grants = list(grants) if isinstance(grants, (list, tuple)) else []
    g_cpu = g_mem = 0
    for i, g in enumerate(grants, 1):
        if not isinstance(g, dict):
            unread.append(f"grant {i} {_short(g)}")
            continue
        g_cpu += _reading(g.get("cpu", 0), f"grant {i}'s cpu", unread) or 0
        g_mem += _reading(g.get("mem_mb", 0), f"grant {i}'s mem_mb", unread) or 0
    ceiling = setting("load_ceiling")
    if ceiling is None:
        ceiling = LOAD_SHARE * cores if cores else None
    floor = setting("disk_floor_gb")
    floor = DISK_FLOOR_GB if floor is None else floor
    disks = snap.get("disks")
    free_disks, own = [], None
    for d in disks if isinstance(disks, (list, tuple)) else []:
        if not isinstance(d, dict) or d.get("free_gb") is None:
            continue
        v = _finite(d["free_gb"])
        if v is None:
            unread.append(f"the free disk of {_short(d.get('mount'))} {_short(d['free_gb'])}")
        else:
            free_disks.append(v)
            holds = d.get("holds")
            if volume is not None and isinstance(holds, list) and volume in holds:
                own = v
    out = {"cores": cores, "mem_mb": mem_mb,
           "granted": {"count": len(grants), "cpu": g_cpu, "mem_mb": g_mem},
           "free": {"cpu": None if cores is None else max(0, cores - g_cpu),
                    "mem_mb": None if mem_mb is None else max(0, mem_mb - g_mem)},
           "load_ceiling": None if ceiling is None else round(ceiling, 2),
           "disk_floor_gb": floor, "disk_free_gb": min(free_disks) if free_disks else None,
           "unread": unread}
    if request is None:
        return out
    out["fit"] = _fit(snap, out, request, ceiling, floor)
    out["parts"] = _parts(snap, out, request, ceiling, floor,
                          out["disk_free_gb"] if volume is None else own)
    return out


def _part(state, reading, why) -> dict:
    return {"state": state, "reading": reading, "why": why}


def _grant_part(b, request) -> dict:
    """The grant against what is not granted: a request over the whole budget is clamped to
    it and fits with no grant out (it runs alone)."""
    bad = [u for u in b["unread"] if u.startswith(("grant ", "the grants", "the config "))
           or u.startswith("the config's mem_reserve_mb")]
    cpu = need = None
    if isinstance(request, dict):
        cpu = _reading(request.get("cpu", 0), "the request's cpu", bad)
        need = _reading(request.get("mem_mb", 0), "the request's mem_mb", bad)
    else:
        bad.append(f"the request {_short(request)}")
    if bad:
        return _part("unread", None, "it cannot read " + "; ".join(bad))
    if b["cores"] is None or b["mem_mb"] is None:
        return _part("unread", None, ("cores" if b["cores"] is None else "memory")
                     + " did not answer")
    alone = cpu > b["cores"] or need > b["mem_mb"]
    cpu, need = min(cpu, b["cores"]), min(need, b["mem_mb"])
    reading = {"cpu": cpu, "mem_mb": need, "alone": alone}
    free = b["free"]
    if alone and b["granted"]["count"]:
        return _part("held", reading, f"over the budget: clamped to {cpu:g} cores and {need:g} "
                     f"MB, it runs alone, and {b['granted']['count']} grants are out")
    if not alone and (cpu > free["cpu"] or need > free["mem_mb"]):
        return _part("held", reading, f"{cpu:g} cores and {need:g} MB asked, {free['cpu']:g} "
                     f"and {free['mem_mb']:g} MB not granted")
    return _part("ok", reading, f"{cpu:g} of {free['cpu']:g} cores and {need:g} of "
                 f"{free['mem_mb']:g} MB free" + (", alone" if alone else ""))


def _parts(snap, b, request, ceiling, floor, disk) -> dict:
    """hw6 R3: each test of `_fit` apart, its reading kept. A reading that is a fault is
    `unread`, which a caller may hold on or pass (the gate passes, hw6 B4)."""
    out = {"grant": _grant_part(b, request)}
    load = snap.get("load")
    load = _finite(load[0]) if isinstance(load, (list, tuple)) and load else None
    if load is None or load < 0 or ceiling is None:
        out["load"] = _part("unread", None, "the load is unknown")
    elif load >= ceiling:
        out["load"] = _part("held", load, f"load {load:.2f} at or over the ceiling {ceiling:.2f}")
    else:
        out["load"] = _part("ok", load, f"load {load:.2f} under {ceiling:.2f}")
    pressure = _part_of(snap, "memory").get("pressure")
    if pressure == "normal":
        out["pressure"] = _part("ok", pressure, "pressure normal")
    elif pressure in ("warn", "critical"):
        out["pressure"] = _part("held", pressure, f"memory pressure {pressure}")
    else:
        out["pressure"] = _part("unread", None, "memory pressure "
                                + (pressure if isinstance(pressure, str) else _short(pressure)))
    if disk is None:
        out["disk"] = _part("unread", None, "the free disk is unknown")
    elif disk < floor:                                  # fix 1, A5: under the floor, not at it
        out["disk"] = _part("held", disk, f"{disk:g} GB free, under the floor of {floor:g}")
    else:
        out["disk"] = _part("ok", disk, f"{disk:g} GB free, the floor {floor:g}")
    return out


def _fit(snap, b, request, ceiling, floor) -> dict:
    bad = list(b["unread"])
    if isinstance(request, dict):
        cpu = _reading(request.get("cpu", 0), "the request's cpu", bad)
        need = _reading(request.get("mem_mb", 0), "the request's mem_mb", bad)
    else:
        bad.append(f"the request {_short(request)}")
    if bad:
        return {"ok": False, "why": "held: it cannot read " + "; ".join(bad)}
    if b["cores"] is None or b["mem_mb"] is None:
        return {"ok": False, "why": "the budget is unknown: "
                + ("cores" if b["cores"] is None else "memory") + " did not answer"}
    clamped = cpu > b["cores"] or need > b["mem_mb"]
    cpu, need = min(cpu, b["cores"]), min(need, b["mem_mb"])
    no = []
    if clamped and b["granted"]["count"]:
        no.append(f"over the budget: clamped to {cpu:g} cores and {need:g} MB, it runs "
                  f"alone, and {b['granted']['count']} grants are out")
    elif not clamped and (cpu > b["free"]["cpu"] or need > b["free"]["mem_mb"]):
        no.append(f"{cpu:g} cores and {need:g} MB asked, {b['free']['cpu']:g} and "
                  f"{b['free']['mem_mb']:g} MB not granted")
    load = snap.get("load")
    load = _finite(load[0]) if isinstance(load, (list, tuple)) and load else None
    if load is None or ceiling is None:
        no.append("the load is unknown")
    elif load >= ceiling:
        no.append(f"load {load:.2f} at or over the ceiling {ceiling:.2f}")
    pressure = _part_of(snap, "memory").get("pressure") or "unknown"
    if pressure != "normal":
        no.append("memory pressure "
                  + (pressure if isinstance(pressure, str) else _short(pressure)))
    disk = b["disk_free_gb"]
    if disk is None:
        no.append("the free disk is unknown")
    elif disk < floor:
        no.append(f"{disk:g} GB free, under the floor of {floor:g}")
    if no:
        return {"ok": False, "why": "; ".join(no)}
    return {"ok": True, "why": f"fits: {cpu:g} of {b['free']['cpu']:g} cores and {need:g} of "
                               f"{b['free']['mem_mb']:g} MB free, load {load:.2f} under "
                               f"{ceiling:.2f}, pressure normal, {disk:g} GB free, the floor {floor:g}"}


# ---- the disk's known consumers ------------------------------------------------------------

def _du(probe, path):
    r = probe.run(["du", "-sk", path], timeout=DU_BOUND)
    return parse_du(r[1]) if r else None      # du exits 1 on an unreadable file, sums the rest


def _newest(path):
    try:
        t = os.stat(path).st_mtime
        with os.scandir(path) as it:
            for e in it:
                try:
                    t = max(t, e.stat(follow_symlinks=False).st_mtime)
                except OSError:
                    pass
        return t
    except OSError:
        return None


def _size(path, until):
    total = 0
    for top, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.lstat(os.path.join(top, f)).st_size
            except OSError:
                pass
        if time.monotonic() > until:
            return None
    return total


def _gate_old(gate, now, faults):
    try:
        names = os.listdir(gate)
    except OSError:
        return None
    old, size, until = [], 0, time.monotonic() + DU_BOUND
    for name in sorted(names):
        p = os.path.join(gate, name)
        if _GATE_ID.match(name) and os.path.isdir(p):
            t = _newest(p)
            if t is not None and now - t > GATE_KEEP_DAYS * 86400:
                old.append(p)
    for p in old:
        n = _size(p, until)
        if n is None:
            faults.append(f"consumer {gate}: past {DU_BOUND:g} s")
            return {"path": gate, "gb": None, "kind": "auto",
                    "what": f"{len(old)} gate results past {GATE_KEEP_DAYS} days, unsized"}
        size += n
    return {"path": gate, "gb": round(size / GB, 1), "kind": "auto",
            "what": f"{len(old)} gate results past {GATE_KEEP_DAYS} days"}


def _gocache_row(probe, path, home, faults):
    row, base = _df(probe, path), _df(probe, home) if home else None
    if row is None:
        faults.append(f"consumer {path}: df did not answer")
        return {"path": path, "gb": None, "kind": "idle", "what": "the Go build cache, unread"}
    if base is not None and base["mount"] == row["mount"]:
        return {"path": path, "gb": None, "kind": "idle",
                "what": "the Go build cache, on the home's volume: not walked"}
    return {"path": path, "gb": _gb(row["used_kb"]), "kind": "idle",
            "what": f"the Go build cache, its volume {row['mount']}'s use"}


def parse_worktrees(text) -> list:
    """`git worktree list --porcelain`: [{path, head, branch}], the main checkout first;
    a bare or prunable one is skipped."""
    out, cur = [], None
    for line in (text or "").splitlines() + [""]:
        if line.startswith("worktree "):
            cur = {"path": line[len("worktree "):], "head": None, "branch": None}
        elif cur is None:
            continue
        elif line.startswith("HEAD "):
            cur["head"] = line[5:].strip()
        elif line.startswith("branch "):
            cur["branch"] = line[7:].strip().replace("refs/heads/", "", 1)
        elif line.strip() == "bare" or line.startswith("prunable"):
            cur["skip"] = True
        elif not line.strip():
            if not cur.pop("skip", False):
                out.append(cur)
            cur = None
    return out


GIT_READ = ("--no-optional-locks", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null")
GIT_STATUS = ("status", "--porcelain", "--untracked-files=all", "--ignore-submodules=none")


def _git(probe, folder, *args):
    """One git read as the gate's dirt read runs it (`gate._dirty`, `land.STATUS`): no
    optional lock, so the index is not rewritten; no fsmonitor and no hook, so the repo's
    config runs no command; no `GIT_*` from the caller, so the read is of `folder`."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return probe.run(["git", "-C", folder, *GIT_READ, *args], env=env)


def _under(path, top):
    p, t = os.path.realpath(path), os.path.realpath(top)
    return p != t and p.startswith(t.rstrip(os.sep) + os.sep)


def _worktree_kind(probe, repo, wt):
    """(kind, what): `idle` where the head is merged into main and the tree is clean."""
    name = wt["branch"] or "a detached head"
    if not wt["head"]:
        return "person", f"worktree of {name}: no head"
    r = _git(probe, repo, "merge-base", "--is-ancestor", wt["head"], "main")
    if r is None or r[0] != 0:
        return "person", f"worktree of {name}: not merged into main"
    r = _git(probe, wt["path"], *GIT_STATUS)
    if r is None or r[0] != 0:
        return "person", f"worktree of {name}: its status did not answer"
    if r[1].strip():
        return "person", f"worktree of {name}: merged, the tree dirty"
    return "idle", f"worktree of {name}: merged into main, clean"


def _worktrees(probe, repo, faults):
    r = _git(probe, repo, "worktree", "list", "--porcelain")
    if r is None or r[0] != 0:
        faults.append(f"consumer {repo}: git worktree list did not answer")
        return []
    out = []
    for wt in parse_worktrees(r[1]):
        if os.path.isdir(wt["path"]) and _under(wt["path"], repo):
            kind, what = _worktree_kind(probe, repo, wt)
            out.append({"path": wt["path"], "gb": None, "kind": kind, "what": what})
    return out


def _children(folder):
    try:
        return sorted(os.path.join(folder, n) for n in os.listdir(folder)
                      if os.path.isdir(os.path.join(folder, n))
                      and not os.path.islink(os.path.join(folder, n)))
    except OSError:
        return []


def consumers(roots, probe=None, now=None, faults=None) -> list:
    """The known disk consumers, each {path, gb, kind, what}, largest first. `roots` names
    `gate` (the gate's folder), `gocache`, `home`, `repos` (a list), `transcripts`,
    `state_home` (each folder in it is a state folder) and `scratch`; a root not given or
    not there is skipped. A size that cannot be read is null and named in `faults`, where
    a list is passed. It removes nothing."""
    probe = probe or default_probe()
    now = probe.now() if now is None else now
    faults = [] if faults is None else faults
    rows, sized = [], []
    gate = roots.get("gate")
    if gate and os.path.isdir(gate):
        row = _gate_old(gate, now, faults)
        if row:
            rows.append(row)
    if roots.get("gocache") and os.path.isdir(roots["gocache"]):
        rows.append(_gocache_row(probe, roots["gocache"], roots.get("home"), faults))
    for repo in roots.get("repos") or []:
        if repo and os.path.isdir(repo):
            sized += _worktrees(probe, repo, faults)
    t = roots.get("transcripts")
    if t and os.path.isdir(t):
        sized.append({"path": t, "gb": None, "kind": "person", "what": "the transcripts"})
    for p in _children(roots["state_home"]) if roots.get("state_home") else []:
        sized.append({"path": p, "gb": None, "kind": "person", "what": "a state folder"})
    s = roots.get("scratch")
    if s and os.path.isdir(s):
        sized.append({"path": s, "gb": None, "kind": "person", "what": "the scratch root"})
    if sized:
        with ThreadPoolExecutor(max_workers=DU_WORKERS) as pool:
            sizes = list(pool.map(lambda row: _du(probe, row["path"]), sized))
        for row, kb in zip(sized, sizes):
            row["gb"] = _gb(kb)
            if kb is None:
                faults.append(f"consumer {row['path']}: du did not answer in {DU_BOUND:g} s")
    rows += sized
    return sorted(rows, key=lambda r: -(r["gb"] if r["gb"] is not None else -1))


def reclaimable(rows) -> dict:
    """{kind: {count, gb}} over `consumers()`'s rows; what `auto` and `idle` would free."""
    out = {k: {"count": 0, "gb": 0.0} for k in KINDS}
    for r in rows:
        k = out.get(r.get("kind"))
        if k is not None:
            k["count"] += 1
            k["gb"] = round(k["gb"] + (r.get("gb") or 0), 1)
    return out


# ---- the job's peak (hw6 B2) ---------------------------------------------------------------

def parse_ps_groups(text) -> dict:
    """`ps -A -o pgid= -o rss=`: {pgid: kB}, the resident memory of each process group summed;
    a line that is no two numbers is skipped."""
    out: dict = {}
    for line in (text or "").splitlines():
        words = line.split()
        if len(words) != 2 or not all(_digits(w) for w in words):
            continue
        g = int(words[0])
        out[g] = out.get(g, 0) + int(words[1])
    return out


def group_rss_mb(pgids, probe=None) -> dict:
    """{pgid: MB} for each of `pgids` that `ps` names, the sum of its group's resident memory;
    {} where `ps` did not answer in RUN_BOUND. Never raises."""
    want = {g for g in pgids or () if isinstance(g, int) and not isinstance(g, bool) and g > 0}
    if not want:
        return {}
    try:
        r = (probe or default_probe()).run(["ps", "-A", "-o", "pgid=", "-o", "rss="])
    except Exception:                                   # noqa: BLE001 - a sample is skipped
        return {}
    if not r or r[0] != 0:
        return {}
    kb = parse_ps_groups(r[1])
    return {g: round(kb[g] / 1024) for g in want if g in kb}


# ---- backoff, pure -------------------------------------------------------------------------

def backoff(attempt, retry_after=None, base=1.0, cap=60.0, rng=random.random) -> float:
    """Seconds before the next try: `retry_after` where it is a number of seconds from 0 to
    an hour (a header's text is read as one), else full jitter, `rng() * min(cap, base *
    2 ** attempt)`. Make at most ATTEMPTS tries of one call. An `attempt`, `base` or `cap`
    that is not a finite number of 0 or more reads as its default (0, 1.0, 60.0), and what
    `rng` gives is held to 0 to 1: it never raises and never returns a negative."""
    if not isinstance(retry_after, bool):
        x = _num(retry_after.strip() if isinstance(retry_after, str) else retry_after) \
            if isinstance(retry_after, (int, float, str)) else None
        if x is not None and 0 <= x <= RETRY_AFTER_MOST:
            return float(x)

    def own(x, default):
        v = _finite(x)
        return default if v is None or v < 0 else v
    n = min(int(own(attempt, 0)), 64)
    try:
        r = _finite(rng())
    except Exception:                                   # noqa: BLE001 - a caller's rng
        r = None
    r = random.random() if r is None else min(max(r, 0.0), 1.0)
    return float(r * min(own(cap, 60.0), own(base, 1.0) * 2 ** n))
