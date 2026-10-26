"""Shared config loader for er-character-pipeline scripts.

Plain Python (no third-party imports) so Blender's bundled Python can import it too.
Usage inside a script:
    import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # from scripts/blender
    from _cfg import load_cfg, out_path
"""
import json
import os
import sys

# Windows consoles default to cp1252: vault paths contain Chinese -> UnicodeEncodeError on print.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLE = os.path.join(SKILL_DIR, "templates", "char_config.example.json")


def load_cfg(path):
    """Load a character JSON config and fill derived defaults."""
    if not path:
        raise SystemExit("need --config <char.json> (copy templates/char_config.example.json)")
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    for key in ("name", "slug", "workspace"):
        if not cfg.get(key):
            raise SystemExit(f"config missing '{key}'")
    cfg.setdefault("out_dir", os.path.join(cfg["workspace"], "out", f"{cfg['slug']}-tripo"))
    cfg.setdefault("blender", "F:/Apps/blender.exe")
    cfg.setdefault("files", {})
    cfg.setdefault("sheet", {})
    s = cfg["sheet"]
    s.setdefault("size", [1024, 1536]); s.setdefault("bg", 138); s.setdefault("mask_thresh", 18)
    s.setdefault("target_h_ratio", 0.88); s.setdefault("top", 92); s.setdefault("head_ratio", [0.20, 0.22])
    cfg.setdefault("rig", {}); cfg.setdefault("face", {}); cfg.setdefault("unity", {})
    cfg["_path"] = os.path.abspath(path)
    return cfg


def out_path(cfg, *parts):
    """Absolute path under the character's out_dir (parts may be a files{} key)."""
    p = os.path.join(cfg["out_dir"], *parts)
    return os.path.abspath(p)


def file_path(cfg, key, required=True):
    """Resolve cfg['files'][key] relative to out_dir; absolute paths pass through."""
    v = cfg.get("files", {}).get(key)
    if not v:
        if required:
            raise SystemExit(f"config files.{key} not set - fill it after the stage that produces it")
        return None
    return v if os.path.isabs(v) else out_path(cfg, v)


def vault_path(cfg, rel):
    if not rel:
        return None
    return rel if os.path.isabs(rel) else os.path.join(cfg["vault_char_dir"], rel)


def blender_args(argv):
    """Arguments after '--' when run as: blender -b --python x.py -- args."""
    return argv[argv.index("--") + 1:] if "--" in argv else []
