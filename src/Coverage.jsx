import React, { useEffect, useState } from 'react';
import { fmt, fmtDate, loadCoverage } from './data.js';

const STATUS = {
  ok: ['ok', 'Faculty list found'],
  partial: ['warn', 'Partly found'],
  no_people_page: ['bad', 'No faculty list recognised'],
  no_site: ['bad', 'No department website found'],
  unreachable: ['bad', 'Website did not load'],
  error: ['bad', 'Error'],
  skipped_time: ['warn', 'Skipped (time limit)'],
};

export default function Coverage({ meta }) {
  const [cov, setCov] = useState(null);
  const [err, setErr] = useState('');
  useEffect(() => { loadCoverage((meta?.revision || meta?.updated_at)).then(setCov).catch(() => setErr('Coverage report is not available yet.')); }, [meta?.revision || meta?.updated_at]);
  if (err) return <div className="banner">{err}</div>;
  if (!cov) return <p className="count">Loading coverage report{'…'}</p>;
  const t = cov.totals;
  return (
    <>
      <section className="update lead">
        <h2>Data coverage</h2>
        <p>Every department is listed, including the ones where the crawler could not find a faculty list. Those fall back to the graduate catalog roster (name, rank, department) until a parser is added.</p>
        <div className="kpis">
          <div><b>{fmt(t.faculty)}</b><span>faculty</span></div><div><b>{fmt(t.with_email)}</b><span>with email</span></div>
          <div><b>{fmt(t.with_research)}</b><span>with research areas</span></div><div><b>{fmt(t.with_scholar)}</b><span>with Google Scholar</span></div>
          <div><b>{fmt(t.with_teaching)}</b><span>with teaching</span></div><div><b>{fmt(t.students)}</b><span>students</span></div>
        </div>
        <p className="muted small">Checked {fmtDate(cov.updated_at)} {'·'} {fmt(cov.pages_requested)} pages read {'·'} {Math.round(cov.elapsed_seconds / 60)} min</p>
      </section>
      {cov.colleges.map((c) => (
        <details key={c.name} className="update college" open={false}>
          <summary><strong>{c.name}</strong> <span className="muted">{'—'} {c.departments} departments {'·'} {fmt(c.faculty)} faculty {'·'} {c.departments_ok} with faculty list</span></summary>
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>Department</th><th>Status</th><th>Faculty</th><th>Email</th><th>Research</th><th>Scholar</th><th>Students</th></tr></thead>
              <tbody>
                {cov.departments.filter((d) => d.college === c.name).map((d) => {
                  const [cls, label] = STATUS[d.status] || ['warn', d.status || 'unknown'];
                  return (
                    <tr key={d.department}>
                      <td>{d.site ? <a href={d.faculty_page || d.site} target="_blank" rel="noreferrer">{d.department}</a> : d.department}</td>
                      <td><span className={`pill ${cls}`}>{label}</span></td>
                      <td>{fmt(d.faculty_in_database)}</td><td>{fmt(d.with_email)}</td><td>{fmt(d.with_research)}</td><td>{fmt(d.with_scholar)}</td><td>{fmt(d.students_found)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </details>
      ))}
    </>
  );
}
