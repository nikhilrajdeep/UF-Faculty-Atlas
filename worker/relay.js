// Refresh relay for UF Faculty Atlas (Cloudflare Worker, free plan is enough).
//
// Why it exists: GitHub Pages is static, so a button on the site cannot start a GitHub workflow by itself,
// and putting a GitHub token in the page would expose it. This tiny server holds the token privately and
// exposes two safe endpoints to the web app:
//   GET  /status   -> latest workflow run + live progress.json written by the crawler
//   POST /refresh  -> starts a refresh (refused while one is running or if one finished very recently)
//
// Secrets/vars (set in Cloudflare, never in the repo): GITHUB_TOKEN (secret), REPO, ALLOWED_ORIGIN,
// REF (default "main"), COOLDOWN_MINUTES (default "180").

const GH = "https://api.github.com";

export default {
  async fetch(request, env, ctx) {
    const origin = request.headers.get("Origin") || "";
    const allowed = (env.ALLOWED_ORIGIN || "").split(",").map((s) => s.trim()).filter(Boolean);
    const originOk = allowed.includes(origin);
    const cors = {
      "Access-Control-Allow-Origin": originOk ? origin : allowed[0] || "",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      "Access-Control-Max-Age": "86400",
      Vary: "Origin",
    };
    const json = (body, status = 200, extra = {}) =>
      new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", ...cors, ...extra } });

    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
    const url = new URL(request.url);
    const repo = env.REPO;
    const headers = {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "User-Agent": "uf-faculty-atlas-relay",
      "X-GitHub-Api-Version": "2022-11-28",
    };

    async function latestRun() {
      const r = await fetch(`${GH}/repos/${repo}/actions/workflows/refresh.yml/runs?per_page=1&branch=${env.REF || "main"}`, { headers });
      if (!r.ok) throw new Error(`GitHub ${r.status}`);
      const run = ((await r.json()).workflow_runs || [])[0];
      return run
        ? { id: run.id, status: run.status, conclusion: run.conclusion, url: run.html_url, created_at: run.created_at, updated_at: run.updated_at, event: run.event }
        : null;
    }

    async function progress() {
      const r = await fetch(`${GH}/repos/${repo}/contents/progress.json?ref=refresh-status`, {
        headers: { ...headers, Accept: "application/vnd.github.raw+json" },
      });
      return r.ok ? await r.json().catch(() => null) : null;
    }

    function gate(run) {
      const cooldown = Number(env.COOLDOWN_MINUTES || 180) * 60000;
      if (run && (run.status === "in_progress" || run.status === "queued" || run.status === "waiting" || run.status === "pending")) {
        return { ok: false, reason: "running", message: "A refresh is already running." };
      }
      if (run && run.conclusion === "success") {
        const wait = new Date(run.updated_at).getTime() + cooldown - Date.now();
        if (wait > 0) return { ok: false, reason: "cooldown", message: `Data was refreshed recently. Try again in ${Math.ceil(wait / 60000)} minutes.`, retry_after_minutes: Math.ceil(wait / 60000) };
      }
      return { ok: true };
    }

    try {
      if (url.pathname === "/status" && request.method === "GET") {
        const cache = caches.default;
        const key = new Request(url.origin + "/status-cache");
        let hit = await cache.match(key);
        if (!hit) {
          const [run, prog] = await Promise.all([latestRun(), progress()]);
          const g = gate(run);
          const body = JSON.stringify({ run, progress: prog, can_refresh: g.ok, reason: g.reason || null, message: g.message || null });
          hit = new Response(body, { headers: { "Content-Type": "application/json", "Cache-Control": "public, max-age=8" } });
          ctx.waitUntil(cache.put(key, hit.clone()));
        }
        return new Response(await hit.text(), { headers: { "Content-Type": "application/json", ...cors } });
      }

      if (url.pathname === "/refresh" && request.method === "POST") {
        if (!originOk) return json({ error: "origin not allowed" }, 403);
        const run = await latestRun();
        const g = gate(run);
        if (!g.ok) return json({ started: false, ...g }, g.reason === "running" ? 409 : 429);
        const r = await fetch(`${GH}/repos/${repo}/actions/workflows/refresh.yml/dispatches`, {
          method: "POST",
          headers: { ...headers, "Content-Type": "application/json" },
          body: JSON.stringify({ ref: env.REF || "main", inputs: { only: "" } }),
        });
        if (r.status !== 204) return json({ started: false, message: `GitHub refused the request (${r.status}).` }, 502);
        await caches.default.delete(new Request(url.origin + "/status-cache"));
        return json({ started: true }, 202);
      }
      return json({ error: "not found" }, 404);
    } catch (e) {
      return json({ error: String(e.message || e) }, 502);
    }
  },
};
