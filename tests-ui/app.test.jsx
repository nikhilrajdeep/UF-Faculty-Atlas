// @vitest-environment jsdom
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import fs from 'node:fs';
import path from 'node:path';
import App from '../src/App.jsx';

const fx = (n) => JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures', `${n}.json`), 'utf8'));
let relay;

beforeEach(() => {
  cleanup();
  location.hash = '';
  relay = { run: null, progress: null, can_refresh: true, message: null };
  globalThis.IntersectionObserver = class { observe() {} disconnect() {} };
  window.scrollTo = () => {};
  globalThis.fetch = vi.fn(async (url, opts = {}) => {
    const u = String(url);
    const ok = (body, status = 200) => ({ ok: status < 400, status, json: async () => body, text: async () => JSON.stringify(body) });
    if (u.startsWith('config.json')) return ok({ repository: 'o/r', refreshApi: 'https://relay.test' });
    if (u.startsWith('data/meta.json')) return ok(fx('meta'));
    if (u.startsWith('data/faculty.json')) return ok(fx('faculty'));
    if (u.startsWith('data/students.json')) return ok(fx('students'));
    if (u.startsWith('data/coverage.json')) return ok(fx('coverage'));
    if (u === 'https://relay.test/status') return ok(relay);
    if (u === 'https://relay.test/refresh' && opts.method === 'POST') { relay.run = { status: 'in_progress' }; relay.progress = { state: 'running', stage: 'profiles', percent: 42.4, eta_seconds: 600, message: 'Reading 4,000 faculty profile pages', counts: { units_total: 110, units_done: 110, profiles_total: 4000, profiles_done: 1700, faculty: 5200, students: 900 } }; return ok({ started: true }, 202); }
    return ok({}, 404);
  });
});

describe('UF Faculty Atlas', () => {
  it('lists faculty, searches, filters and opens details', async () => {
    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => expect(screen.getAllByText(/View faculty details/).length).toBeGreaterThan(5));
    const total = fx('faculty').faculty.length;
    expect(screen.getByText(new RegExp(`${total} researchers found`))).toBeTruthy();

    await user.type(screen.getByLabelText('Search faculty'), 'Derek Bambauer');
    await waitFor(() => expect(screen.getByText(/1 researchers found/)).toBeTruthy());
    await user.click(screen.getByText(/View faculty details/));
    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByText('Derek Bambauer')).toBeTruthy();
    expect(within(dialog).getByText('bambauer@law.ufl.edu')).toBeTruthy();
    expect(within(dialog).getByText(/Artificial Intelligence/)).toBeTruthy();
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('college filter narrows departments', async () => {
    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => screen.getAllByText(/View faculty details/));
    const [collegeSel, deptSel] = screen.getAllByRole('combobox');
    const colleges = [...collegeSel.options].map((o) => o.value).filter(Boolean);
    expect(colleges.length).toBeGreaterThan(1);
    const before = deptSel.options.length;
    await user.selectOptions(collegeSel, colleges[0]);
    expect(deptSel.options.length).toBeLessThanOrEqual(before);
  });

  it('students tab shows advisors and coverage tab lists departments', async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole('button', { name: 'Graduate students' }));
    await waitFor(() => expect(screen.getAllByRole('row').length).toBeGreaterThan(5));
    expect(screen.getByText(/Student e-mail addresses and home locations are intentionally not collected/)).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Data coverage' }));
    await waitFor(() => expect(screen.getByText(/Every department is listed/)).toBeTruthy());
    expect(screen.getAllByText(/departments/).length).toBeGreaterThan(0);
  });

  it('updates tab: refresh button starts a run and shows a real progress bar', async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole('button', { name: /Database updates/ }));
    const btn = await screen.findByRole('button', { name: 'Refresh database now' });
    await waitFor(() => expect(btn.disabled).toBe(false));
    await user.click(btn);
    const bar = await screen.findByRole('progressbar');
    await waitFor(() => expect(bar.getAttribute('aria-valuenow')).toBe('42'));
    expect(screen.getByText(/about 10 min left/)).toBeTruthy();
    expect(screen.getByText(/Profiles 1,700\/4,000/)).toBeTruthy();
    expect(screen.getByRole('button', { name: /Refresh in progress/ }).disabled).toBe(true);
    const post = fetch.mock.calls.filter(([u, o]) => u === 'https://relay.test/refresh' && o?.method === 'POST');
    expect(post.length).toBe(1);
  });

  it('without a relay it explains setup but still renders', async () => {
    const orig = globalThis.fetch;
    globalThis.fetch = vi.fn(async (u, o) => (String(u).startsWith('config.json') ? { ok: true, json: async () => ({ repository: 'o/r' }) } : orig(u, o)));
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole('button', { name: /Database updates/ }));
    expect(await screen.findByText(/One-time setup needed/)).toBeTruthy();
  });
});
