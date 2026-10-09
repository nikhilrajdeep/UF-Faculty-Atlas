import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import fs from 'node:fs';
import path from 'node:path';

// The database lives in docs/data (committed by the refresh workflow). In dev, serve it at /data/.
const serveData = {
  name: 'serve-docs-data',
  configureServer(server) {
    server.middlewares.use('/data', (req, res, next) => {
      const file = path.join(process.cwd(), 'docs', 'data', decodeURIComponent((req.url || '').split('?')[0]));
      if (file.startsWith(path.join(process.cwd(), 'docs', 'data')) && fs.existsSync(file) && fs.statSync(file).isFile()) {
        res.setHeader('Content-Type', 'application/json');
        fs.createReadStream(file).pipe(res);
      } else next();
    });
  },
};

// Relative base so the site works from any GitHub Pages path (https://user.github.io/repo/).
export default defineConfig({ plugins: [react(), serveData], base: './' });
