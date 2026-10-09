import React, { useDeferredValue, useEffect, useMemo, useState } from 'react';
import { download, fmt, loadStudents, matchesQuery, toCsv } from './data.js';

const PAGE = 100;

export default function Students({ db, meta, openFaculty }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState('');
  const [q, setQ] = useState('');
  const [college, setCollege] = useState('');
  const [dept, setDept] = useState('');
  const [program, setProgram] = useState('');
  const [limit, setLimit] = useState(PAGE);
  const dq = useDeferredValue(q);

  useEffect(() => { loadStudents(meta?.updated_at).then(setData).catch(() => setErr('Student data could not be loaded.')); }, [meta?.updated_at]);

  const colleges = useMemo(() => [...new Set((data?.items || []).map((s) => s.college))].filter(Boolean).sort(), [data]);
  const depts = useMemo(() => [...new Set((data?.items || []).filter((s) => !college || s.college === college).map((s) => s.department))].sort(), [data, college]);
  const shown = useMemo(() => (data?.items || []).filter((s) =>
    (!college || s.college === college) && (!dept || s.department === dept) && (!program || s.program === program) && matchesQuery(s._q, dq)), [data, college, dept, program, dq]);
  useEffect(() => setLimit(PAGE), [college, dept, program, dq]);

  const facultyById = useMemo(() => new Map((db?.items || []).map((f) => [f.id, f])), [db]);
  const exportCsv = () => download('uf-graduate-students.csv', toCsv(shown, [
    { label: 'Student', get: (s) => s.name }, { label: 'Program', get: (s) => s.program }, { label: 'Department', get: (s) => s.department },
    { label: 'College', get: (s) => s.college }, { label: 'Advisor(s)', get: (s) => (s.advisor_names || []).join('; ') },
  ]));

  return (
    <>
      <section className="update lead">
        <h2>Graduate students and advisors</h2>
        <p>Student lists published on department websites, matched to advisors where the advisor name is unambiguous. Student e-mail addresses and home locations are intentionally not collected.</p>
      </section>
      <div className="section-title"><h2>{data ? fmt(shown.length) : '…'} students</h2><button onClick={exportCsv} disabled={!shown.length}>{'↓'} Export CSV</button></div>
      <input className="search" placeholder="Search student, advisor, department…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search students" />
      <div className="filters">
        <select value={college} onChange={(e) => { setCollege(e.target.value); setDept(''); }}><option value="">All colleges</option>{colleges.map((c) => <option key={c}>{c}</option>)}</select>
        <select value={dept} onChange={(e) => setDept(e.target.value)}><option value="">All departments</option>{depts.map((d) => <option key={d}>{d}</option>)}</select>
        <select value={program} onChange={(e) => setProgram(e.target.value)}><option value="">All programs</option><option>PhD</option><option>MS</option><option>Postdoc</option></select>
      </div>
      {err && <div className="banner">{err}</div>}
      {data && !data.items.length && <div className="empty"><h3>No student lists yet</h3><p>Run a refresh from Database updates to collect them.</p></div>}
      {shown.length > 0 && (
        <div className="table-wrap">
          <table className="data">
            <thead><tr><th>Student</th><th>Program</th><th>Advisor(s)</th><th>Department</th></tr></thead>
            <tbody>
              {shown.slice(0, limit).map((s) => (
                <tr key={s.id}>
                  <td>{s.name}</td><td>{s.program || '—'}</td>
                  <td>{(s.advisor_names || []).length ? s.advisor_names.map((n, i) => {
                    const id = s.advisor_ids?.[i];
                    return <span key={n + i}>{i > 0 && ', '}{id && facultyById.has(id) ? <a href={`#faculty`} onClick={(e) => { e.preventDefault(); openFaculty(id); }}>{facultyById.get(id).name}</a> : n}</span>;
                  }) : '—'}</td>
                  <td>{s.department}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {shown.length > limit && <div className="more"><button onClick={() => setLimit((n) => n + PAGE * 3)}>Show more</button></div>}
    </>
  );
}
