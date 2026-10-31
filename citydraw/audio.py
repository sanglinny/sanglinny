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
        # pencil: bright grainy noise, amplitude flutter from hand motion
        pen = _band(rng.normal(0, 1, n), 2200, 7500)
        flutter = 0.55 + 0.45 * np.abs(np.sin(2 * np.pi * 7.3 * t + 2 * np.sin(2 * np.pi * 0.9 * t)))
        grain = _band(rng.normal(0, 1, n), 20, 60)
        grain = 0.7 + 0.6 * grain / (np.abs(grain).max() + 1e-9)
        out += 0.16 * pen * flutter * grain * _env(acts, fps, 1, n)
        # marker: softer, lower, a little squeaky
        mk = _band(rng.normal(0, 1, n), 500, 2600)
        sw = 0.6 + 0.4 * np.abs(np.sin(2 * np.pi * 4.1 * t))
        out += 0.13 * mk * sw * _env(acts, fps, 2, n)
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
    out = np.clip(out, -1, 1)
    wavfile.write(path, SR, (np.stack([out, out], 1) * 32767).astype(np.int16))
