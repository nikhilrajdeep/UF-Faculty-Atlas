// Data loading and indexing. The database is static JSON committed to the repository (docs/data).
// Everything heavy (search index, college/department maps) is computed once, not on every keystroke.

export const TOPICS = [
  { label: 'Remote sensing', re: /remote sensing|satellite|lidar|hyperspectral|earth observation|radiometr|sar\b/ },
  { label: 'Machine learning / AI', re: /machine learning|artificial intelligence|deep learning|neural network|\bai\b|data[- ]driven/ },
  { label: 'GIS & geospatial', re: /\bgis\b|geospatial|geographic information|spatial analysis|mapping/ },
  { label: 'Precision agriculture', re: /precision (agri|farming)|crop model|smart farming|sensors? for agri/ },
  { label: 'Soil science', re: /\bsoils?\b|pedolog|soil physics|soil moisture|vadose/ },
  { label: 'Hydrology & water', re: /hydrolog|watershed|groundwater|water (quality|resources|management)|irrigation|wetland/ },
  { label: 'Climate', re: /climate|meteorolog|atmospher|carbon cycl|global change/ },
  { label: 'Ecology & environment', re: /ecolog|conservation|biodiversity|environmental/ },
  { label: 'Data science', re: /data science|statistic|bioinformatic|computational|modeling|modelling/ },
];

const fetchJson = async (path, version) => {
  const r = await fetch(`${path}${version ? `?v=${encodeURIComponent(version)}` : ''}`, { cache: 'default' });
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
};

export const loadMeta = () => fetch(`data/meta.json?t=${Date.now()}`, { cache: 'no-store' }).then((r) => (r.ok ? r.json() : null)).catch(() => null);
export const loadCoverage = (v) => fetchJson('data/coverage.json', v);

const initials = (name) => name.split(/\s+/).filter(Boolean).slice(0, 2).map((x) => x[0]).join('').toUpperCase();

export async function loadFaculty(version) {
  const j = await fetchJson('data/faculty.json', version);
  const items = j.faculty || [];
  const colleges = new Map(); // college -> Set(department)
  for (const f of items) {
    const affs = f.affiliations?.length ? f.affiliations : [{ college: f.college, department: f.department }];
    f._colleges = [...new Set(affs.map((a) => a.college).filter(Boolean))];
    f._depts = [...new Set(affs.map((a) => a.department).filter(Boolean))];
    f._q = [f.name, f.title, f.department, f.college, f.lab_name, ...(f.research_areas || []), ...(f.teaching || []),
      ...(f.extension || []), f.research_summary, ...(f.roles || []), ...(f.current_students || []).map((s) => s.name), f.email]
      .filter(Boolean).join(' • ').toLowerCase();
    f._topics = TOPICS.reduce((m, t, i) => (t.re.test(f._q) ? m | (1 << i) : m), 0);
    f._initials = initials(f.name);
    f._rich = (f.email ? 1 : 0) + (f.research_areas?.length ? 1 : 0) + (f.google_scholar ? 1 : 0) + (f.teaching?.length ? 1 : 0);
    for (const c of f._colleges) {
      if (!colleges.has(c)) colleges.set(c, new Set());
      f._depts.forEach((d) => colleges.get(c).add(d));
    }
  }
  const collegeList = [...colleges.keys()].sort();
  return { items, meta: j.metadata || {}, colleges: collegeList, deptsOf: (c) => [...(c ? colleges.get(c) || [] : new Set([...colleges.values()].flatMap((s) => [...s])))].sort() };
}

export function matchesQuery(blob, query) {
  if (!query) return true;
  for (const part of query.toLowerCase().split(/\s+/)) if (part && !blob.includes(part)) return false;
  return true;
}

export function toCsv(rows, columns) {
  const esc = (v) => `"${String(v ?? '').replaceAll('"', '""')}"`;
  const lines = [columns.map((c) => esc(c.label)).join(',')];
  for (const r of rows) lines.push(columns.map((c) => esc(c.get(r))).join(','));
  return lines.join('\r\n');
}

export function download(filename, text) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], { type: 'text/csv;charset=utf-8' }));
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1500);
}

export const fmt = (n) => (n ?? 0).toLocaleString();
export const fmtDate = (iso) => (iso ? new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : 'Never');
export function fmtEta(seconds) {
  if (seconds == null) return '';
  if (seconds < 90) return 'about a minute left';
  const m = Math.round(seconds / 60);
  return m < 90 ? `about ${m} min left` : `about ${(m / 60).toFixed(1)} hours left`;
}
