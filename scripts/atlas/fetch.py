"""Polite, thread-safe HTTP fetcher: per-host rate limit, robots.txt, retries, size cap."""
import threading
import time
import urllib.robotparser
from urllib.parse import urlparse

import requests

from .parsers import is_uf_host

UA = "UF-Faculty-Atlas/2.0 (+https://github.com/nikhilrajdeep/UF-Faculty-Atlas; public academic directory research)"
MAX_BYTES = 4_000_000


class Fetcher:
    def __init__(self, delay=1.0, timeout=25, retries=2):
        self.delay, self.timeout, self.retries = delay, timeout, retries
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"})
        adapter = requests.adapters.HTTPAdapter(pool_connections=32, pool_maxsize=32)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self._host_lock = {}
        self._host_last = {}
        self._robots = {}
        self._glock = threading.Lock()
        self.errors = []  # (url, message)
        self.requests_made = 0
        self.cache = {}

    # -- politeness
    def _lock_for(self, host):
        with self._glock:
            return self._host_lock.setdefault(host, threading.Lock())

    def _wait(self, host, delay):
        lock = self._lock_for(host)
        with lock:
            gap = time.monotonic() - self._host_last.get(host, 0)
            if gap < delay:
                time.sleep(delay - gap)
            self._host_last[host] = time.monotonic()

    def _robots_for(self, scheme, host):
        with self._glock:
            if host in self._robots:
                return self._robots[host]
        rp = urllib.robotparser.RobotFileParser()
        try:
            self._wait(host, self.delay)
            r = self.session.get(f"{scheme}://{host}/robots.txt", timeout=10)
            if r.status_code == 200 and "html" not in r.headers.get("Content-Type", "").lower():
                rp.parse(r.text.splitlines())
            else:
                rp.parse([])
        except requests.RequestException:
            rp.parse([])
        with self._glock:
            self._robots[host] = rp
        return rp

    def crawl_delay(self, host):
        rp = self._robots.get(host)
        try:
            d = rp.crawl_delay(UA) if rp else None
        except Exception:
            d = None
        return max(self.delay, float(d)) if d else self.delay

    # -- fetching
    def get(self, url, keep=False):
        """Returns (final_url, html) or None. Never raises. Page bodies are cached only when keep=True."""
        p = urlparse(url)
        if p.scheme not in ("http", "https") or not is_uf_host(p.hostname):
            return None
        if url in self.cache:
            return self.cache[url]
        rp = self._robots_for(p.scheme, p.hostname)
        if not rp.can_fetch(UA, url):
            self.errors.append((url, "blocked by robots.txt"))
            self.cache[url] = None
            return None
        delay = self.crawl_delay(p.hostname)
        last_err = ""
        for attempt in range(self.retries + 1):
            try:
                self._wait(p.hostname, delay)
                self.requests_made += 1
                r = self.session.get(url, timeout=self.timeout, stream=True, allow_redirects=True)
                if r.status_code == 429 or r.status_code >= 500:
                    last_err = f"HTTP {r.status_code}"
                    wait = r.headers.get("Retry-After", "")
                    time.sleep(min(int(wait) if wait.isdigit() else 5 * (attempt + 1), 30))
                    continue
                if r.status_code >= 400:
                    self.errors.append((url, f"HTTP {r.status_code}"))
                    self.cache[url] = None
                    return None
                if not is_uf_host(urlparse(r.url).hostname):  # redirected off UF
                    self.cache[url] = None
                    return None
                ctype = r.headers.get("Content-Type", "text/html").lower()
                if "html" not in ctype and "xml" not in ctype:
                    self.cache[url] = None
                    return None
                body = r.raw.read(MAX_BYTES + 1, decode_content=True)
                r.encoding = r.encoding or r.apparent_encoding or "utf-8"
                text = body[:MAX_BYTES].decode(r.encoding if r.encoding else "utf-8", errors="replace")
                res = (r.url, text)
                if keep:
                    self.cache[url] = res
                return res
            except requests.RequestException as e:
                last_err = type(e).__name__
                time.sleep(2 * (attempt + 1))
        self.errors.append((url, last_err or "failed"))
        self.cache[url] = None
        return None
