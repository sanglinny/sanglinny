"""City builders.  Each city = shared skyline generator + its own landmarks
and palette.  Add a new city by writing a config dict in CITIES (and, if
needed, a new landmark function)."""
from __future__ import annotations

import math

import numpy as np

from .procedural import Scene, ellipse_pts, shade

# ---------------------------------------------------------------------------
# landmarks — all take (scene, cx, base_y, h) and draw upward from base_y
# ---------------------------------------------------------------------------


def eiffel(sc: Scene, cx, by, h, color="#9a6b43", deck="#7d5434", prio=10, lattice=True):
    X = lambda u: cx + u * h
    Y = lambda v: by - v * h
    arch = ellipse_pts(cx, by, 0.17 * h, 0.13 * h, 0, -math.pi, n=24)
    sc.poly([(X(-.30), Y(0)), (X(-.115), Y(.22)), (X(.115), Y(.22)), (X(.30), Y(0)), (X(.17), Y(0))]
            + arch[1:-1] + [(X(-.17), Y(0))], color, group="eif", prio=prio)
    sc.rect(X(-.16), Y(.255), X(.16), Y(.22), deck, group="eifdeck", prio=prio)
    sc.poly([(X(-.11), Y(.255)), (X(-.055), Y(.50)), (X(.055), Y(.50)), (X(.11), Y(.255))], color, group="eif", prio=prio)
    sc.rect(X(-.075), Y(.52), X(.075), Y(.50), deck, group="eifdeck", prio=prio)
    sc.poly([(X(-.05), Y(.52)), (X(-.016), Y(.88)), (X(.016), Y(.88)), (X(.05), Y(.52))], color, group="eif", prio=prio)
    sc.rect(X(-.028), Y(.915), X(.028), Y(.88), deck, group="eifdeck", prio=prio)
    sc.poly([(X(-.008), Y(.915)), (X(0), Y(1.0)), (X(.008), Y(.915))], deck, group="eifdeck", prio=prio)
    if lattice:
        def cross(v0, v1, w0, w1, n):
            for k in range(n):
                a, b = v0 + (v1 - v0) * k / n, v0 + (v1 - v0) * (k + 1) / n
                wa, wb = w0 + (w1 - w0) * k / n, w0 + (w1 - w0) * (k + 1) / n
                sc.line([(X(-wa), Y(a)), (X(wb), Y(b))], 2)
                sc.line([(X(wa), Y(a)), (X(-wb), Y(b))], 2)
        cross(.255, .50, .10, .055, 3)
        cross(.52, .88, .045, .016, 5)
        sc.line([(X(-.235), Y(.06)), (X(-.13), Y(.20))], 2)
        sc.line([(X(.235), Y(.06)), (X(.13), Y(.20))], 2)


def clock_tower(sc: Scene, cx, by, h, stone="#d9b77a", roof="#4c5a6b", face="#fff6dc", prio=10):
    X = lambda u: cx + u * h
    Y = lambda v: by - v * h
    sc.rect(X(-.08), Y(.62), X(.08), Y(0), stone, group="ctstone", prio=prio)
    sc.rect(X(-.1), Y(.80), X(.1), Y(.62), stone, group="ctstone", prio=prio)
    sc.circle(X(0), Y(.71), .068 * h, face, group="ctface", prio=prio)
    sc.line([(X(0), Y(.71)), (X(0), Y(.755))], 3)
    sc.line([(X(0), Y(.71)), (X(.03), Y(.70))], 3)
    sc.rect(X(-.085), Y(.87), X(.085), Y(.80), shade(stone, .85), group="ctbelfry", prio=prio)
    for k in range(3):
        u = -.05 + k * .05
        sc.poly([(X(u - .015), Y(.80)), (X(u - .015), Y(.85)), (X(u), Y(.862)), (X(u + .015), Y(.85)), (X(u + .015), Y(.80))], "#5d4630", group="ctwin", prio=prio)
    sc.poly([(X(-.095), Y(.87)), (X(0), Y(1.0)), (X(.095), Y(.87))], roof, group="ctroof", prio=prio)
    for u in (-.1, .1):
        sc.poly([(X(u - .012), Y(.80)), (X(u), Y(.85)), (X(u + .012), Y(.80))], roof, group="ctroof", prio=prio)
    for v in np.linspace(.08, .55, 6):
        for u in (-.04, .04):
            sc.rect(X(u - .012), Y(v + .05), X(u + .012), Y(v), "#5d4630", group="ctwin", prio=prio)


