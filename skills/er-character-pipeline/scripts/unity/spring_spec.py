"""Print the exact ucli.sh commands (placeholders filled from the character config) for the Unity stage.

usage: py -3 spring_spec.py --config char.json [--face-type "Gameplay.Actors.WrenFaceController, Assembly-CSharp"]
Prints, in order: guard, import_setup, enforce_tpose, avatar_check, materials_setup, prefab_build, render_views (unlit +
toon), hero_swap, weapon_mount, avatar_check again. (fix_animator_node.cs is a repair tool, not in the list.) Copy-paste them one at a time and read each result before the next.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _cfg import SKILL_DIR, load_cfg  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--face-type", default="NONE", help='e.g. "Gameplay.Actors.CharacterFaceController, Assembly-CSharp"')
    a = ap.parse_args()
    cfg = load_cfg(a.config)
    u, rc, N = cfg["unity"], cfg["rig"], cfg["name"]
    d = u["asset_dir"]
    fbx, prefab = f"{d}/{N}.fbx", f"{d}/{N}.prefab"
    springs, colls = [], set()
    for c in rc.get("chains", []):
        sp = c.get("spring")
        if not sp:
            continue
        names = [c["name"].replace("{S}", s) for s in (["L", "R"] if c.get("mirror") else [""])]
        for nm in names:
            springs.append(f"{nm}_|{sp['stiffness']}|{sp['drag']}|{sp['radius']}|{','.join(sp.get('colliders', []))}")
            colls |= set(sp.get("colliders", []))
    if rc.get("skirt") and rc["skirt"].get("spring"):
        sp = rc["skirt"]["spring"]
        springs.append(f"{rc['skirt']['name']}_|{sp['stiffness']}|{sp['drag']}|{sp['radius']}|{','.join(sp.get('colliders', []))}")
        colls |= set(sp.get("colliders", []))
    sc_ = rc.get("sleeve_chain")  # 10-08 Vesper: wide-sleeve cuff chains hang from the forearm, no colliders
    if sc_ and sc_.get("spring"):
        sp = sc_["spring"]
        for s_ in ("L", "R"):
            springs.append(f"{sc_.get('name', 'Sleeve_{S}').replace('{S}', s_)}_|{sp['stiffness']}|{sp['drag']}|{sp['radius']}|{','.join(sp.get('colliders', []))}")
            colls |= set(sp.get("colliders", []))
    for r in rc.get("rigid", []):
        sp = r.get("spring")
        if sp:
            springs.append(f"{r['bone']}|{sp['stiffness']}|{sp['drag']}|{sp['radius']}|{','.join(sp.get('colliders', []))}")
            colls |= set(sp.get("colliders", []))
    radius = u.get("collider_radius", {})
    missing = [c for c in colls if c not in radius]
    if missing:
        raise SystemExit(f"unity.collider_radius lacks {missing}")
    m = u.get("spring_manager", {})
    g = m.get("gravity", [0, -0.08, 0])
    manager = "|".join(str(x) for x in [m.get("simulationFrameRate", 60), m.get("dynamicRatio", 0.75), g[0], g[1], g[2],
                                         int(m.get("enableCollision", True)), int(m.get("enableLengthLimits", False)), int(m.get("collideWithGround", False))])
    ev = os.path.join(SKILL_DIR, "scripts", "unity", "eval").replace("\\", "/")
    U = f'bash "{os.path.join(SKILL_DIR, "scripts", "unity", "ucli.sh").replace(chr(92), "/")}"'
    e = cfg.get("emission")
    emis = f"EMISSION=1 ER={e['color'][0]} EG={e['color'][1]} EB={e['color'][2]}" if e else "EMISSION=0 ER=0 EG=0 EB=0"
    print(f'{U} guard')
    print(f'{U} eval {ev}/import_setup.cs FBX="{fbx}"')
    print(f'{U} eval {ev}/enforce_tpose.cs FBX="{fbx}"')
    print(f'{U} eval {ev}/avatar_check.cs FBX="{fbx}"')
    t = u.get("toon", {})
    sc = t.get("_ShadowColor", [0.85, 0.8, 0.85, 1])
    toon = (f'SHADOW={sc[0]},{sc[1]},{sc[2]} THRESH={t.get("_ShadowThreshold", 0.5)} SMOOTH={t.get("_ShadowSmoothing", 0.25)} '
            f'OUTLINE={t.get("_OutlineWidth", 0)} RIM={t.get("_RimThreshold", 0.9)} BASE={t.get("_BaseColor", [0.95])[0]}')
    print(f'{U} eval {ev}/materials_setup.cs DIR="{d}" NAME="{N}" FBX="{fbx}" {emis} {toon}')
    print(f'{U} eval {ev}/prefab_build.cs FBX="{fbx}" PREFAB="{prefab}" CONTROLLER="Assets/Art/Animations/Hero/HeroAnimationController.controller" '
          f'FACE_TYPE="{a.face_type}" SPRING="{";".join(springs)}" COLLIDERS="{",".join(f"{c}:{radius[c]}" for c in sorted(colls))}" MANAGER="{manager}"')
    rout = os.path.join(cfg["out_dir"], cfg["files"].get("unity_dir", "unity"), "render").replace("\\", "/")
    print(f'mkdir -p "{rout}_unlit" "{rout}_toon"')
    print(f'{U} eval {ev}/render_views.cs PREFAB="{prefab}" OUT="{rout}_unlit" LIGHTSET="Assets/Prefabs/Environment/LightSet.prefab" UNLIT=1')
    print(f'{U} eval {ev}/render_views.cs PREFAB="{prefab}" OUT="{rout}_toon" LIGHTSET="Assets/Prefabs/Environment/LightSet.prefab" UNLIT=0')
    hp = u.get("hero_prefab", "Assets/Prefabs/Heroes/Hero.prefab")
    print(f'# before hero_swap: back up the hero prefab to Assets/Temp/HeroOld.prefab (hero_swap.cs does it) and outside the project')
    print(f'{U} eval {ev}/hero_swap_keepall.cs HERO="{hp}" NEWPREFAB="{prefab}" RATIO={u.get("height_vs_old_hero", 0.9)}')
    print(f'{U} eval {ev}/weapon_mount.cs HERO="{hp}" OLDHERO="Assets/Temp/HeroOld.prefab" CLIP="{u.get("grip_reference_clip")}"')
    print(f'{U} eval {ev}/avatar_check.cs FBX="{fbx}"')


if __name__ == "__main__":
    main()
