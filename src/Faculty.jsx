import React, { useDeferredValue, useEffect, useMemo, useRef, useState } from 'react';
import { TOPICS, download, fmt, fmtDate, matchesQuery, toCsv } from './data.js';

const PAGE = 48;

export default function Faculty({ db, meta, openId, setOpenId }) {
  const [q, setQ] = useState('');
  const [college, setCollege] = useState('');
  const [dept, setDept] = useState('');
  const [topic, setTopic] = useState(-1);
  const [only, setOnly] = useState({ email: false, scholar: false, students: false, research: false });
  const [limit, setLimit] = useState(PAGE);
  const deferredQ = useDeferredValue(q);

  const shown = useMemo(() => {
    if (!db) return [];
    const bit = topic >= 0 ? 1 << topic : 0;
    const out = db.items.filter((f) =>
      (!college || f._colleges.includes(college)) &&
      (!dept || f._depts.includes(dept)) &&
      (!bit || (f._topics & bit)) &&
      (!only.email || f.email) && (!only.scholar || f.google_scholar) &&
      (!only.students || f.current_students?.length) && (!only.research || f.research_areas?.length) &&
      matchesQuery(f._q, deferredQ));
    // better-documented profiles first when browsing, alphabetical when searching a name
    return deferredQ ? out : out.sort((a, b) => b._rich - a._rich || a.name.localeCompare(b.name));
  }, [db, college, dept, topic, only, deferredQ]);

  useEffect(() => setLimit(PAGE), [college, dept, topic, only, deferredQ]);

  const sentinel = useRef(null);
  useEffect(() => {
    if (!sentinel.current) return undefined;
    const io = new IntersectionObserver((e) => e[0].isIntersecting && setLimit((n) => n + PAGE), { rootMargin: '600px' });
    io.observe(sentinel.current);
    return () => io.disconnect();
  }, [shown.length, limit]);

  const chosen = useMemo(() => (openId && db ? db.items.find((f) => f.id === openId) : null), [openId, db]);
  const departments = db ? db.deptsOf(college) : [];
  const toggle = (k) => setOnly((o) => ({ ...o, [k]: !o[k] }));

  const exportCsv = () => download('uf-faculty.csv', toCsv(shown, [
    { label: 'Name', get: (f) => f.name }, { label: 'Title', get: (f) => f.title }, { label: 'College', get: (f) => f.college },
    { label: 'Department', get: (f) => f.department }, { label: 'Email', get: (f) => f.email },
    { label: 'Research areas', get: (f) => (f.research_areas || []).join('; ') }, { label: 'Teaching', get: (f) => (f.teaching || []).join('; ') },
    { label: 'Extension', get: (f) => (f.extension || []).join('; ') }, { label: 'Google Scholar', get: (f) => f.google_scholar },
    { label: 'Lab', get: (f) => f.lab_url }, { label: 'UF profile', get: (f) => f.profile_url },
    { label: 'Current students', get: (f) => (f.current_students || []).map((s) => `${s.name}${s.program ? ` (${s.program})` : ''}`).join('; ') },
  ]));

  return (
    <>
      <section className="hero">
        <span>DISCOVER UF RESEARCHERS</span>
        <h1>Find the minds<br />behind the <em>research.</em></h1>
        <p>Search faculty across UF colleges and departments by research interests, teaching, Google Scholar, and current students.</p>
      </section>
      <section className="stats">
        <div><b>{db ? fmt(db.items.length) : '…'}</b><span>Faculty records</span></div>
        <div><b>{db ? db.colleges.length : '…'}</b><span>Colleges</span></div>
        <div><b>{meta?.departments ?? '…'}</b><span>Departments checked</span></div>
        <div><b>{meta?.updated_at ? new Date(meta.updated_at).toLocaleDateString() : 'Not synced'}</b><span>Last update</span></div>
      </section>

      <div className="section-title"><h2>Faculty directory</h2><button onClick={exportCsv} disabled={!shown.length}>{'↓'} Export CSV ({fmt(shown.length)})</button></div>
      <input className="search" placeholder="Search name, research interest, course, lab, student name, department…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search faculty" />
      <div className="filters">
        <select value={college} onChange={(e) => { setCollege(e.target.value); setDept(''); }} aria-label="College">
          <option value="">All colleges</option>{db?.colleges.map((c) => <option key={c}>{c}</option>)}
        </select>
        <select value={dept} onChange={(e) => setDept(e.target.value)} aria-label="Department">
          <option value="">All departments</option>{departments.map((d) => <option key={d}>{d}</option>)}
        </select>
        <button onClick={() => { setCollege(''); setDept(''); setTopic(-1); setQ(''); setOnly({ email: false, scholar: false, students: false, research: false }); }}>Clear all</button>
      </div>
      <div className="chips" role="group" aria-label="Research topics">
        {TOPICS.map((t, i) => (
          <button key={t.label} className={topic === i ? 'chip on' : 'chip'} onClick={() => setTopic(topic === i ? -1 : i)}>{t.label}</button>
        ))}
      </div>
      <div className="chips" role="group" aria-label="Only show profiles with">
        <span className="chip-label">Only with:</span>
        {[['email', 'Email'], ['research', 'Research areas'], ['scholar', 'Google Scholar'], ['students', 'Current students']].map(([k, label]) => (
          <button key={k} className={only[k] ? 'chip on' : 'chip'} onClick={() => toggle(k)}>{label}</button>
        ))}
      </div>
      <p className="count">{db ? `${fmt(shown.length)} researchers found` : 'Loading database…'} {'·'} Fields come from each department’s public pages and may be incomplete</p>

      {db && shown.length > 0 && (
        <section className="grid">
          {shown.slice(0, limit).map((f) => (
            <article key={f.id} className="card">
              <div className="avatar">{f._initials}</div>
              <h3>{f.name}</h3>
              <p>{f.title || 'Faculty'}</p>
              <p>{f.department || 'Department not identified'}</p>
              <small>{f.college || 'College not identified'}</small>
              <div className="tags">{(f.research_areas || []).slice(0, 3).map((t) => <span key={t}>{t}</span>)}</div>
              <div className="badges">
                {f.email && <i title="Email available">{'✉'}</i>}
                {f.google_scholar && <i title="Google Scholar">{'\u{1F393}'}</i>}
                {f.current_students?.length > 0 && <i title="Current students listed">{'\u{1F465}'} {f.current_students.length}</i>}
              </div>
              <button onClick={() => setOpenId(f.id)}>View faculty details {'↗'}</button>
            </article>
          ))}
        </section>
      )}
      {db && shown.length > limit && <div ref={sentinel} className="more"><button onClick={() => setLimit((n) => n + PAGE)}>Show more</button></div>}
      {db && !shown.length && <div className="empty"><h3>No matching faculty found</h3><p>Try fewer filters or a different search.</p></div>}
      {chosen && <FacultyModal f={chosen} onClose={() => setOpenId(null)} />}
    </>
  );
}