def pagoda(sc: Scene, cx, by, h, tiers=5, wall="#c0392b", roof="#2f3b4a", prio=10):
    X = lambda u: cx + u * h
    Y = lambda v: by - v * h
    sc.rect(X(-.24), Y(.04), X(.24), Y(0), "#b9a58a", group="pgbase", prio=prio)
    th = .82 / tiers
    for k in range(tiers):
        v0 = .04 + k * th
        ww = .16 * (1 - k * .11)
        rw = ww + .09 * (1 - k * .07)
        sc.rect(X(-ww), Y(v0 + th * .62), X(ww), Y(v0), wall, group="pgwall", prio=prio)
        sc.rect(X(-ww * .35), Y(v0 + th * .5), X(ww * .35), Y(v0), "#f1c40f", group="pgdoor", prio=prio)
        # curved roof with upturned eaves
        top = v0 + th
        ro = [(X(-rw - .02), Y(v0 + th * .72)), (X(-rw), Y(v0 + th * .60))]
        ro += [(X(u), Y(v0 + th * .62 + .02 * (1 - (u / rw) ** 2))) for u in np.linspace(-rw, rw, 9)]
        ro += [(X(rw), Y(v0 + th * .60)), (X(rw + .02), Y(v0 + th * .72)),
               (X(ww * .7), Y(top)), (X(-ww * .7), Y(top))]
        sc.poly(ro, roof, group="pgroof", prio=prio)
    sc.line([(X(0), Y(.86)), (X(0), Y(1.0))], 4)
    for v in (.9, .94, .97):
        sc.line([(X(-.015), Y(v)), (X(.015), Y(v))], 3)


def mountain(sc: Scene, cx, by, h, w=1.6, rock="#6b7fa8", snow="#ffffff", prio=80):
    X = lambda u: cx + u * h
    Y = lambda v: by - v * h
    sc.poly([(X(-w / 2), Y(0)), (X(-.14), Y(.93)), (X(-.05), Y(1.0)), (X(.06), Y(.99)),
             (X(.15), Y(.92)), (X(w / 2), Y(0))], rock, group="mtn", prio=prio)
    sc.poly([(X(-.14), Y(.93)), (X(-.05), Y(1.0)), (X(.06), Y(.99)), (X(.15), Y(.92)),
             (X(.30), Y(.66)), (X(.20), Y(.72)), (X(.13), Y(.62)), (X(.05), Y(.74)), (X(-.03), Y(.60)),
             (X(-.10), Y(.72)), (X(-.19), Y(.64)), (X(-.30), Y(.66))], snow, group="snow", prio=prio)


def ferris_wheel(sc: Scene, cx, by, h, rim="#ffffff", pod="#e74c3c", prio=15):
    r = h * .44
    cy = by - h + r
    sc.poly([(cx - r * .45, by), (cx, cy), (cx + r * .45, by), (cx + r * .3, by), (cx, cy + r * .2), (cx - r * .3, by)],
            "#bdc3c7", group="fwleg", prio=prio)
    rim_pts = ellipse_pts(cx, cy, r, r, n=90)
    sc.line(rim_pts, 4)
    sc.line(ellipse_pts(cx, cy, r * .93, r * .93, n=90), 2)
    n = 16
    for k in range(n):
        a = 2 * math.pi * k / n
        sc.line([(cx, cy), (cx + r * math.cos(a), cy + r * math.sin(a))], 2)
    for k in range(n):
        a = 2 * math.pi * (k + .5) / n
        sc.circle(cx + r * 1.04 * math.cos(a), cy + r * 1.04 * math.sin(a), r * .055, pod, group="fwpod", prio=prio)
    sc.circle(cx, cy, r * .06, "#7f8c8d", group="fwhub", prio=prio)


