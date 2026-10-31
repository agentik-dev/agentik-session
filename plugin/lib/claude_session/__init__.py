"""Launch Claude Code with a named profile, and keep the session handoff-ready."""
import json
import os
import re


def _pin() -> str:
    """The version, from `plugin.json`, the one pin (design/04 §6): in the plugin, its manifest;
    in a tree `make install` froze, the copy beside the package. Never raises: an import that
    fails takes every hook with it."""
    lib = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    for path in (os.path.join(os.path.dirname(lib), ".claude-plugin", "plugin.json"),
                 os.path.join(lib, "plugin.json")):
        try:
            with open(path, encoding="utf-8") as fh:
                version = json.load(fh)["version"]
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if isinstance(version, str) and version:
            return version
    return "0.0.0-unknown"


# The version in semver, the spelling plugin.json and the dependents' ranges use.
SEMVER = _pin()
# The same version as PEP 440 spells it.
__version__ = re.sub(r"-(alpha|beta)\.?", lambda m: m.group(1)[0], SEMVER)
