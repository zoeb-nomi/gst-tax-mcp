"""Terminal-style video renderer for the demo sessions.

Renders a list of segments (title cards and transcript screens with burned-in
subtitles) to a WebM video, using the ffmpeg binary shipped with
imageio-ffmpeg. Pure Python; no system ffmpeg needed.

Usage: python render_video.py segments.json out.webm [--fps 10] [--size 960x600]
Segment kinds:
  {"type": "title", "lines": [...], "sub": "...", "hold": 8}
  {"type": "term",  "lines": [...], "sub": "...", "hold": 6, "title": "..."}
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SIZE = (960, 600)
BG = (13, 17, 23)
PANEL = (22, 27, 34)
BAR = (33, 38, 45)
TEXT = (201, 209, 217)
DIM = (110, 124, 140)
GREEN = (63, 185, 80)
YELLOW = (210, 153, 34)
CYAN = (63, 157, 190)
WHITE = (230, 237, 243)

FONT_PATHS = ["DejaVuSansMono.ttf", "DejaVuSansMono-Bold.ttf"]


def _font(size: int, bold: bool = False):
    import PIL.ImageFont as ImageFont
    spec = importlib.util.find_spec("matplotlib")
    base = Path(spec.origin).parent / "mpl-data" / "fonts" / "ttf"
    name = FONT_PATHS[1] if bold else FONT_PATHS[0]
    return ImageFont.truetype(str(base / name), size)


def wrap(text: str, width: int) -> list[str]:
    out = []
    for para in text.split("\n"):
        if not para:
            out.append("")
            continue
        line = ""
        for word in para.split(" "):
            cand = (line + " " + word).strip()
            if len(cand) > width and line:
                out.append(line)
                line = word
            else:
                line = cand
        out.append(line)
    return out


def paginate(lines: list[str], max_lines: int) -> list[list[str]]:
    pages, cur = [], []
    for line in lines:
        cur.append(line)
        if len(cur) == max_lines:
            pages.append(cur)
            cur = []
    if cur:
        pages.append(cur)
    return pages


def render(segments: list[dict], out_path: Path, fps: int = 10,
           size=SIZE) -> Path:
    from PIL import Image, ImageDraw
    font = _font(16)
    bold = _font(17, bold=True)
    sub_font = _font(18)
    w, h = size
    max_cols = 88
    max_lines = 20

    def new_img() -> Image.Image:
        img = Image.new("RGB", size, BG)
        return img

    def title_frame(lines: list[str], sub: str) -> Image.Image:
        img = new_img()
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, w, 6], fill=GREEN)
        sizes = [30, 26, 22, 19, 17]
        fitted: list[tuple[str, int]] = []
        for ln in lines:
            for size in sizes:
                if d.textlength(ln, font=_font(size, bold=True)) <= w - 80:
                    fitted.append((ln, size))
                    break
            else:
                fitted.append((ln, sizes[-1]))
        y = h // 2 - sum(sz + 18 for _, sz in fitted) // 2
        for ln, size in fitted:
            f = _font(size, bold=True)
            tw = d.textlength(ln, font=f)
            d.text(((w - tw) / 2, y), ln, font=f, fill=WHITE)
            y += size + 18
        d.rectangle([0, h - 84, w, h], fill=PANEL)
        yy = h - 68
        for ln in wrap(sub, 74)[:2]:
            tw = d.textlength(ln, font=sub_font)
            d.text(((w - tw) / 2, yy), ln, font=sub_font, fill=DIM)
            yy += 26
        return img

    def term_pages(seg: dict) -> list[tuple[Image.Image, int]]:
        lines = []
        for raw in seg["lines"]:
            lines.extend(wrap(raw, max_cols))
        pages = paginate(lines, max_lines)
        out = []
        for pi, page in enumerate(pages):
            img = new_img()
            d = ImageDraw.Draw(img)
            d.rectangle([0, 0, w, 34], fill=BAR)
            d.text((12, 8), seg.get("title", "gst-tax-mcp"), font=bold, fill=TEXT)
            d.text((w - 150, 8), f"pg {pi + 1}/{len(pages)}", font=font, fill=DIM)
            y = 52
            for ln in page:
                color = TEXT
                if ln.startswith("$ "):
                    color = GREEN
                elif ln.startswith("# "):
                    color = YELLOW
                elif ln.startswith("== "):
                    color = CYAN
                    d.rectangle([0, y - 6, w, y + 18], fill=PANEL)
                d.text((14, y), ln, font=font, fill=color)
                y += 24
            d.rectangle([0, h - 84, w, h], fill=PANEL)
            sub = seg.get("sub", "")
            if sub:
                yy = h - 70
                for ln in wrap(sub, 84)[:2]:
                    d.text((14, yy), ln, font=font, fill=DIM)
                    yy += 26
            hold = seg.get("hold", 6)
            if pi == len(pages) - 1:
                hold = seg.get("final_hold", hold)
            out.append((img, hold))
        return out

    plan: list[tuple[Image.Image, int]] = []
    for seg in segments:
        if seg["type"] == "title":
            plan.append((title_frame(seg["lines"], seg.get("sub", "")),
                         seg.get("hold", 8)))
        else:
            plan.extend(term_pages(seg))

    total_frames = sum(int(hold * fps) for _, hold in plan)
    ffbin = importlib.util.find_spec("imageio_ffmpeg")
    ffmpeg = importlib.util.module_from_spec(ffbin)
    ffbin.loader.exec_module(ffmpeg)
    exe = ffmpeg.get_ffmpeg_exe()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [exe, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
           "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "36",
           "-deadline", "realtime", "-cpu-used", "8",
           "-row-mt", "1", str(out_path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for img, hold in plan:
        for _ in range(int(hold * fps)):
            proc.stdin.write(img.tobytes())
    proc.stdin.close()
    proc.wait()
    if proc.returncode != 0:
        raise SystemExit(f"ffmpeg failed with code {proc.returncode}")
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("segments")
    ap.add_argument("out")
    ap.add_argument("--fps", type=int, default=10)
    args = ap.parse_args()
    segments = json.loads(Path(args.segments).read_text())
    out = render(segments, Path(args.out), args.fps)
    mb = out.stat().st_size / 1e6
    print(f"video: {out} ({mb:.1f} MB)")


if __name__ == "__main__":
    main()
