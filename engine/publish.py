"""Publish due carousels from schedule.json to Instagram via the official
Instagram API (Instagram Login, Content Publishing).

Env:
  IG_ACCESS_TOKEN   long-lived Instagram user token (GitHub secret)
  GITHUB_REPOSITORY owner/repo, used to build public raw image URLs
  IG_API_VERSION    optional, default v24.0

Usage:  python engine/publish.py [--dry-run]
Publishes at most one post per run; records results in published.json.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEDULE = ROOT / "schedule.json"
LOG = ROOT / "published.json"
API = f"https://graph.instagram.com/{os.environ.get('IG_API_VERSION', 'v24.0')}"
BRANCH = "main"


def call(method, path, **params):
    params["access_token"] = os.environ["IG_ACCESS_TOKEN"]
    data = urllib.parse.urlencode(params).encode()
    url = f"{API}/{path}"
    if method == "GET":
        req = urllib.request.Request(f"{url}?{data.decode()}")
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"API error on {path}: {e.code} {e.read().decode(errors='replace')}")


def wait_ready(container_id, tries=20):
    for _ in range(tries):
        status = call("GET", container_id, fields="status_code").get("status_code")
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            sys.exit(f"container {container_id} failed: {status}")
        time.sleep(5)
    sys.exit(f"container {container_id} not ready in time")


def image_urls(post_id):
    repo = os.environ["GITHUB_REPOSITORY"]
    slides = sorted((ROOT / "posts" / post_id / "slides").glob("*.jpg"))
    return [f"https://raw.githubusercontent.com/{repo}/{BRANCH}/posts/{post_id}/slides/{s.name}" for s in slides]


def publish(post_id):
    caption = (ROOT / "posts" / post_id / "caption.txt").read_text(encoding="utf-8").strip()
    user = call("GET", "me", fields="user_id,username")
    uid = user["user_id"]
    children = []
    for url in image_urls(post_id):
        children.append(call("POST", f"{uid}/media", image_url=url, is_carousel_item="true")["id"])
    for c in children:
        wait_ready(c)
    carousel = call("POST", f"{uid}/media", media_type="CAROUSEL", children=",".join(children), caption=caption)["id"]
    wait_ready(carousel)
    return call("POST", f"{uid}/media_publish", creation_id=carousel)["id"]


def main():
    dry = "--dry-run" in sys.argv
    schedule = json.loads(SCHEDULE.read_text(encoding="utf-8"))
    log = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else {}
    if os.environ.get("IG_ACCESS_TOKEN"):
        print(f"connected as @{call('GET', 'me', fields='username')['username']}")
    now = datetime.now(timezone.utc)
    due =[e for e in schedule if e["post"] not in log and datetime.fromisoformat(e["at"]) <= now]
    if not due:
        print("nothing due")
        return
    entry = min(due, key=lambda e: datetime.fromisoformat(e["at"]))
    if dry:
        print(f"[dry-run] would publish {entry['post']} ({len(list((ROOT / 'posts' / entry['post'] / 'slides').glob('*.jpg')))} slides)")
        return
    if not os.environ.get("IG_ACCESS_TOKEN"):
        print("IG_ACCESS_TOKEN not set yet - skipping")
        return
    media_id = publish(entry["post"])
    log[entry["post"]] = {"media_id": media_id, "published_at": now.isoformat(timespec="seconds")}
    LOG.write_text(json.dumps(log, indent=2) + "\n", encoding="utf-8")
    print(f"published {entry['post']} -> {media_id}")


if __name__ == "__main__":
    main()