def dome(sc: Scene, cx, by, h, wall="#f4efe6", domec="#e8e1d1", prio=40):
    X = lambda u: cx + u * h
    Y = lambda v: by - v * h
    sc.rect(X(-.45), Y(.35), X(.45), Y(0), wall, group="dmwall", prio=prio)
    for u in np.linspace(-.35, .35, 6):
        sc.poly([(X(u - .03), Y(0)), (X(u - .03), Y(.2)), (X(u), Y(.24)), (X(u + .03), Y(.2)), (X(u + .03), Y(0))], "#8e7b62", group="dmwin", prio=prio)
    sc.rect(X(-.2), Y(.5), X(.2), Y(.35), wall, group="dmwall", prio=prio)
    sc.poly(ellipse_pts(X(0), Y(.5), .2 * h, .38 * h, math.pi, 2 * math.pi, n=30), domec, group="dmdome", prio=prio)
    sc.rect(X(-.03), Y(.96), X(.03), Y(.86), wall, group="dmwall", prio=prio)
    sc.poly([(X(-.035), Y(.96)), (X(0), Y(1.0)), (X(.035), Y(.96))], domec, group="dmdome", prio=prio)
    for u in (-.33, .33):
        sc.poly(ellipse_pts(X(u), Y(.35), .07 * h, .12 * h, math.pi, 2 * math.pi, n=16), domec, group="dmdome", prio=prio)


def turtle_tower(sc: Scene, cx, by, h, wall="#e9dcc0", roof="#b0563f", prio=10):
    """Small 3-storey tower on an islet (Hoàn Kiếm lake style)."""
    X = lambda u: cx + u * h
    Y = lambda v: by - v * h
    sc.poly(ellipse_pts(cx, by + .02 * h, .55 * h, .07 * h, math.pi, 2 * math.pi, n=30) + [(X(.55), Y(-.02)), (X(-.55), Y(-.02))],
            "#6aa84f", group="islet", prio=prio)
    widths = [.22, .16, .10]
    v = 0
    for k, w in enumerate(widths):
        hh = [.30, .22, .16][k]
        sc.rect(X(-w), Y(v + hh), X(w), Y(v), wall, group="ttwall", prio=prio)
        na = 3 if k == 0 else (2 if k == 1 else 1)
        for a in range(na):
            u = -w + (2 * w) * (a + .5) / na
            aw = min(.04, w / na * .5)
            sc.poly([(X(u - aw), Y(v + .02)), (X(u - aw), Y(v + hh * .6)), (X(u), Y(v + hh * .8)),
                     (X(u + aw), Y(v + hh * .6)), (X(u + aw), Y(v + .02))], "#4a3a2c", group="ttwin", prio=prio)
        sc.poly([(X(-w - .04), Y(v + hh)), (X(-w + .02), Y(v + hh + .05)), (X(w - .02), Y(v + hh + .05)), (X(w + .04), Y(v + hh))],
                roof, group="ttroof", prio=prio)
        v += hh + .05
    sc.poly([(X(-.05), Y(v)), (X(0), Y(v + .12)), (X(.05), Y(v))], roof, group="ttroof", prio=prio)


LANDMARKS = dict(eiffel=eiffel, clock_tower=clock_tower, pagoda=pagoda, mountain=mountain,
                 ferris_wheel=ferris_wheel, dome=dome, turtle_tower=turtle_tower)


# ---------------------------------------------------------------------------
# generic city furniture
# ---------------------------------------------------------------------------

