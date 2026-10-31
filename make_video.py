#!/usr/bin/env python3
"""Make one "draw a city" timelapse video.

Examples
  python make_video.py --city paris                       # built-in city, 16:9
  python make_video.py --city hanoi --short               # 9:16 YouTube Shorts
  python make_video.py --image my_city.png --title "ROMA" # your own illustration
  python make_video.py --list
"""
import argparse
import os
import sys
import time

from citydraw.engine import Timing, render


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--city", help="built-in city key (see --list)")
    src.add_argument("--image", help="finished coloured line-art image to replay")
    ap.add_argument("--list", action="store_true", help="list built-in cities")
    ap.add_argument("--title", help="override title text")
    ap.add_argument("--subtitle", help="override subtitle text")
    ap.add_argument("--outro", default=None, help="text under the title at the end (e.g. 'Which city next?')")
    ap.add_argument("--short", action="store_true", help="vertical 1080x1920 (Shorts/TikTok/Reels)")
    ap.add_argument("--size", default=None, help="WxH, default 1920x1080")
    ap.add_argument("--draw", type=float, default=None, help="seconds of pencil drawing")
    ap.add_argument("--color", type=float, default=None, help="seconds of colouring")
    ap.add_argument("--hook", type=float, default=2.6)
    ap.add_argument("--rewind", type=float, default=1.6)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--speed-label", default="x16", help="text on the fast-forward badge")
    ap.add_argument("--no-badge", action="store_true")
    ap.add_argument("--no-sfx", action="store_true", help="no synthesised pencil/marker sounds")
    ap.add_argument("--music", help="background music file (mixed under the sfx)")
    ap.add_argument("--music-volume", type=float, default=0.25)
    ap.add_argument("--seed", type=int, default=None, help="change to get a different skyline")
    ap.add_argument("--colors", type=int, default=10, help="(--image) number of marker colours")
    ap.add_argument("-o", "--out", help="output .mp4 path")
    a = ap.parse_args()

    from citydraw.cities import CITIES, build_city
    if a.list or not (a.city or a.image):
        print("Built-in cities:", ", ".join(CITIES))
        return
    if a.size:
        W, H = map(int, a.size.lower().split("x"))
    elif a.short:
        W, H = 1080, 1920
    else:
        W, H = 1920, 1080

    t0 = time.time()
    if a.city:
        if a.city not in CITIES:
            sys.exit(f"unknown city {a.city!r}; choose from {', '.join(CITIES)}")
        cfg = CITIES[a.city]
        sc = build_city(cfg, W, H, seed=a.seed)
        plan = sc.to_plan(a.title or cfg["title"], a.subtitle if a.subtitle is not None else cfg.get("subtitle", ""),
                          a.outro if a.outro is not None else cfg.get("outro", ""))
        name = a.city
    else:
        from citydraw.from_image import plan_from_image
        name = os.path.splitext(os.path.basename(a.image))[0]
        plan = plan_from_image(a.image, W, H, a.title or "", a.subtitle or "", a.outro or "", n_colors=a.colors)
    print(f"plan: {len(plan.line_paths)} pen strokes, {len(plan.fill_jobs)} colour regions ({time.time() - t0:.1f}s)")

    short = H > W
    timing = Timing(fps=a.fps, hook=a.hook, rewind=a.rewind,
                    draw=a.draw if a.draw is not None else (20 if short else 40),
                    color=a.color if a.color is not None else (20 if short else 40),
                    speed_label=a.speed_label)
    out = a.out or os.path.join("output", f"{name}{'_short' if short else ''}.mp4")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    render(plan, out, timing, badge=not a.no_badge, audio=not a.no_sfx, music=a.music,
           music_volume=a.music_volume)
    print(f"done -> {out}  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
