"""Federal interior fixtures for the J01 kit (pilot.json "furniture" kinds).

Every builder takes a kitlib.Part, the footprint centre (cx, cy) in Blender XY, and the pilot size
(sx = width along X, h = height, sd = depth along Y). Fronts face -Y (towards the V5 camera / room side).
Boxy federal language: shell-white bodies, panel-grey frames, dark bases, small handles; glow only on screens.
"""


def _feet(p, x0, y0, x1, y1, h=0.12, inset=0.06):
    p.box(x0 + inset, y0 + inset, -0.05, x1 - inset, y1 - inset, h, "dark")


def rack(p, cx, cy, sx, h, sd, goods=True):
    x0, x1, y0, y1 = cx - sx / 2, cx + sx / 2, cy - sd / 2, cy + sd / 2
    post = 0.12
    for x in (x0, x1 - post):
        for y in (y0, y1 - post):
            p.box(x, y, -0.05, x + post, y + post, h, "panel")
    levels = [0.15, 0.85, 1.55, h - 0.08]
    for z in levels:
        p.box(x0 + 0.02, y0 + 0.02, z, x1 - 0.02, y1 - 0.02, z + 0.08, "shell")
        p.box(x0, y0, z - 0.06, x1, y0 + 0.1, z + 0.02, "panel")        # front lip
    p.box(x0 + post, y1 - 0.06, 0.15, x1 - post, y1, h - 0.08, "shell_in")  # back panel
    if goods:
        # closed goods crates on the lower two shelves, a gap left on purpose (empty slot = no search)
        bw = (sx - 0.5) / 3
        for i, z in enumerate(levels[:2]):
            for j in range(3):
                if (i, j) in ((0, 2), (1, 0)):
                    continue
                bx = x0 + 0.18 + j * (bw + 0.07)
                hh = 0.52 if i == 0 else 0.46
                p.box(bx, y0 + 0.16, z + 0.08, bx + bw, y1 - 0.14, z + 0.08 + hh, "shell")
                p.box(bx - 0.02, y0 + 0.14, z + 0.08 + hh - 0.08, bx + bw + 0.02, y1 - 0.12, z + 0.08 + hh,
                      "panel")
                p.box(bx + bw / 2 - 0.12, y0 + 0.12, z + 0.08 + hh * 0.45, bx + bw / 2 + 0.12, y0 + 0.16,
                      z + 0.08 + hh * 0.6, "dark")


def container(p, cx, cy, sx, h, sd):
    """Federal tote / crate: shell body, panel-grey corner frame, lid band, side handles, latch."""
    x0, x1, y0, y1 = cx - sx / 2, cx + sx / 2, cy - sd / 2, cy + sd / 2
    p.box(x0 + 0.06, y0 + 0.06, 0.0, x1 - 0.06, y1 - 0.06, h - 0.06, "shell")
    p.box(x0, y0, -0.05, x1, y1, 0.16, "dark")                              # base skid
    p.box(x0 + 0.02, y0 + 0.02, h - 0.28, x1 - 0.02, y1 - 0.02, h - 0.16, "panel")  # lid seam band
    p.box(x0 + 0.04, y0 + 0.04, h - 0.16, x1 - 0.04, y1 - 0.04, h, "shell")         # lid
    c = 0.14
    for x in (x0, x1 - c):
        for y in (y0, y1 - c):
            p.box(x, y, 0.0, x + c, y + c, h - 0.02, "panel")                  # corner posts
    for x in (x0 - 0.04, x1 - 0.02):
        p.box(x, cy - 0.3, h * 0.5, x + 0.06, cy + 0.3, h * 0.5 + 0.12, "dark")  # side handles
    p.box(cx - 0.18, y0 - 0.03, h - 0.42, cx + 0.18, y0 + 0.04, h - 0.18, "dark")  # latch
    p.box(cx - 0.08, y0 - 0.05, h - 0.34, cx + 0.08, y0 - 0.02, h - 0.28, "glow")


def cabinet(p, cx, cy, sx, h, sd):
    """Tall locker: two (or more) doors with vertical handles, dark plinth, top cap."""
    x0, x1, y0, y1 = cx - sx / 2, cx + sx / 2, cy - sd / 2, cy + sd / 2
    p.box(x0 + 0.03, y0 + 0.05, 0.12, x1 - 0.03, y1, h - 0.1, "shell_in")
    p.box(x0, y0 + 0.02, -0.05, x1, y1, 0.14, "dark")
    p.box(x0 - 0.02, y0, h - 0.12, x1 + 0.02, y1 + 0.02, h, "panel")
    n = max(2, int(round(sx / 0.9)))
    dw = (sx - 0.12) / n
    for i in range(n):
        a = x0 + 0.06 + i * dw
        p.box(a + 0.025, y0, 0.2, a + dw - 0.025, y0 + 0.07, h - 0.18, "shell")
        hx = a + dw - 0.16 if i % 2 == 0 else a + 0.1
        p.box(hx, y0 - 0.04, h * 0.42, hx + 0.06, y0 + 0.02, h * 0.62, "dark")
    p.box(x0, y0 + 0.02, -0.05, x0 + 0.06, y1, h - 0.1, "panel")
    p.box(x1 - 0.06, y0 + 0.02, -0.05, x1, y1, h - 0.1, "panel")


