import React, { useCallback, useEffect, useRef, useState } from 'react';
import { fmt, fmtDate, fmtEta, loadMeta } from './data.js';

const STAGES = { starting: 'starting', discover: 'finding departments', departments: 'reading department lists', profiles: 'reading faculty profiles', merge: 'merging records' };

// Refresh is started and watched entirely from this page. The browser talks to a small relay (config.refreshApi)
// that holds the GitHub credential, so visitors never go to GitHub and no secret is ever shipped in the page.

export default function Updates({ config, meta, onNewData }) {
  const api = (config.refreshApi || '').replace(/\/$/, '');
  const repo = config.repository;
  const [status, setStatus] = useState(null); // {run, progress, can_refresh, message}
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState('');
  const [publishing, setPublishing] = useState(false);
  const baseline = useRef(meta?.updated_at);
  const wasRunning = useRef(false);

  const poll = useCallback(async () => {
    try {
      if (api) {
        const r = await fetch(`${api}/status`);
        if (r.ok) setStatus(await r.json());
      } else if (repo) {
        // read-only fallback: the crawler's last published progress (GitHub caches this file for a few minutes)
        const r = await fetch(`https://raw.githubusercontent.com/${repo}/refresh-status/progress.json?t=${Date.now()}`);
        setStatus({ progress: r.ok ? await r.json() : null, run: null, can_refresh: false });
      }
    } catch { /* offline: keep last status */ }
  }, [api, repo]);

  const p = status?.progress;
  const running = !!(p && p.state === 'running' && (!status?.run || status.run.status !== 'completed'));
  useEffect(() => { baseline.current = baseline.current || meta?.updated_at; }, [meta?.updated_at]);

  useEffect(() => {
    poll();
    const t = setInterval(poll, running || busy ? 4000 : 30000);
    return () => clearInterval(t);
  }, [poll, running, busy]);

  // When a run finishes, wait for GitHub Pages to publish the new files, then reload the data.
  useEffect(() => {
    if (running) { wasRunning.current = true; return undefined; }
    if (!wasRunning.current || p?.state !== 'success') return undefined;
    setPublishing(true);
    const t = setInterval(async () => {
      const m = await loadMeta();
      if (m?.updated_at && m.updated_at !== baseline.current) {
        baseline.current = m.updated_at; wasRunning.current = false; setPublishing(false); onNewData(); clearInterval(t);
      }
    }, 15000);
    return () => clearInterval(t);
  }, [running, p?.state, onNewData]);

  async function refresh() {
    setBusy(true); setNote('');
    try {
      const r = await fetch(`${api}/refresh`, { method: 'POST' });
      const j = await r.json().catch(() => ({}));
      setNote(j.started ? 'Refresh started. This page will show live progress.' : j.message || 'The refresh could not be started.');
      await poll();
    } catch { setNote('Could not reach the refresh service.'); }
    setBusy(false);
  }

  const c = p?.counts || {};
  const pct = running ? p.percent : p?.state === 'success' ? 100 : p?.percent || 0;
  const label = running ? 'Refreshing' : p?.state === 'success' ? 'Up to date' : p?.state === 'failed' ? 'Last refresh failed' : 'Idle';

  return (
    <>
      <h1 className="page-title">Database updates.</h1>
      <p>Faculty come from UF department websites and the graduate catalog. A refresh re-reads about a hundred department sites, so it takes a while; the bar below is based on pages actually read, not a timer.</p>

      <section className="update">
        <h2>{label}{running && p?.stage ? ` — ${STAGES[p.stage] || p.stage}` : ''}</h2>
        <div className="bar" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}><div className={running ? 'live' : ''} style={{ width: `${pct}%` }} /></div>
        <div className="bar-meta"><h3>{Math.round(pct)}%</h3><span>{running ? [p?.message, fmtEta(p?.eta_seconds)].filter(Boolean).join(' · ') : p?.message || 'No refresh in progress.'}</span></div>
        {(running || p?.state === 'success') && c.units_total > 0 && (
          <p className="muted">Departments {fmt(c.units_done)}/{fmt(c.units_total)} {'·'} Profiles {fmt(c.profiles_done)}/{fmt(c.profiles_total)} {'·'} Faculty found {fmt(c.faculty)} {'·'} Students {fmt(c.students)}</p>
        )}
        {publishing && <p className="note">Finished crawling. Publishing the new data to the site {'—'} this page reloads it automatically.</p>}
        {p?.state === 'failed' && <p className="note bad">The last refresh failed. The previous data is still in use. {p.run_url && <a href={p.run_url} target="_blank" rel="noreferrer">Details {'↗'}</a>}</p>}

        {api ? (
          <>
            <button className="action" onClick={refresh} disabled={busy || running || status?.can_refresh === false}>
              {running ? 'Refresh in progress…' : busy ? 'Starting…' : 'Refresh database now'}
            </button>
            {!running && status?.can_refresh === false && status?.message && <p className="muted">{status.message}</p>}
            {note && <p className="muted">{note}</p>}
          </>
        ) : (
          <p className="note">One-time setup needed to start refreshes from this page: deploy the small refresh relay in <code>worker/</code> and put its address in <code>config.json</code> (see README). Progress of any running refresh is still shown here.</p>
        )}
      </section>

      <section className="update">
        <h2>Current data</h2>
        <p>{fmt(meta?.faculty)} faculty {'·'} {fmt(meta?.students)} students {'·'} {fmt(meta?.departments)} departments {'·'} last refreshed {fmtDate(meta?.updated_at)}</p>
        <p className="muted small">Data is compiled automatically from public pages and can contain gaps or mistakes. The Data coverage tab shows exactly which departments were read successfully.</p>
      </section>
    </>
  );
}
