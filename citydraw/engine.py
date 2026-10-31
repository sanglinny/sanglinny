"""Timelapse renderer: hook (finished colour) -> rewind to blank paper -> pen
draws the line art -> marker colours it -> outro.

Everything is driven by a `Plan` (see below).  The renderer never "draws" the
art itself: the finished colour image and the finished ink image are prepared
up-front, and the pen only paints *reveal masks* along its path.  That keeps
the final frame pixel-identical to the hook frame, and lets the same renderer
work for procedurally generated cities and for any illustration you import.
"""
from __future__ import annotations

import io
import math
import os
import subprocess
import tempfile
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_TITLE = os.path.join(ROOT, "assets", "fonts", "Baloo2-ExtraBold.ttf")
FONT_HAND = os.path.join(ROOT, "assets", "fonts", "PatrickHand-Regular.ttf")


# --------------------------------------------------------------------------
# data model
# --------------------------------------------------------------------------
@dataclass
class FillJob:
    mask: np.ndarray          # bool, cropped to bbox
    bbox: tuple               # x0, y0, x1, y1 (x1/y1 exclusive)
    path: np.ndarray          # (N,2) float, absolute coords, brush centre line
    brush: int                # brush width in px
    color: tuple              # marker colour (for the pen sprite)


@dataclass
class Plan:
    W: int
    H: int
    paper: np.ndarray         # HxWx3 uint8 blank paper
    color: np.ndarray         # HxWx3 uint8 finished colouring (no ink needed)
    ink_rgb: np.ndarray       # HxWx3 uint8 ink colour per pixel
    ink_alpha: np.ndarray     # HxW uint8 ink coverage
    line_paths: list          # [(np.ndarray (N,2), width_px)]
    fill_jobs: list           # [FillJob]
    title: str = ""
    subtitle: str = ""
    outro: str = ""
    meta: dict = field(default_factory=dict)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def make_paper(W, H, seed=1, tint=(250, 248, 242)):
    rng = np.random.default_rng(seed)
    base = np.ones((H, W, 3), np.float32) * np.array(tint, np.float32)
    fine = rng.normal(0, 2.2, (H, W, 1)).astype(np.float32)
    coarse = rng.normal(0, 1, (H // 16 + 2, W // 16 + 2)).astype(np.float32)
    coarse = np.asarray(Image.fromarray(coarse).resize((W, H), Image.BICUBIC))[..., None]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    vign = 1 - 0.05 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    out = (base + fine + coarse * 2.5) * vign[..., None]
    return np.clip(out, 0, 255).astype(np.uint8)


def polyline_length(p):
    if len(p) < 2:
        return 0.0
    return float(np.sum(np.hypot(*np.diff(p, axis=0).T)))


def _cum(p):
    d = np.hypot(*np.diff(p, axis=0).T)
    return np.concatenate([[0], np.cumsum(d)])


def _sub_polyline(p, cum, s0, s1):
    """Points of polyline p between arc lengths s0..s1."""
    def at(s):
        i = int(np.clip(np.searchsorted(cum, s) - 1, 0, len(p) - 2))
        seg = cum[i + 1] - cum[i]
        t = 0 if seg <= 0 else (s - cum[i]) / seg
        return p[i] + (p[i + 1] - p[i]) * t
    i0 = np.searchsorted(cum, s0, side="right")
    i1 = np.searchsorted(cum, s1, side="left")
    pts = [at(s0)] + [p[i] for i in range(i0, i1)] + [at(s1)]
    return np.array(pts)


def _bbox_of(pts, pad, W, H):
    x0 = int(max(0, math.floor(pts[:, 0].min() - pad)))
    y0 = int(max(0, math.floor(pts[:, 1].min() - pad)))
    x1 = int(min(W, math.ceil(pts[:, 0].max() + pad + 1)))
    y1 = int(min(H, math.ceil(pts[:, 1].max() + pad + 1)))
    return x0, y0, x1, y1


def _stroke(draw, pts, width, value=255, offset=(0, 0)):
    ox, oy = offset
    q = [(float(x - ox), float(y - oy)) for x, y in pts]
    if len(q) >= 2:
        draw.line(q, fill=value, width=int(width), joint="curve")
    r = width / 2
    for x, y in (q[0], q[-1]):
        draw.ellipse([x - r, y - r, x + r, y + r], fill=value)


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)


# --------------------------------------------------------------------------
# pen sprites
# --------------------------------------------------------------------------
def _rot(pts, ang):
    c, s = math.cos(ang), math.sin(ang)
    return [(x * c - y * s, x * s + y * c) for x, y in pts]


def make_tool_sprite(kind, color=(40, 40, 40), length=330, angle_deg=-58):
    """RGBA sprite + tip offset.  The tool lies along +x (tip at origin) and
    is rotated so it points down-left like a right hand holding it."""
    S = 3
    L, Wd = length * S, (30 if kind == "pencil" else 44) * S
    shapes = []
    if kind == "pencil":
        cone = 70 * S
        shapes.append(([(0, 0), (cone, -Wd / 2), (cone, Wd / 2)], (236, 200, 150)))      # wood
        shapes.append(([(0, 0), (cone * .33, -Wd / 6), (cone * .33, Wd / 6)], color))     # lead
        shapes.append(([(cone, -Wd / 2), (L - 60 * S, -Wd / 2), (L - 60 * S, Wd / 2), (cone, Wd / 2)], (246, 190, 40)))
        shapes.append(([(cone, -Wd / 6), (L - 60 * S, -Wd / 6), (L - 60 * S, Wd / 6), (cone, Wd / 6)], (255, 214, 90)))
        shapes.append(([(L - 60 * S, -Wd / 2), (L - 30 * S, -Wd / 2), (L - 30 * S, Wd / 2), (L - 60 * S, Wd / 2)], (190, 190, 196)))
        shapes.append(([(L - 30 * S, -Wd / 2), (L, -Wd / 2.4), (L, Wd / 2.4), (L - 30 * S, Wd / 2)], (240, 140, 150)))
    else:  # marker
        tipL = 34 * S
        shapes.append(([(0, -Wd / 7), (tipL, -Wd / 4), (tipL, Wd / 4), (0, Wd / 7)], color))
        shapes.append(([(tipL, -Wd / 2.6), (tipL + 40 * S, -Wd / 2), (tipL + 40 * S, Wd / 2), (tipL, Wd / 2.6)], (235, 235, 238)))
        shapes.append(([(tipL + 40 * S, -Wd / 2), (L, -Wd / 2), (L, Wd / 2), (tipL + 40 * S, Wd / 2)], (250, 250, 252)))
        shapes.append(([(L - 120 * S, -Wd / 2), (L, -Wd / 2), (L, Wd / 2), (L - 120 * S, Wd / 2)], color))
        shapes.append(([(tipL + 60 * S, -Wd / 2), (L - 140 * S, -Wd / 2), (L - 140 * S, -Wd / 4), (tipL + 60 * S, -Wd / 4)], (255, 255, 255)))
    ang = math.radians(angle_deg)
    allp = [q for pts, _ in shapes for q in _rot(pts, ang)]
    minx = min(p[0] for p in allp) - 40 * S
    miny = min(p[1] for p in allp) - 40 * S
    maxx = max(p[0] for p in allp) + 40 * S
    maxy = max(p[1] for p in allp) + 40 * S
    w, h = int(maxx - minx), int(maxy - miny)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for pts, col in shapes:
        q = [(x - minx, y - miny) for x, y in _rot(pts, ang)]
        d.polygon(q, fill=tuple(col) + (255,), outline=(60, 50, 40, 255), width=2 * S)
    img = img.resize((w // S, h // S), Image.LANCZOS)
    tip = (-minx / S, -miny / S)
    a = np.asarray(img)[..., 3]
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow.putalpha(Image.fromarray((a * 0.28).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)))
    return img, shadow, tip


class ToolBox:
    def __init__(self, scale=1.0):
        self.scale = scale
        self._cache = {}

    def get(self, kind, color):
        key = (kind, tuple(color))
        if key not in self._cache:
            img, sh, tip = make_tool_sprite(kind, color, length=int(330 * self.scale))
            self._cache[key] = (img, sh, tip)
        return self._cache[key]


# --------------------------------------------------------------------------
# canvas state
# --------------------------------------------------------------------------
class Canvas:
    def __init__(self, plan: Plan):
        self.p = plan
        self.Ml = Image.new("L", (plan.W, plan.H), 0)
        self.dl = ImageDraw.Draw(self.Ml)
        self.Mc = np.zeros((plan.H, plan.W), np.uint8)
        self.frame = plan.paper.copy()
        self._paper = plan.paper.astype(np.float32)
        self._color = plan.color.astype(np.float32)
        self._ink = plan.ink_rgb.astype(np.float32)
        self._ia = plan.ink_alpha.astype(np.float32) / 255.0

    def recompose(self, bb):
        x0, y0, x1, y1 = bb
        if x1 <= x0 or y1 <= y0:
            return
        sl = (slice(y0, y1), slice(x0, x1))
        ac = (self.Mc[sl].astype(np.float32) / 255.0)[..., None]
        f = self._paper[sl] * (1 - ac) + self._color[sl] * ac
        ml = np.asarray(self.Ml.crop(bb), np.float32) / 255.0
        al = (ml * self._ia[sl])[..., None]
        f = f * (1 - al) + self._ink[sl] * al
        self.frame[sl] = np.clip(f + 0.5, 0, 255).astype(np.uint8)

    def ink_segment(self, pts, width):
        w = max(2, width + 2)
        _stroke(self.dl, pts, w)
        self.recompose(_bbox_of(pts, w, self.p.W, self.p.H))

    def color_segment(self, job: FillJob, jimg, jdraw, pts):
        x0, y0, x1, y1 = job.bbox
        _stroke(jdraw, pts, job.brush, offset=(x0, y0))
        bx0, by0, bx1, by1 = _bbox_of(pts, job.brush, self.p.W, self.p.H)
        bx0, by0 = max(bx0, x0), max(by0, y0)
        bx1, by1 = min(bx1, x1), min(by1, y1)
        if bx1 <= bx0 or by1 <= by0:
            return
        lx0, ly0, lx1, ly1 = bx0 - x0, by0 - y0, bx1 - x0, by1 - y0
        brush = np.asarray(jimg.crop((lx0, ly0, lx1, ly1)))
        m = job.mask[ly0:ly1, lx0:lx1]
        sub = self.Mc[by0:by1, bx0:bx1]
        np.maximum(sub, np.where(m, brush, 0).astype(np.uint8), out=sub)
        self.recompose((bx0, by0, bx1, by1))

    def finish_job(self, job: FillJob):
        x0, y0, x1, y1 = job.bbox
        sub = self.Mc[y0:y1, x0:x1]
        sub[job.mask] = 255
        self.recompose(job.bbox)

    def finish_all(self):
        self.Mc[:] = 255
        self.Ml.paste(255, (0, 0, self.p.W, self.p.H))
        self.recompose((0, 0, self.p.W, self.p.H))


# --------------------------------------------------------------------------
# stroke scheduler
# --------------------------------------------------------------------------
TRAVEL_COST = 0.22   # moving with the pen lifted is ~5x faster than drawing


def schedule(strokes, n_frames, start_pos):
    """strokes: list of (path, payload).  Returns list (per frame) of lists of
    events: ('draw', idx, s0, s1) | ('end', idx), plus pen positions / lift."""
    lens = [polyline_length(p) for p, _ in strokes]
    pos = np.array(start_pos, float)
    total = 0.0
    for (p, _), L in zip(strokes, lens):
        total += np.hypot(*(p[0] - pos)) * TRAVEL_COST + L
        pos = p[-1]
    speed = max(total / max(n_frames, 1), 1e-6)
    frames = []
    budget = 0.0
    pos = np.array(start_pos, float)
    i, s, travelling = 0, 0.0, True
    cum = [_cum(p) if len(p) > 1 else np.zeros(1) for p, _ in strokes]
    for _ in range(n_frames):
        budget += speed
        ev = []
        lift = 0.0
        while budget > 1e-9 and i < len(strokes):
            p = strokes[i][0]
            if travelling:
                dist = np.hypot(*(p[0] - pos))
                need = dist * TRAVEL_COST
                if need <= budget:
                    budget -= need
                    pos = p[0].copy()
                    travelling = False
                    s = 0.0
                else:
                    t = budget / need
                    pos = pos + (p[0] - pos) * t
                    budget = 0
                    lift = 1.0
            else:
                L = lens[i]
                take = min(L - s, budget)
                if L > 0:
                    ev.append(("draw", i, s, s + take))
                s += take
                budget -= take
                if L > 0:
                    c = cum[i]
                    j = int(np.clip(np.searchsorted(c, s) - 1, 0, len(p) - 2))
                    seg = c[j + 1] - c[j]
                    t = 0 if seg <= 0 else (s - c[j]) / seg
                    pos = p[j] + (p[j + 1] - p[j]) * t
                if s >= L - 1e-6:
                    ev.append(("end", i))
                    i += 1
                    travelling = True
        frames.append((ev, pos.copy(), lift))
    # flush anything left by float error
    if i < len(strokes):
        rest = []
        for k in range(i, len(strokes)):
            rest.append(("draw", k, 0 if k > i else s, lens[k]))
            rest.append(("end", k))
        frames[-1][0].extend(rest)
    return frames


# --------------------------------------------------------------------------
# overlays
# --------------------------------------------------------------------------
def draw_title(img: Image.Image, text, sub="", alpha=1.0, y_frac=0.13, size_frac=0.11):
    if not text or alpha <= 0:
        return img
    W, H = img.size
    base = min(W, H)
    f = font(FONT_TITLE, int(base * size_frac))
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    a = int(255 * alpha)
    tw = d.textlength(text, font=f)
    x, y = (W - tw) / 2, H * y_frac
    sw = max(4, int(base * size_frac * 0.09))
    d.text((x + sw * .6, y + sw * .9), text, font=f, fill=(0, 0, 0, int(a * .35)), stroke_width=sw, stroke_fill=(0, 0, 0, int(a * .35)))
    d.text((x, y), text, font=f, fill=(255, 255, 255, a), stroke_width=sw, stroke_fill=(30, 30, 40, a))
    if sub:
        f2 = font(FONT_HAND, int(base * size_frac * 0.42))
        tw2 = d.textlength(sub, font=f2)
        y2 = y + base * size_frac * 1.25
        d.text(((W - tw2) / 2, y2), sub, font=f2, fill=(255, 255, 255, a), stroke_width=max(3, sw // 2), stroke_fill=(30, 30, 40, a))
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def draw_badge(img: Image.Image, text, kind="ff", alpha=1.0):
    """Small 'x16 >>' fast-forward / '<<' rewind badge in the corner."""
    if alpha <= 0:
        return img
    W, H = img.size
    s = int(min(W, H) * 0.05)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    a = int(220 * alpha)
    pad = int(s * 0.6)
    x, y = W - pad - int(s * 3.6), pad
    d.rounded_rectangle([x, y, x + s * 3.6, y + s * 1.25], radius=s // 2, fill=(20, 20, 24, int(a * .75)))
    tri = s * 0.42
    cx, cy = x + s * 0.55, y + s * 0.625
    for k in range(2):
        ox = cx + k * tri * 0.95
        if kind == "ff":
            d.polygon([(ox, cy - tri), (ox + tri, cy), (ox, cy + tri)], fill=(255, 255, 255, a))
        else:
            d.polygon([(ox + tri, cy - tri), (ox, cy), (ox + tri, cy + tri)], fill=(255, 255, 255, a))
    f = font(FONT_TITLE, int(s * 0.8))
    d.text((x + s * 1.75, y + s * 0.12), text, font=f, fill=(255, 255, 255, a))
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


# --------------------------------------------------------------------------
# ffmpeg
# --------------------------------------------------------------------------
class VideoWriter:
    def __init__(self, path, W, H, fps, crf=18):
        self.proc = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
             "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "medium",
             "-crf", str(crf), "-pix_fmt", "yuv420p", "-r", str(fps), path],
            stdin=subprocess.PIPE)
        self.n = 0

    def write(self, frame):
        if isinstance(frame, Image.Image):
            frame = np.asarray(frame.convert("RGB"))
        self.proc.stdin.write(np.ascontiguousarray(frame, dtype=np.uint8).tobytes())
        self.n += 1

    def close(self):
        self.proc.stdin.close()
        if self.proc.wait() != 0:
            raise RuntimeError("ffmpeg failed")


# --------------------------------------------------------------------------
# main render
# --------------------------------------------------------------------------
@dataclass
class Timing:
    fps: int = 30
    hook: float = 2.6
    rewind: float = 1.6
    blank: float = 0.5
    draw: float = 40.0
    color: float = 40.0
    outro: float = 4.0
    speed_label: str = "x16"


def _place_tool(img: Image.Image, tools: ToolBox, kind, color, pos, lift, jitter):
    spr, sh, tip = tools.get(kind, color)
    x = pos[0] - tip[0] + jitter[0]
    y = pos[1] - tip[1] + jitter[1] - lift * 14
    so = 10 + lift * 22
    img.paste(sh, (int(x + so), int(y + so)), sh)
    img.paste(spr, (int(x), int(y)), spr)


def render(plan: Plan, out_path, timing: Timing = Timing(), badge=True, audio=True,
           music=None, music_volume=0.25, log=print):
    W, H, fps = plan.W, plan.H, timing.fps
    tools = ToolBox(scale=min(W, H) / 1080)
    rng = np.random.default_rng(7)
    tmpdir = tempfile.mkdtemp(prefix="citydraw_")
    part2 = os.path.join(tmpdir, "part2.mp4")
    part1 = os.path.join(tmpdir, "part1.mp4")

    cv = Canvas(plan)
    n_draw = int(timing.draw * fps)
    n_col = int(timing.color * fps)
    n_rew = int(timing.rewind * fps)
    snaps = []                       # JPEG snapshots of the forward process
    snap_every = max(1, (n_draw + n_col) // max(n_rew, 1))
    activity = []                    # per frame: 0 idle, 1 pencil, 2 marker

    vw = VideoWriter(part2, W, H, fps)
    offscreen = np.array([W * 1.1, H * 1.2])

    def snap(frame_np):
        b = io.BytesIO()
        Image.fromarray(frame_np).save(b, "JPEG", quality=90)
        snaps.append(b.getvalue())

    # ---- pencil: line art ------------------------------------------------
    log(f"  drawing {len(plan.line_paths)} strokes over {n_draw} frames")
    strokes = [(p, w) for p, w in plan.line_paths if len(p) >= 2]
    sched = schedule(strokes, n_draw, offscreen)
    cums = [_cum(p) for p, _ in strokes]
    fidx = 0
    for k, (ev, pos, lift) in enumerate(sched):
        moved = False
        for e in ev:
            if e[0] == "draw":
                _, i, s0, s1 = e
                if s1 > s0:
                    cv.ink_segment(_sub_polyline(strokes[i][0], cums[i], s0, s1), strokes[i][1])
                    moved = True
        img = Image.fromarray(cv.frame)
        jit = rng.normal(0, 0.6, 2) if moved else (0, 0)
        _place_tool(img, tools, "pencil", (50, 50, 55), pos, lift, jit)
        if badge:
            img = draw_badge(img, timing.speed_label, "ff", min(1, k / fps * 2))
        vw.write(img)
        activity.append(1 if moved else 0)
        if fidx % snap_every == 0:
            snap(cv.frame)
        fidx += 1
    cv.Ml.paste(255, (0, 0, W, H))
    cv.recompose((0, 0, W, H))

    # ---- marker: colouring -----------------------------------------------
    log(f"  colouring {len(plan.fill_jobs)} regions over {n_col} frames")
    jobs = [j for j in plan.fill_jobs if len(j.path) >= 2]
    sched = schedule([(j.path, j) for j in jobs], n_col, sched[-1][1] if sched else offscreen)
    jcums = [_cum(j.path) for j in jobs]
    jimgs = {}
    cur = jobs[0].color if jobs else (0, 0, 0)
    for k, (ev, pos, lift) in enumerate(sched):
        moved = False
        for e in ev:
            if e[0] == "draw":
                _, i, s0, s1 = e
                j = jobs[i]
                cur = j.color
                if i not in jimgs:
                    x0, y0, x1, y1 = j.bbox
                    im = Image.new("L", (x1 - x0, y1 - y0), 0)
                    jimgs[i] = (im, ImageDraw.Draw(im))
                if s1 > s0:
                    cv.color_segment(j, *jimgs[i], _sub_polyline(j.path, jcums[i], s0, s1))
                    moved = True
            else:
                cv.finish_job(jobs[e[1]])
                jimgs.pop(e[1], None)
        if not moved and ev == [] and lift and k + 1 < len(sched):
            # peek: show the colour of the next region while travelling
            for e in sched[k + 1][0]:
                if e[0] == "draw":
                    cur = jobs[e[1]].color
                    break
        img = Image.fromarray(cv.frame)
        jit = rng.normal(0, 1.0, 2) if moved else (0, 0)
        _place_tool(img, tools, "marker", cur, pos, lift, jit)
        if badge:
            img = draw_badge(img, timing.speed_label, "ff")
        vw.write(img)
        activity.append(2 if moved else 0)
        if fidx % snap_every == 0:
            snap(cv.frame)
        fidx += 1
    cv.finish_all()
    final = cv.frame.copy()

    # ---- outro: tool leaves, title appears -------------------------------
    n_out = int(timing.outro * fps)
    start = sched[-1][1] if sched else offscreen
    for k in range(n_out):
        t = k / max(n_out - 1, 1)
        img = Image.fromarray(final)
        if t < 0.35:
            e = (t / 0.35) ** 2
            pos = start + (offscreen - start) * e
            _place_tool(img, tools, "marker", cur, pos, e, (0, 0))
        ta = np.clip((t - 0.25) / 0.2, 0, 1)
        img = draw_title(img, plan.title, plan.outro or plan.subtitle, ta)
        vw.write(img)
        activity.append(0)
    vw.close()

    # ---- part 1: hook + rewind ------------------------------------------
    log("  hook + rewind")
    vw = VideoWriter(part1, W, H, fps)
    n_hook = int(timing.hook * fps)
    fin_img = Image.fromarray(final)
    for k in range(n_hook):
        t = k / max(n_hook - 1, 1)
        z = 1.10 - 0.10 * (1 - (1 - t) ** 3)       # zoom out 1.10 -> 1.00
        cw, ch = W / z, H / z
        x0, y0 = (W - cw) / 2, (H - ch) * 0.45
        img = fin_img.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))
        ta = np.clip(t / 0.18, 0, 1) * np.clip((1 - t) / 0.15, 0, 1)
        img = draw_title(img, plan.title, plan.subtitle, ta)
        vw.write(img)
    # rewind: play snapshots backwards, accelerating, with tape wobble
    order = list(range(len(snaps) - 1, -1, -1))
    for k in range(n_rew):
        t = k / max(n_rew - 1, 1)
        e = t * t * (3 - 2 * t)
        idx = order[min(len(order) - 1, int(e * len(order)))] if order else 0
        if snaps:
            img = Image.open(io.BytesIO(snaps[idx])).convert("RGB")
        else:
            img = Image.fromarray(plan.paper)
        if k == 0:
            img = fin_img.copy()
        arr = np.asarray(img).copy()
        # horizontal tape-glitch bands
        for _ in range(3):
            yb = rng.integers(0, H - 8)
            hb = rng.integers(2, 10)
            arr[yb:yb + hb] = np.roll(arr[yb:yb + hb], rng.integers(-30, 30), axis=1)
        img = Image.fromarray(arr)
        img = draw_badge(img, "", "rw")
        vw.write(img)
    for k in range(int(timing.blank * fps)):
        vw.write(plan.paper)
    vw.close()
    n_part1 = n_hook + n_rew + int(timing.blank * fps)

    # ---- join + audio ----------------------------------------------------
    joined = os.path.join(tmpdir, "joined.mp4")
    lst = os.path.join(tmpdir, "list.txt")
    with open(lst, "w") as fh:
        fh.write(f"file '{part1}'\nfile '{part2}'\n")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
                    "-c", "copy", joined], check=True)
    if not audio and not music:
        os.replace(joined, out_path)
        return out_path
    from .audio import make_soundtrack
    wav = os.path.join(tmpdir, "sfx.wav")
    acts = [0] * n_hook + [3] * n_rew + [0] * int(timing.blank * fps) + activity
    make_soundtrack(wav, acts, fps, sfx=audio, rewind_start=n_hook / fps, rewind_len=timing.rewind)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", joined, "-i", wav]
    if music:
        cmd += ["-stream_loop", "-1", "-i", music, "-filter_complex",
                f"[2:a]volume={music_volume},afade=t=out:st={len(acts)/fps-2:.2f}:d=2[m];[1:a][m]amix=inputs=2:duration=first:normalize=0[a]",
                "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", out_path]
    subprocess.run(cmd, check=True)
    return out_path
