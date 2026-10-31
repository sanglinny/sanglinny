"""Turn any finished, coloured line-art illustration (e.g. one you drew, or an
AI image with clear dark outlines) into a drawing/colouring timelapse plan.

Pipeline: detect dark outlines -> skeletonise -> trace into pen strokes;
regions between outlines -> group by colour (like picking up one marker at a
time) -> back-and-forth colouring paths.
"""
import numpy as np
import cv2
from PIL import Image
from scipy import ndimage
from skimage.morphology import skeletonize

from .engine import Plan, make_paper
from .planning import make_fill_jobs, order_paths_nn

NB = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def fit_on_paper(img: Image.Image, W, H, margin=0.04, paper=None):
    m = int(min(W, H) * margin)
    iw, ih = img.size
    s = min((W - 2 * m) / iw, (H - 2 * m) / ih)
    nw, nh = int(iw * s), int(ih * s)
    img = img.convert("RGB").resize((nw, nh), Image.LANCZOS)
    canvas = Image.fromarray(paper) if paper is not None else Image.new("RGB", (W, H), "white")
    canvas = canvas.copy()
    ox, oy = (W - nw) // 2, (H - nh) // 2
    canvas.paste(img, (ox, oy))
    inside = np.zeros((H, W), bool)
    inside[oy:oy + nh, ox:ox + nw] = True
    return np.asarray(canvas), inside


def ink_alpha_from(rgb, inside, strength=1.0):
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, k)
    a_dark = np.clip((110 - gray) / 60, 0, 1)                 # plain dark pixels
    a_line = np.clip((blackhat - 18) / 45, 0, 1)              # thin darker strokes
    a = np.maximum(a_dark, a_line * np.clip((170 - gray) / 80, 0, 1)) * strength
    a[~inside] = 0
    return (np.clip(a, 0, 1) * 255).astype(np.uint8)


def trace_skeleton(skel):
    """Walk a 1-px skeleton into polylines (split at junctions)."""
    H, W = skel.shape
    sk = skel.copy()
    pad = np.pad(sk, 1).astype(np.uint8)
    deg = sum(np.roll(np.roll(pad, -dy, 0), -dx, 1) for dy, dx in NB)[1:-1, 1:-1] * sk
    visited = np.zeros_like(sk)
    paths = []

    def walk(y, x):
        pts = [(x, y)]
        visited[y, x] = True
        while True:
            nxt = None
            for dy, dx in NB:
                yy, xx = y + dy, x + dx
                if 0 <= yy < H and 0 <= xx < W and sk[yy, xx] and not visited[yy, xx]:
                    nxt = (yy, xx)
                    if dy == 0 or dx == 0:
                        break
            if nxt is None:
                break
            y, x = nxt
            visited[y, x] = True
            pts.append((x, y))
            if deg[y, x] > 2:
                break
        return pts

    ys, xs = np.nonzero(sk & (deg == 1))
    for y, x in zip(ys, xs):
        if not visited[y, x]:
            paths.append(walk(y, x))
    ys, xs = np.nonzero(sk)
    for y, x in zip(ys, xs):
        if not visited[y, x]:
            paths.append(walk(y, x))
    return [np.array(p, float) for p in paths if len(p) >= 3]


def smooth(p, k=5):
    if len(p) < k + 2:
        return p
    q = ndimage.uniform_filter1d(p, k, axis=0, mode="nearest")
    q[0], q[-1] = p[0], p[-1]
    return q[::2] if len(q) > 6 else q


def plan_from_image(path, W=1920, H=1080, title="", subtitle="", outro="", n_colors=10,
                    ink_strength=1.0, min_stroke=6):
    paper = make_paper(W, H)
    rgb, inside = fit_on_paper(Image.open(path), W, H, paper=paper)
    ia = ink_alpha_from(rgb, inside, ink_strength)
    ink_mask = ia > 110
    ink_mask = ndimage.binary_opening(ink_mask, iterations=1) | (ia > 200)
    # strokes
    skel = skeletonize(ink_mask)
    dist = ndimage.distance_transform_edt(ink_mask)
    raw = trace_skeleton(skel)
    paths = []
    for p in raw:
        L = np.sum(np.hypot(*np.diff(p, axis=0).T))
        if L < min_stroke:
            continue
        xi, yi = p[:, 0].astype(int), p[:, 1].astype(int)
        w = float(np.clip(np.median(dist[yi, xi]) * 2 + 2, 2, 14))
        paths.append((smooth(p), w))
    # draw roughly top-to-bottom in bands, nearest-neighbour inside a band
    paths.sort(key=lambda pw: pw[0][:, 1].min())
    ordered, band = [], []
    band_h = H / 6
    cur_band = 0
    for pw in paths:
        b = int(pw[0][:, 1].min() // band_h)
        if b != cur_band and band:
            ordered += order_paths_nn(band, ordered[-1][0][-1] if ordered else (W / 2, 0))
            band = []
        cur_band = b
        band.append(pw)
    if band:
        ordered += order_paths_nn(band, ordered[-1][0][-1] if ordered else (W / 2, 0))

    # colour regions: areas enclosed by ink, grouped by colour cluster
    free = inside & ~ndimage.binary_dilation(ink_mask, iterations=1)
    cc, n = ndimage.label(free)
    idx = np.arange(1, n + 1)
    sizes = ndimage.sum(np.ones_like(cc), cc, idx)
    means = np.stack([ndimage.mean(rgb[..., c], cc, idx) for c in range(3)], 1).astype(np.float32)
    k = int(min(n_colors, max(1, n)))
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
    _, lab, centers = cv2.kmeans(means, k, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    lab = lab.ravel()
    # colour largest-area clusters last (sky / background), small details first
    area = np.array([sizes[lab == c].sum() for c in range(k)])
    order_clusters = list(np.argsort(area))
    labels = np.zeros_like(cc)
    keep = sizes >= 12
    lut = np.zeros(n + 1, np.int32)
    lut[1:] = np.where(keep, lab + 1, 0)
    labels = lut[cc]
    colors = {c + 1: tuple(int(v) for v in centers[c]) for c in range(k)}
    jobs = make_fill_jobs(labels, colors, [c + 1 for c in order_clusters])
    ink_rgb = rgb.copy()
    return Plan(W, H, paper, rgb, ink_rgb, ia, ordered, jobs, title, subtitle, outro)
