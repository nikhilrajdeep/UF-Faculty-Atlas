import React, { useCallback, useEffect, useState } from 'react';
import { loadConfig, loadFaculty, loadMeta, fmt, fmtDate } from './data.js';
import Faculty from './Faculty.jsx';
import Students from './Students.jsx';
import Coverage from './Coverage.jsx';
import Updates from './Updates.jsx';

const TABS = [
  ['faculty', 'Faculty directory'],
  ['students', 'Graduate students'],
  ['coverage', 'Data coverage'],
  ['updates', '↻ Database updates'],
];

export default function App() {
  const [tab, setTab] = useState(() => (location.hash.slice(1) || 'faculty'));
  const [config, setConfig] = useState({});
  const [meta, setMeta] = useState(null);
  const [db, setDb] = useState(null);
  const [error, setError] = useState('');
  const [openId, setOpenId] = useState(null);

  const go = (t) => { setTab(t); history.replaceState(null, '', `#${t}`); window.scrollTo(0, 0); };

  const loadAll = useCallback(async () => {
    try {
      const m = await loadMeta();
      setMeta(m);
      setDb(await loadFaculty(m?.updated_at));
      setError('');
    } catch (e) {
      setError('The faculty database could not be loaded. Open Database updates to refresh it.');
    }
  }, []);

  useEffect(() => { loadConfig().then(setConfig); loadAll(); }, [loadAll]);

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
          <span>UNIVERSITY OF FLORIDA / {tab === 'updates' ? 'DATA OPERATIONS' : tab.toUpperCase()}</span>
          <a href="https://www.ufl.edu/" target="_blank" rel="noreferrer">ufl.edu {'↗'}</a>
        </header>
        {error && <div className="banner">{error}</div>}
        {tab === 'faculty' && (
          <Faculty db={db} meta={meta} totalDepts={totalDepts} openId={openId} setOpenId={setOpenId} goStudents={() => go('students')} />
        )}
        {tab === 'students' && <Students db={db} meta={meta} openFaculty={(id) => { setOpenId(id); go('faculty'); }} />}
        {tab === 'coverage' && <Coverage meta={meta} />}
        {tab === 'updates' && <Updates config={config} meta={meta} onNewData={loadAll} />}
        <footer className="foot">
          {db ? `${fmt(db.items.length)} faculty records` : 'Loading…'} {'•'} Updated {fmtDate(meta?.updated_at)}
        </footer>
      </main>
    </div>
  );
}
