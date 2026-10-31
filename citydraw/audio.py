"""Synthesised foley: pencil scratching, marker squeak, tape-rewind whoosh."""
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

SR = 44100


def _band(x, lo, hi):
    return sosfilt(butter(4, [lo, hi], btype="band", fs=SR, output="sos"), x)


def _env(acts, fps, value, n, smooth=0.03):
    a = np.array([1.0 if v == value else 0.0 for v in acts])
    t = np.arange(n) / SR
    e = np.interp(t, np.arange(len(a)) / fps, a)
    k = max(1, int(smooth * SR))
    return np.convolve(e, np.ones(k) / k, mode="same")


def make_soundtrack(path, acts, fps, sfx=True, rewind_start=0.0, rewind_len=1.5, seed=3, pops=()):
    n = int(len(acts) / fps * SR) + SR // 10
    rng = np.random.default_rng(seed)
    out = np.zeros(n)
    if sfx:
        t = np.arange(n) / SR
        # pencil: hand strokes back and forth (~4-6 per second), each stroke a
        # burst of graphite scratch + crackly grain; loud enough to be heard
        def strokes(rate, jitter, sharp):
            f = rate * (1 + jitter * _band(rng.normal(0, 1, n), 0.2, 2.0) * 3)
            ph = np.cumsum(f / SR)
            env = np.abs(np.sin(np.pi * ph)) ** sharp
            amp = np.repeat(rng.uniform(0.55, 1.0, int(ph[-1]) + 2), 1)[ph.astype(int)]
            return env * amp
        pen_env = _env(acts, fps, 1, n, smooth=0.015)
        scratch = _band(rng.normal(0, 1, n), 1400, 6500) + 0.45 * _band(rng.normal(0, 1, n), 350, 1400)
        grain = np.zeros(n)
        idx = rng.integers(0, n, int(n / SR * 420))
        grain[idx] = rng.uniform(-1, 1, len(idx))
        grain = _band(grain, 2500, 9000) * 6
        pencil = (scratch * (0.35 + 0.65 * strokes(4.8, 0.25, 0.7)) + grain) * pen_env
        out += 0.55 * pencil
        # marker: softer felt tip, slower strokes with a little squeak
        mk_env = _env(acts, fps, 2, n, smooth=0.02)
        felt = _band(rng.normal(0, 1, n), 500, 3000) + 0.3 * _band(rng.normal(0, 1, n), 3000, 7000)
        squeak = np.sin(2 * np.pi * np.cumsum(1800 + 300 * np.sin(2 * np.pi * 0.7 * t)) / SR) * 0.08
        out += 0.75 * (felt * (0.3 + 0.7 * strokes(3.2, 0.2, 1.2)) + squeak * strokes(3.2, 0.2, 4)) * mk_env
        # rewind whoosh: band-passed noise with rising tone
        e = _env(acts, fps, 3, n, smooth=0.12)
        if e.max() > 0:
            ph = np.cumsum(2 * np.pi * (300 + 1500 * np.clip((t - rewind_start) / max(rewind_len, .1), 0, 1) ** 2) / SR)
            whoosh = _band(rng.normal(0, 1, n), 300, 4000) * 0.35 + 0.12 * np.sin(ph)
            out += 0.5 * whoosh * e
        # hook "ding" at frame 0 and a soft pop when the art is finished
        for start, f0 in ((0.05, 1318.5), (len(acts) / fps - 3.0, 1046.5)):
            s = int(start * SR)
            if 0 <= s < n:
                L = min(n - s, int(1.2 * SR))
                tt = np.arange(L) / SR
                bell = (np.sin(2 * np.pi * f0 * tt) + .4 * np.sin(2 * np.pi * f0 * 2.01 * tt)) * np.exp(-tt * 4)
                out[s:s + L] += 0.18 * bell
        # paper pop-up "flap" for each piece folding up
        for k, tp in enumerate(pops):
            s0 = int(tp * SR)
            L = int(0.09 * SR)
            if 0 <= s0 < n - L:
                tt = np.arange(L) / SR
                burst = _band(rng.normal(0, 1, L), 300 + 40 * (k % 7), 2500) * np.exp(-tt * 45)
                out[s0:s0 + L] += 0.35 * burst
    peak = np.abs(out).max()
    if peak > 0:
        out *= 0.89 / peak          # normalise to -1 dBFS
    out = np.clip(out, -1, 1)
    wavfile.write(path, SR, (np.stack([out, out], 1) * 32767).astype(np.int16))
