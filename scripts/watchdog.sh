#!/usr/bin/env bash
# Diagnostics for hung crawls: every few minutes, snapshot the crawler's Python stacks and push them
# to the 'refresh-debug' branch so a stall can be diagnosed without access to the live log.
pip install -q py-spy >/dev/null 2>&1 || exit 0
while sleep "${WATCHDOG_EVERY:-100}"; do
  pid=$(pgrep -f "atlas.crawl" | head -1)
  [ -z "$pid" ] && continue
  d=$(mktemp -d)
  { date -u; sudo env "PATH=$PATH" py-spy dump --pid "$pid" 2>&1 | head -150; echo; ps -o pid,pcpu,pmem,rss,etime,cmd -p "$pid"; free -m; echo "--- crawl.log tail"; tail -40 /tmp/crawl.log 2>/dev/null; } > "$d/stacks.txt" 2>&1
  ( cd "$d" && git init -q -b refresh-debug && git add . \
    && git -c user.name=atlas-bot -c user.email=atlas-bot@users.noreply.github.com commit -q -m dbg \
    && git -c "http.https://github.com/.extraheader=AUTHORIZATION: basic $(printf 'x-access-token:%s' "$GITHUB_TOKEN" | base64 -w0)" \
       push -q -f "https://github.com/$GITHUB_REPOSITORY.git" refresh-debug:refresh-debug ) >/dev/null 2>&1
  rm -rf "$d"
done
