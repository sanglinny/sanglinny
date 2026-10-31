"""Procedurally generated hand-drawn city scenes.

A scene is a z-ordered list of filled outlined shapes and pure ink lines.
`Scene.to_plan()` turns it into the colour / ink images + pen paths that the
engine replays.
"""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import uniform_filter1d

from .engine import Plan, make_paper
from .planning import make_fill_jobs, order_paths_nn, split_visible

INK = (38, 36, 44)


def hexrgb(c):
    if isinstance(c, (tuple, list)):
        return tuple(int(v) for v in c)
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def shade(c, k):
    c = hexrgb(c)
    if k < 1:
        return tuple(int(v * k) for v in c)
    return tuple(int(v + (255 - v) * (k - 1)) for v in c)


def ellipse_pts(cx, cy, rx, ry, a0=0, a1=2 * math.pi, n=48):
    t = np.linspace(a0, a1, n)
    return [(cx + rx * math.cos(a), cy + ry * math.sin(a)) for a in t]


class Scene:
    def __init__(self, W, H, seed=0, wobble=1.0):
        self.W, self.H = W, H
        self.items = []          # dicts
        self.groups = {}         # name -> (color, prio)
        self.rng = np.random.default_rng(seed)
        self.wobble = wobble
        self._n = 0
        self.clip = None         # (x0,y0,x1,y1): nothing is visible outside

    # -- building blocks -------------------------------------------------
    def poly(self, pts, fill, group=None, prio=50, outline=True, width=3, gradient=None):
        self._n += 1
        group = group or f"g{self._n}"
        if group not in self.groups:
            self.groups[group] = (hexrgb(fill), prio)
        self.items.append(dict(kind="poly", pts=self._wob(pts, True), group=group,
                               outline=outline, width=width, gradient=gradient))

    def rect(self, x0, y0, x1, y1, fill, **kw):
        self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], fill, **kw)

    def circle(self, cx, cy, r, fill, ry=None, **kw):
        self.poly(ellipse_pts(cx, cy, r, ry or r, n=max(16, int(r))), fill, **kw)

    def line(self, pts, width=3):
        self.items.append(dict(kind="line", pts=self._wob(pts, False), width=width))

    def _wob(self, pts, closed):
        p = np.asarray(pts, float)
        if closed:
            p = np.vstack([p, p[:1]])
        out = [p[0]]
        for a, b in zip(p[:-1], p[1:]):
            L = np.hypot(*(b - a))
            n = max(1, int(L / 9))
            for t in np.linspace(0, 1, n + 1)[1:]:
                out.append(a + (b - a) * t)
        out = np.array(out)
        if self.wobble > 0 and len(out) > 3:
            noise = self.rng.normal(0, 1, out.shape)
            noise = uniform_filter1d(noise, 5, axis=0, mode="wrap" if closed else "nearest")
            amp = self.wobble * 1.3
            if closed:
                noise[-1] = noise[0]
            out = out + noise * amp
        return out

    # -- rasterise --------------------------------------------------------
    def to_plan(self, title="", subtitle="", outro="", paper_seed=1, S=2):
        W, H = self.W, self.H
        paper = make_paper(W, H, paper_seed)
        Cimg = Image.fromarray(paper).resize((W * S, H * S))
        Limg = Image.new("L", (W * S, H * S), 0)
        lab = Image.new("I", (W, H), 0)
        dc, dl, dlab = ImageDraw.Draw(Cimg), ImageDraw.Draw(Limg), ImageDraw.Draw(lab)
        gid = {g: i + 1 for i, g in enumerate(self.groups)}
        paths = []
        zmap = Image.new("I", (W, H), -1)          # topmost outlined polygon per pixel
        dz = ImageDraw.Draw(zmap)
        prio_of = {}
        cur_prio = 0
        for z, it in enumerate(self.items):
            if it["kind"] == "poly":
                cur_prio = self.groups[it["group"]][1] if z else -1   # z=0 is the frame
            prio_of[z] = cur_prio
            pts = it["pts"]
            sp = [(x * S, y * S) for x, y in pts]
            w = it["width"]
            if it["kind"] == "poly":
                col = self.groups[it["group"]][0]
                if it["gradient"]:
                    top, bot = (hexrgb(c) for c in it["gradient"])
                    m = Image.new("L", Cimg.size, 0)
                    ImageDraw.Draw(m).polygon(sp, fill=255)
                    ys = np.linspace(0, 1, H * S)[:, None, None]
                    g = (np.array(top) * (1 - ys) + np.array(bot) * ys).astype(np.uint8)
                    g = Image.fromarray(np.broadcast_to(g, (H * S, W * S, 3)).copy())
                    Cimg.paste(g, (0, 0), m)
                else:
                    dc.polygon(sp, fill=col)
                dlab.polygon([tuple(p) for p in pts], fill=gid[it["group"]])
                if it["outline"]:
                    dl.polygon(sp, fill=0)
                    dz.polygon([tuple(p) for p in pts], fill=z)
                    dl.line(sp, fill=255, width=int(w * S), joint="curve")
                    paths.append((np.asarray(pts), w, z))
            else:
                dl.line(sp, fill=255, width=int(w * S), joint="curve")
                r = w * S / 2
                for x, y in (sp[0], sp[-1]):
                    dl.ellipse([x - r, y - r, x + r, y + r], fill=255)
                paths.append((np.asarray(pts), w, z))
        C = np.asarray(Cimg.resize((W, H), Image.LANCZOS)).astype(np.float32)
        # marker streak texture
        rng = np.random.default_rng(paper_seed + 5)
        streak = np.asarray(Image.fromarray(rng.normal(0, 1, (H // 3, W // 40)).astype(np.float32)).resize((W, H), Image.BICUBIC))
        labels = np.asarray(lab, np.int32)
        k = np.where(labels > 0, 0.022, 0.0).astype(np.float32)
        C = np.clip(C * (1 + k[..., None] * streak[..., None]), 0, 255).astype(np.uint8)
        ia = np.asarray(Limg.resize((W, H), Image.LANCZOS)).copy()
        if self.clip:
            x0, y0, x1, y1 = (int(v) for v in self.clip)
            out = np.ones((H, W), bool)
            out[y0:y1, x0:x1] = False
            labels = np.where(out, 0, labels)
            ring = np.ones((H, W), bool)               # keep the frame line itself
            ring[y0 - 4:y1 + 5, x0 - 4:x1 + 5] = False
            ia[ring] = 0
            C[out] = paper[out]
        ink_rgb = np.empty((H, W, 3), np.uint8)
        ink_rgb[:] = INK
        # line paths: drop occluded parts, keep scene order but chain nearby
        paths.sort(key=lambda t: prio_of[t[2]])   # hero landmark first, sky stuff last
        vis = split_visible(paths, ia, zmap=np.asarray(zmap, np.int32))
        lines = []
        chunk = []
        for p in vis:   # order NN inside chunks of ~25 strokes => builds up in scene order
            chunk.append(p)
            if len(chunk) >= 25:
                lines += order_paths_nn(chunk, lines[-1][0][-1] if lines else (0, 0))
                chunk = []
        lines += order_paths_nn(chunk, lines[-1][0][-1] if lines else (0, 0)) if chunk else []
        order = sorted(self.groups, key=lambda g: self.groups[g][1])
        colors = {gid[g]: self.groups[g][0] for g in self.groups}
        jobs = make_fill_jobs(labels, colors, [gid[g] for g in order])
        return Plan(W, H, paper, C, ink_rgb, ia, lines, jobs, title, subtitle, outro)
