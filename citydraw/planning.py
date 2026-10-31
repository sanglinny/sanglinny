"""Shared planning helpers: colouring paths, visibility splitting, ordering."""
import numpy as np
from scipy import ndimage

from .engine import FillJob, polyline_length


def brush_path(mask, x0, y0, brush):
    """Back-and-forth colouring path covering a boolean mask (local coords
    offset by x0,y0).  Scans along the longer side like a person would."""
    h, w = mask.shape
    transpose = h > w * 1.3
    m = mask.T if transpose else mask
    H, W = m.shape
    step = max(2.0, brush * 0.62)
    rows = np.arange(step * 0.45, H + step * 0.45, step)
    pts = []
    flip = False
    for y in rows:
        a, b = int(max(0, y - step / 2)), int(min(H, y + step / 2 + 1))
        if b <= a:
            continue
        cols = np.where(m[a:b].any(0))[0]
        if len(cols) == 0:
            continue
        inset = min(brush * 0.3, (cols[-1] - cols[0]) / 2)
        xa, xb = cols[0] + inset, cols[-1] - inset
        yy = min(y, H - 1)
        seg = [(xa, yy - step * 0.15), (xb, yy + step * 0.15)]
        if flip:
            seg = [(xb, yy - step * 0.15), (xa, yy + step * 0.15)]
        pts.extend(seg)
        flip = not flip
    if not pts:
        ys, xs = np.nonzero(m)
        pts = [(xs.mean(), ys.mean()), (xs.mean() + 1, ys.mean())]
    p = np.array(pts, float)
    if transpose:
        p = p[:, ::-1]
    p[:, 0] += x0
    p[:, 1] += y0
    return p


def brush_for(area):
    return int(np.clip(np.sqrt(area) / 7.0, 9, 70))


def make_fill_jobs(labels, label_color, order, min_px=12):
    """labels: HxW int map (0 = nothing).  order: label ids in colouring order.
    Each connected component becomes its own job, ordered nearest-neighbour
    inside its label group."""
    jobs = []
    last = None
    for lab in order:
        m = labels == lab
        if not m.any():
            continue
        cc, n = ndimage.label(m)
        objs = ndimage.find_objects(cc)
        comps = []
        for k, sl in enumerate(objs, start=1):
            if sl is None:
                continue
            sub = cc[sl] == k
            if sub.sum() < min_px:
                continue
            y0, x0 = sl[0].start, sl[1].start
            comps.append((sub, (x0, y0, sl[1].stop, sl[0].stop)))
        # nearest-neighbour order
        while comps:
            if last is None:
                k = int(np.argmin([b[1] * 10 + b[0] for _, b in comps]))
            else:
                k = int(np.argmin([np.hypot((b[0] + b[2]) / 2 - last[0], (b[1] + b[3]) / 2 - last[1]) for _, b in comps]))
            sub, bb = comps.pop(k)
            br = brush_for(sub.sum())
            path = brush_path(sub, bb[0], bb[1], br)
            jobs.append(FillJob(mask=sub, bbox=bb, path=path, brush=br, color=tuple(int(c) for c in label_color[lab])))
            last = path[-1]
    return jobs


def resample(p, step=2.0):
    p = np.asarray(p, float)
    if len(p) < 2:
        return p
    d = np.hypot(*np.diff(p, axis=0).T)
    cum = np.concatenate([[0], np.cumsum(d)])
    L = cum[-1]
    if L == 0:
        return p[:1]
    s = np.linspace(0, L, max(2, int(L / step) + 1))
    return np.stack([np.interp(s, cum, p[:, 0]), np.interp(s, cum, p[:, 1])], 1)


def split_visible(paths, ink_alpha, min_len=5, thresh=40, zmap=None):
    """Cut paths where the ink is hidden (occluded), so the pen never draws
    'invisible' lines.  paths: (pts, width[, z]).  With a z-map (index of the
    topmost polygon per pixel) a point of item z is visible only if nothing
    drawn later covers it."""
    vis = ndimage.maximum_filter(ink_alpha, size=5) > thresh
    zmin = ndimage.minimum_filter(zmap, size=5) if zmap is not None else None
    H, W = vis.shape
    out = []
    for item in paths:
        p, w = item[0], item[1]
        q = resample(p, 2.0)
        xi = np.clip(q[:, 0].round().astype(int), 0, W - 1)
        yi = np.clip(q[:, 1].round().astype(int), 0, H - 1)
        v = vis[yi, xi]
        if zmin is not None and len(item) > 2:
            v &= zmin[yi, xi] <= item[2]
        start = None
        for k, ok in enumerate(np.append(v, False)):
            if ok and start is None:
                start = k
            elif not ok and start is not None:
                seg = q[start:k]
                if len(seg) >= 2 and polyline_length(seg) >= min_len:
                    out.append((seg, w))
                start = None
    return out


def order_paths_nn(paths, start=(0, 0), allow_reverse=True):
    """Greedy nearest-neighbour ordering of strokes (vectorised)."""
    if not paths:
        return []
    starts = np.array([p[0] for p, _ in paths])
    ends = np.array([p[-1] for p, _ in paths])
    used = np.zeros(len(paths), bool)
    pos = np.array(start, float)
    out = []
    for _ in range(len(paths)):
        ds = np.hypot(*(starts - pos).T)
        de = np.hypot(*(ends - pos).T) if allow_reverse else np.full(len(paths), np.inf)
        ds[used] = np.inf
        de[used] = np.inf
        # mild bias toward top-to-bottom progress so the drawing "builds up"
        i, j = int(np.argmin(ds)), int(np.argmin(de))
        if de[j] < ds[i]:
            p, w = paths[j]
            out.append((p[::-1].copy(), w))
            used[j] = True
            pos = p[0]
        else:
            p, w = paths[i]
            out.append((p, w))
            used[i] = True
            pos = p[-1]
    return out