def drawer(p, cx, cy, sx, h, sd):
    """Tool chest: three drawer rows (blue-grey fronts), wide handles, top work surface."""
    x0, x1, y0, y1 = cx - sx / 2, cx + sx / 2, cy - sd / 2, cy + sd / 2
    p.box(x0 + 0.03, y0 + 0.05, 0.12, x1 - 0.03, y1, h - 0.08, "shell_in")
    p.box(x0, y0 + 0.02, -0.05, x1, y1, 0.14, "dark")
    p.box(x0 - 0.03, y0 - 0.03, h - 0.1, x1 + 0.03, y1 + 0.03, h, "panel")
    rows = 3
    rh = (h - 0.3) / rows
    for r in range(rows):
        z = 0.16 + r * rh
        for k, (a, b) in enumerate(((x0 + 0.06, cx - 0.03), (cx + 0.03, x1 - 0.06))):
            p.box(a, y0, z + 0.03, b, y0 + 0.07, z + rh - 0.03, "panel")
            m = (a + b) / 2
            p.box(m - 0.3, y0 - 0.05, z + rh * 0.55, m + 0.3, y0 + 0.01, z + rh * 0.55 + 0.07, "shell")


def desk(p, cx, cy, sx, h, sd):
    """Duty desk with terminal (glow screen, <5%) + one chair on the -Y side. h = desk+screen height."""
    dd = min(1.0, sd * 0.5)
    y1 = cy + sd / 2
    y0 = y1 - dd
    x0, x1 = cx - sx / 2, cx + sx / 2
    top = 0.86
    p.box(x0, y0, top - 0.07, x1, y1, top, "shell")
    p.box(x0, y0 + 0.04, top - 0.2, x1, y1, top - 0.07, "panel")
    for x in (x0 + 0.05, x1 - 0.55):
        p.box(x, y0 + 0.1, -0.05, x + 0.5, y1 - 0.05, top - 0.2, "panel")   # side pedestals
    p.box(x1 - 0.5, y0 + 0.08, 0.1, x1 - 0.1, y0 + 0.12, top - 0.26, "shell_in")
    # terminal: tilted slab approximated by a block + screen
    tx = cx - 0.2
    p.box(tx - 0.55, y1 - 0.35, top, tx + 0.55, y1 - 0.15, top + 0.08, "dark")
    p.box(tx - 0.5, y1 - 0.28, top + 0.08, tx + 0.5, y1 - 0.18, h, "panel")
    p.box(tx - 0.42, y1 - 0.3, top + 0.16, tx + 0.42, y1 - 0.27, h - 0.08, "glow")
    # paper stack + handover tray (unfinished handover record)
    p.box(cx + 0.45, y0 + 0.25, top, cx + 0.85, y0 + 0.55, top + 0.06, "shell")
    # chair
    chx, chy = cx - 0.2, y0 - 0.45
    p.box(chx - 0.3, chy - 0.28, 0.42, chx + 0.3, chy + 0.28, 0.52, "panel")
    p.box(chx - 0.28, chy + 0.22, 0.52, chx + 0.28, chy + 0.3, 1.05, "panel")
    p.box(chx - 0.05, chy - 0.05, 0.08, chx + 0.05, chy + 0.05, 0.42, "dark")
    p.box(chx - 0.32, chy - 0.32, -0.02, chx + 0.32, chy + 0.32, 0.08, "dark")


def repair(p, cx, cy, sx, h, sd):
    """Teardown bench with an EMPTY drive mount: saddle blocks, opened clamp bands, pressed outline."""
    x0, x1, y0, y1 = cx - sx / 2, cx + sx / 2, cy - sd / 2, cy + sd / 2
    top = 0.95
    p.box(x0, y0, top - 0.12, x1, y1, top, "shell")
    p.box(x0 + 0.05, y0 + 0.05, top - 0.3, x1 - 0.05, y1 - 0.05, top - 0.12, "panel")
    for x in (x0 + 0.1, x1 - 0.32):
        for y in (y0 + 0.1, y1 - 0.32):
            p.box(x, y, -0.05, x + 0.22, y + 0.22, top - 0.3, "panel")
    p.box(x0 + 0.1, y0 + 0.2, 0.25, x1 - 0.1, y1 - 0.2, 0.33, "dark")       # low stretcher shelf
    # empty drive mount: two saddles + pressed rectangle where the drive sat
    mx = cx
    p.box(mx - 1.15, cy - 0.75, top, mx + 1.15, cy + 0.75, top + 0.03, "seam")  # pressed footprint
    for dx in (-0.85, 0.85):
        p.box(mx + dx - 0.16, cy - 0.6, top, mx + dx + 0.16, cy + 0.6, top + 0.34, "dark")
        # opened clamp band: half ring standing up, left open
        p.box(mx + dx - 0.07, cy - 0.66, top + 0.34, mx + dx + 0.07, cy - 0.5, h, "panel")
        p.box(mx + dx - 0.07, cy - 0.66, h - 0.12, mx + dx + 0.07, cy - 0.05, h, "panel")
    # loosened bolts / small parts tray
    p.box(x1 - 0.7, y0 + 0.2, top, x1 - 0.15, y0 + 0.6, top + 0.08, "panel")


BUILDERS = {"rack": rack, "container": container, "cabinet": cabinet, "drawer": drawer, "desk": desk,
            "repair": repair}
