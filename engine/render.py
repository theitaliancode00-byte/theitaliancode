"""Render a post (posts/<id>/post.json) into 1080x1350 PNG slides + caption.txt.

Usage:  python engine/render.py posts/001-rule-cappuccino   (or "all")
"""
import json
import shutil
import subprocess
import sys
import tempfile
from html import escape
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "engine" / "style.css").as_uri()
HANDLE = "@the.italiancode"
CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]

FRAME = '<div class="frame"><i class="corner tl"></i><i class="corner tr"></i><i class="corner bl"></i><i class="corner br"></i></div>'


def chrome():
    for c in CHROME_CANDIDATES:
        if Path(c).exists():
            return c
    sys.exit("Chrome/Edge not found")


def paras(items):
    return "".join(f"<p>{p}</p>" for p in items)


def divider():
    return '<div class="divider"><span></span><b></b><span></span></div>'


def slide_body(s):
    t = s["type"]
    if t == "cover":
        rule = f'<div class="rule-no">{s["rule_no"]}</div>' if s.get("rule_no") else ""
        kicker = f'<div class="kicker">{s["kicker"]}</div>' if s.get("kicker") else ""
        sub = f'{divider()}<div class="sub">{s["sub"]}</div>' if s.get("sub") else ""
        return f'<div class="body center">{kicker}{rule}<h1>{s["title"]}</h1>{sub}</div>'
    if t == "text":
        kicker = f'<div class="kicker">{s["kicker"]}</div>' if s.get("kicker") else ""
        return f'<div class="body">{kicker}<h2>{s["heading"]}</h2>{paras(s["paragraphs"])}</div>'
    if t == "phrase":
        return (
            f'<div class="body"><div class="num">{s["num"]}</div>'
            f'<div class="phrase">{s["phrase"]}</div>'
            f'<div class="pron">{s["pron"]}</div>'
            f'<div class="meaning">{s["meaning"]}</div>'
            f'<div class="example"><div class="ex-it">{s["ex_it"]}</div><div class="ex-en">{s["ex_en"]}</div></div></div>'
        )
    if t == "list":
        kicker = f'<div class="kicker">{s["kicker"]}</div>' if s.get("kicker") else ""
        lis = "".join(f"<li><b>{a}</b><span>{b}</span></li>" for a, b in s["items"])
        return f'<div class="body">{kicker}<h2>{s["heading"]}</h2><ul class="lux">{lis}</ul></div>'
    if t == "cta":
        return (
            f'<div class="body center"><div class="kicker">{s.get("kicker", "The Italian Code")}</div>'
            f'<h1>{s["title"]}</h1>{divider()}<p style="margin:0 auto">{s["text"]}</p>'
            f'<div><span class="cta-btn">{s["button"]}</span></div></div>'
        )
    raise ValueError(f"unknown slide type {t}")


def slide_html(s, idx, total, series):
    theme = s.get("theme", "green")
    swipe = '<div class="swipe">Swipe &rarr;</div>' if idx == 1 and total > 1 else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{CSS}"></head>
<body><div class="slide t-{theme}">{FRAME}
<div class="top"><span>The Italian Code</span><span>{idx:02d} / {total:02d}</span></div>
{slide_body(s)}
{swipe}
<div class="bottom"><span>{HANDLE}</span><div class="tricolor"><i></i><i></i><i></i></div></div>
</div></body></html>"""


def screenshot(html_path: Path, png_path: Path, profile_dir: str, w=1080, h=1350):
    subprocess.run(
        [chrome(), "--headless=new", "--disable-gpu", "--hide-scrollbars",
         f"--user-data-dir={profile_dir}", f"--window-size={w},{h}",
         "--virtual-time-budget=6000", f"--screenshot={png_path}", html_path.as_uri()],
        check=True, capture_output=True,
    )


def render_post(post_dir: Path):
    post = json.loads((post_dir / "post.json").read_text(encoding="utf-8"))
    out = post_dir / "slides"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir()
    slides = post["slides"]
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for i, s in enumerate(slides, 1):
            html = tmp / f"s{i}.html"
            html.write_text(slide_html(s, i, len(slides), post["series"]), encoding="utf-8")
            png = tmp / f"s{i}.png"
            screenshot(html, png, str(tmp / "profile"))
            # Instagram's publishing API only accepts JPEG
            Image.open(png).convert("RGB").save(out / f"{i:02d}.jpg", "JPEG", quality=92, optimize=True)
    (post_dir / "caption.txt").write_text(post["caption"].strip() + "\n\n" + " ".join(post["hashtags"]) + "\n", encoding="utf-8")
    print(f"{post_dir.name}: {len(slides)} slides")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    targets = sorted(p for p in (ROOT / "posts").iterdir() if (p / "post.json").exists()) if arg == "all" else [Path(arg).resolve()]
    for t in targets:
        render_post(t)
