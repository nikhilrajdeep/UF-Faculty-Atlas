// Copies the built app (dist/) into docs/ for GitHub Pages "Deploy from a branch: main /docs",
// leaving docs/data (the database) untouched.
import fs from 'node:fs';
import path from 'node:path';

const dist = path.resolve('dist');
const docs = path.resolve('docs');
fs.mkdirSync(docs, { recursive: true });
fs.rmSync(path.join(docs, 'assets'), { recursive: true, force: true });
for (const entry of fs.readdirSync(dist)) {
  fs.cpSync(path.join(dist, entry), path.join(docs, entry), { recursive: true });
}
fs.copyFileSync(path.join(docs, 'index.html'), path.join(docs, '404.html'));
fs.writeFileSync(path.join(docs, '.nojekyll'), '');
console.log('Published site files to docs/ (data left in place).');
