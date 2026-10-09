"""Publish live crawl progress to a single-commit 'refresh-status' branch (no history growth).

The web app (via the refresh relay) reads progress.json from that branch to draw its progress bar.
Only runs inside GitHub Actions; elsewhere it is a no-op.
"""
import base64
import json
import os
import subprocess
import tempfile
from pathlib import Path

STATUS_BRANCH = "refresh-status"


def enabled():
    return bool(os.getenv("GITHUB_ACTIONS") and os.getenv("GITHUB_TOKEN") and os.getenv("GITHUB_REPOSITORY"))


def push_status(files):
    """files: {name: text}. Force-pushes them as one orphan commit to the status branch."""
    if not enabled():
        return False
    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    tmp = Path(tempfile.mkdtemp(prefix="atlas-status-"))
    try:
        for name, text in files.items():
            (tmp / name).write_text(text, encoding="utf-8")

        def git(*args):
            return subprocess.run(
                ["git", "-c", "user.name=atlas-bot", "-c", "user.email=atlas-bot@users.noreply.github.com", *args],
                cwd=tmp, env=env, capture_output=True, text=True, timeout=90,
            )

        git("init", "-q", "-b", STATUS_BRANCH)
        git("add", ".")
        git("commit", "-q", "-m", "status")
        r = git("-c", f"http.https://github.com/.extraheader=AUTHORIZATION: basic {basic}", "push", "-q", "-f",
                f"https://github.com/{repo}.git", f"{STATUS_BRANCH}:{STATUS_BRANCH}")
        if r.returncode != 0:
            print(f"status push failed: {r.stderr[-300:]}", flush=True)
        return r.returncode == 0
    except Exception as e:
        print(f"status push error: {type(e).__name__}: {e}", flush=True)
        return False
    finally:
        subprocess.run(["rm", "-rf", str(tmp)], check=False)


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default