function List({ title, items, render }) {
  if (!items?.length) return null;
  return (<><h3>{title}</h3><ul className="plain">{items.map((x, i) => <li key={i}>{render ? render(x) : x}</li>)}</ul></>);
}

function FacultyModal({ f, onClose }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  const link = (href, label) => href && <a href={href} target="_blank" rel="noreferrer">{label} {'↗'}</a>;
  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-label={f.name}>
        <button className="close" onClick={onClose} aria-label="Close">{'✕'}</button>
        <h2>{f.name}</h2>
        <p>{[f.title, f.department, f.college].filter(Boolean).join(' · ')}</p>
        {f.affiliations?.length > 1 && <p className="muted">Also: {f.affiliations.slice(1).map((a) => a.department).join('; ')}</p>}
        {(f.location || f.roles?.length > 0) && <p className="muted">{[...(f.roles || []), f.location].filter(Boolean).join(' · ')}</p>}
        <div className="links">
          {f.email && <a href={`mailto:${f.email}`}>{f.email}</a>}
          {link(f.google_scholar, 'Google Scholar')}{link(f.orcid, 'ORCID')}{link(f.lab_url, f.lab_name || 'Lab website')}
          {link(f.website, 'Website')}{link(f.profile_url, 'UF profile')}{link(f.edis_url, 'Extension publications (EDIS)')}
        </div>
        <List title="Research areas" items={f.research_areas} />
        {f.research_summary && <p>{f.research_summary}</p>}
        <List title="Teaching" items={f.teaching} />
        <List title="Extension" items={f.extension} />
        <List title={`Current students (${f.current_students?.length || 0})`} items={f.current_students}
          render={(s) => `${s.name}${s.program ? ` — ${s.program}` : ''}`} />
        {!f.research_areas?.length && !f.teaching?.length && !f.current_students?.length && (
          <p className="muted">No research, teaching or student details were found on this person’s public UF pages.</p>
        )}
        <p className="muted small">Last checked {fmtDate(f.verified_at)}. Always confirm details on the linked UF page.</p>
      </div>
    </div>
  );
}
