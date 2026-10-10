import React, { useCallback, useEffect, useState } from 'react';
import { loadFaculty, loadMeta, fmt, fmtDate } from './data.js';
import Faculty from './Faculty.jsx';
import Coverage from './Coverage.jsx';

const TABS = [
  ['faculty', 'Faculty directory'],
  ['coverage', 'Data coverage'],
];

export default function App() {
  const [tab, setTab] = useState(() => (['faculty', 'coverage'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'faculty'));
  const [meta, setMeta] = useState(null);
  const [db, setDb] = useState(null);
  const [error, setError] = useState('');
  const [openId, setOpenId] = useState(null);

  const go = (t) => { setTab(t); history.replaceState(null, '', `#${t}`); window.scrollTo(0, 0); };

  const loadAll = useCallback(async () => {
    try {
      const m = await loadMeta();
      setMeta(m);
      setDb(await loadFaculty(m?.revision || m?.updated_at));
      setError('');
    } catch (e) {
      setError('The faculty database could not be loaded. Please try again in a few minutes.');
    }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  const totalDepts = meta?.departments ?? 0;
  return (
    <div className="layout">
      <aside>
        <div className="logo">{'◉'} UF <span>FACULTY ATLAS</span></div>
        <p className="sub">RESEARCH DISCOVERY</p>
        {TABS.map(([id, label]) => (
          <button key={id} className={tab === id ? 'active' : ''} onClick={() => go(id)}>{label}</button>
        ))}
        <small>Independent directory built from public UF web pages {'•'} Not an official UF product</small>
      </aside>
      <main>
        <header>
          <span>UNIVERSITY OF FLORIDA / {tab.toUpperCase()}</span>
          <a href="https://www.ufl.edu/" target="_blank" rel="noreferrer">ufl.edu {'↗'}</a>
        </header>
        {error && <div className="banner">{error}</div>}
        {tab === 'faculty' && (
          <Faculty db={db} meta={meta} totalDepts={totalDepts} openId={openId} setOpenId={setOpenId} />
        )}
        {tab === 'coverage' && <Coverage meta={meta} />}
        <footer className="foot">
          {db ? `${fmt(db.items.length)} faculty records` : 'Loading…'} {'•'} Updated {fmtDate(meta?.updated_at)}
        </footer>
      </main>
    </div>
  );
}