def cloud(sc, cx, cy, s, rng=None, prio=90):
    """Flat-bottomed cumulus: upper envelope of a few circles."""
    rng = rng or np.random.default_rng(0)
    w = s * 1.8
    circ = [(cx - w * .55, cy - s * .05, s * .45), (cx - w * .15, cy - s * .35, s * .7),
            (cx + w * .25, cy - s * .25, s * .6), (cx + w * .6, cy, s * .38)]
    circ = [(x + rng.uniform(-.1, .1) * s, y, r * rng.uniform(.9, 1.1)) for x, y, r in circ]
    x0 = min(x - r for x, y, r in circ)
    x1 = max(x + r for x, y, r in circ)
    base = cy + s * .3
    top = []
    for x in np.linspace(x0, x1, 70):
        ys = [y - math.sqrt(max(r * r - (x - xc) ** 2, 0)) for xc, y, r in circ if abs(x - xc) <= r]
        top.append((x, min(min(ys) if ys else base, base)))
    sc.poly([(x1, base), (x0, base)] + top, "#ffffff", group="cloud", prio=prio)


def building(sc: Scene, x0, x1, by, h, wall, roof_style, roof, win="#ffe9a8", prio=30, rng=None, tube=False):
    top = by - h
    sc.rect(x0, top, x1, by, wall, prio=prio, group=f"wall{wall}")
    w = x1 - x0
    sc.rect(x1 - w * .18, top, x1, by, shade(wall, .82), outline=False, prio=prio + 1, group=f"shd{wall}")
    if roof_style == "mansard":
        sc.poly([(x0 - 4, top), (x0 + w * .1, top - h * .14), (x1 - w * .1, top - h * .14), (x1 + 4, top)], roof, group=f"roof{roof}", prio=prio)
        for k in range(max(1, int(w // 45))):
            u = x0 + w * (k + .5) / max(1, int(w // 45))
            sc.rect(u - 7, top - h * .11, u + 7, top - h * .02, win, group="win", prio=prio + 2)
    elif roof_style == "gable":
        sc.poly([(x0 - 6, top), (x0 + w / 2, top - min(h * .3, w * .45)), (x1 + 6, top)], roof, group=f"roof{roof}", prio=prio)
    elif roof_style == "flat":
        sc.rect(x0 - 4, top - 8, x1 + 4, top, roof, group=f"roof{roof}", prio=prio)
    elif roof_style == "asian":
        sc.poly([(x0 - 16, top + 4), (x0 - 4, top - 4), (x0 + w * .2, top - h * .16), (x1 - w * .2, top - h * .16), (x1 + 4, top - 4), (x1 + 16, top + 4)],
                roof, group=f"roof{roof}", prio=prio)
    # windows grid
    cols = max(1, int(w // 34))
    rows = max(1, int((h - 30) // 46))
    cw = w / cols
    for r in range(rows):
        for c in range(cols):
            wx = x0 + c * cw + cw * .28
            wy = top + 16 + r * 46
            if wy + 26 > by - 34:
                continue
            sc.rect(wx, wy, wx + cw * .44, wy + 26, win, group="win", prio=prio + 2)
            if tube and r > 0:
                sc.line([(wx - 5, wy + 30), (wx + cw * .44 + 5, wy + 30)], 2)
    # door
    dx = x0 + w * .5
    sc.poly([(dx - 11, by), (dx - 11, by - 24), (dx, by - 32), (dx + 11, by - 24), (dx + 11, by)], "#6d4c41", group="door", prio=prio + 2)


def tree(sc, x, by, s, prio=60):
    sc.rect(x - s * .12, by - s * .9, x + s * .12, by, "#8d6e63", group="trunk", prio=prio)
    for dx, dy, r in ((0, -1.3, .55), (-.38, -1.0, .42), (.38, -1.0, .42)):
        sc.circle(x + dx * s, by + dy * s, r * s, "#5fae4e", group="leaf", prio=prio)


def build_city(cfg, W=1920, H=1080, seed=None):
    seed = cfg.get("seed", 1) if seed is None else seed
    rng = np.random.default_rng(seed)
    sc = Scene(W, H, seed=seed)
    m = int(min(W, H) * .05)
    fx0, fy0, fx1, fy1 = m, m, W - m, H - m
    fw, fh = fx1 - fx0, fy1 - fy0
    sc.clip = (fx0, fy0, fx1, fy1)
    U = min(fh, fw * 1.25)                        # unit size for landmarks
    hor = cfg.get("horizon", .74)
    if fh > fw:                                   # vertical: less sky
        hor = 1 - (1 - hor) * .72
    hy = fy0 + fh * hor

    # frame + sky
    sc.rect(fx0, fy0, fx1, fy1, cfg["sky"][1], group="sky", prio=99, gradient=cfg["sky"], width=4)
    sun = cfg.get("sun", "#ffd54f")
    if sun:
        sx, sy = cfg.get("sun_pos", (.82, .2))
        sc.circle(fx0 + fw * sx, fy0 + fh * sy, U * .1, sun, group="sun", prio=95)
    for k in range(cfg.get("clouds", 3)):
        cloud(sc, fx0 + fw * rng.uniform(.1, .9), fy0 + fh * rng.uniform(.12, .3), U * rng.uniform(.06, .09), rng)
    for k in range(cfg.get("birds", 4)):
        bx, by_ = fx0 + fw * rng.uniform(.15, .75), fy0 + fh * rng.uniform(.1, .3)
        s = U * .02
        sc.line([(bx - s, by_ - s * .5), (bx - s * .4, by_ - s * .7), (bx, by_)], 2)
        sc.line([(bx, by_), (bx + s * .4, by_ - s * .7), (bx + s, by_ - s * .5)], 2)

    # far layer: landmarks marked "far" + background skyline
    for lm in cfg["landmarks"]:
        if lm.get("far"):
            LANDMARKS[lm["type"]](sc, fx0 + fw * lm["x"], hy - fh * lm.get("lift", 0), U * lm["h"], **lm.get("args", {}))
    bgc = cfg.get("bg_buildings", "#c9d6e3")
    x = fx0
    while x < fx1:
        w = rng.uniform(.04, .08) * fw
        h = rng.uniform(.08, .2) * U
        sc.rect(x, hy - h, min(x + w, fx1), hy, bgc, group="bgb", prio=70, width=2)
        x += w * rng.uniform(.9, 1.15)
    # main landmarks
    for lm in cfg["landmarks"]:
        if not lm.get("far") and not lm.get("front"):
            LANDMARKS[lm["type"]](sc, fx0 + fw * lm["x"], hy - fh * lm.get("lift", 0), U * lm["h"], **lm.get("args", {}))

    # foreground buildings on both sides (leave a gap for the landmark)
    pal = cfg["walls"]
    roofs = cfg["roofs"]
    style = cfg.get("roof_style", "gable")
    gap = cfg.get("gap", (.36, .64))
    tube = cfg.get("tube_houses", False)
    for side in (0, 1):
        x = fx0 if side == 0 else fx0 + fw * gap[1]
        end = fx0 + fw * gap[0] if side == 0 else fx1
        while x < end - 20:
            w = min(rng.uniform(.055, .09) * fw * (.75 if tube else 1), end - x)
            if w < 30:
                break
            h = rng.uniform(.18, .34) * U
            building(sc, x, x + w, hy + U * .04, h, pal[rng.integers(len(pal))], style,
                     roofs[rng.integers(len(roofs))], rng=rng, tube=tube)
            x += w + rng.uniform(0, .01) * fw

    # ground
    gy = hy + U * .04
    g = cfg.get("ground", "river")
    if g == "river":
        sc.rect(fx0, gy, fx1, fy1, "#5aa9e6", group="water", prio=75)
        for k in range(14):
            wx = fx0 + fw * rng.uniform(.05, .9)
            wy = gy + (fy1 - gy) * rng.uniform(.2, .9)
            ww = U * rng.uniform(.03, .06)
            sc.line([(wx, wy), (wx + ww * .5, wy - 4), (wx + ww, wy)], 2)
        bx, bw = fx0 + fw * rng.uniform(.15, .65), U * .2
        byy = gy + (fy1 - gy) * .55
        sc.poly([(bx, byy), (bx + bw, byy), (bx + bw * .85, byy + bw * .18), (bx + bw * .12, byy + bw * .18)], "#ffffff", group="boat", prio=20)
        sc.rect(bx + bw * .25, byy - bw * .14, bx + bw * .7, byy, "#e74c3c", group="boatc", prio=20)
    elif g == "lake":
        sc.rect(fx0, gy, fx1, fy1, "#7cc4b8", group="water", prio=75)
        for k in range(12):
            wx = fx0 + fw * rng.uniform(.05, .9)
            wy = gy + (fy1 - gy) * rng.uniform(.25, .9)
            sc.line([(wx, wy), (wx + U * .05, wy)], 2)
    else:  # street
        sc.rect(fx0, gy, fx1, fy1, "#9e9e9e", group="road", prio=75)
        sc.rect(fx0, gy, fx1, gy + (fy1 - gy) * .22, "#d7ccc8", group="walk", prio=74)
        yy = gy + (fy1 - gy) * .6
        for k in range(10):
            xx = fx0 + fw * (k + .2) / 10
            sc.rect(xx, yy - 3, xx + fw * .045, yy + 3, "#ffffff", group="stripe", prio=73, width=2)
    # trees / lamps along the bank
    for k in range(cfg.get("trees", 5)):
        tx = fx0 + fw * rng.uniform(.03, .97)
        if gap[0] - .02 < (tx - fx0) / fw < gap[1] + .02:
            continue
        tree(sc, tx, gy + 6, U * rng.uniform(.055, .08))
    for lm in cfg["landmarks"]:
        if lm.get("front"):
            LANDMARKS[lm["type"]](sc, fx0 + fw * lm["x"], hy - fh * lm.get("lift", 0), U * lm["h"], **lm.get("args", {}))
    return sc


CITIES = {
    "paris": dict(
        title="PARIS", subtitle="France", seed=4, ground="river",
        sky=("#8ec5ff", "#ffe2c6"), sun="#ffcf5a", roof_style="mansard",
        walls=["#f3e1c2", "#efd3a8", "#f6e9d4", "#e9cfae"], roofs=["#5f6f86", "#6b7b94"],
        landmarks=[dict(type="dome", x=.18, h=.26, lift=.22, far=True),
                   dict(type="eiffel", x=.5, h=.68)],
    ),
    "london": dict(
        title="LONDON", subtitle="United Kingdom", seed=7, ground="river",
        sky=("#a7c7e7", "#eef3f7"), sun=None, roof_style="gable", clouds=5,
        walls=["#c0573f", "#d9a066", "#e6d5b8", "#b4553f"], roofs=["#3d4a5c", "#5b4a42"],
        gap=(.30, .70),
        landmarks=[dict(type="ferris_wheel", x=.63, h=.52, far=True),
                   dict(type="clock_tower", x=.42, h=.68)],
    ),
    "tokyo": dict(
        title="TOKYO", subtitle="Japan", seed=11, ground="street",
        sky=("#ffb3c1", "#fff1d6"), sun="#ff6b6b", sun_pos=(.18, .22), roof_style="flat",
        walls=["#f7f1e3", "#dfe6e9", "#ffeaa7", "#fab1a0"], roofs=["#636e72", "#2d3436"],
        landmarks=[dict(type="mountain", x=.5, h=.5, far=True, args=dict(w=1.9)),
                   dict(type="eiffel", x=.64, h=.66, args=dict(color="#e8452c", deck="#ffffff")),
                   dict(type="pagoda", x=.38, h=.5, args=dict(tiers=5))],
        gap=(.28, .74),
    ),
    "hanoi": dict(
        title="HÀ NỘI", subtitle="Việt Nam", seed=21, ground="lake",
        sky=("#9bd3f2", "#fff4d2"), sun="#ffd34e", roof_style="asian", tube_houses=True,
        walls=["#f6d26b", "#f3b562", "#9fd8cb", "#f7e3af", "#e8a0a0"], roofs=["#a8462f", "#8d3b26"],
        horizon=.66, gap=(.33, .67),
        landmarks=[dict(type="pagoda", x=.82, h=.42, far=True, lift=.02, args=dict(tiers=3, wall="#c8553d", roof="#5b3a29")),
                   dict(type="turtle_tower", x=.5, h=.46, lift=-.16, front=True)],
    ),
}
