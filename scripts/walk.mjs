// Headless walk of the review page (P6.1.1): upload one visit folder, wait for the readings table, save a
// correction, require 0 console errors.   node scripts/walk.mjs <port> <visit folder>
import { spawn } from 'node:child_process';
import { mkdtempSync, readdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

const [port, folder] = process.argv.slice(2);
const files = readdirSync(folder).filter((f) => /\.jpe?g$/i.test(f)).map((f) => resolve(folder, f));
const CHROME = process.env.CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const chrome = spawn(CHROME, ['--headless=new', '--remote-debugging-port=9339', `--user-data-dir=${mkdtempSync(join(tmpdir(), 'gw-'))}`, 'about:blank'], { stdio: 'ignore' });
setTimeout(() => { console.log('FAIL watchdog: exceeded 120s'); chrome.kill(); process.exit(1); }, 120000).unref();
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let t;
for (let i = 0; i < 40 && !t; i++) { await sleep(250); try { t = (await (await fetch('http://127.0.0.1:9339/json')).json()).find((x) => x.type === 'page'); } catch {} }
const ws = new WebSocket(t.webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0; const pending = {}; const errors = [];
ws.onmessage = (m) => {
  const d = JSON.parse(m.data);
  if (d.id && pending[d.id]) { pending[d.id](d.result); delete pending[d.id]; }
  if (d.method === 'Runtime.consoleAPICalled' && d.params.type === 'error') errors.push(JSON.stringify(d.params.args));
  if (d.method === 'Runtime.exceptionThrown') errors.push(d.params.exceptionDetails.text);
  if (d.method === 'Log.entryAdded' && d.params.entry.level === 'error') errors.push(d.params.entry.text);
};
const cdp = (method, params = {}) => new Promise((r) => { pending[++id] = r; ws.send(JSON.stringify({ id, method, params })); });
const ev = async (expr) => (await cdp('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true })).result.value;
await cdp('Runtime.enable'); await cdp('Log.enable'); await cdp('DOM.enable'); await cdp('Page.enable');
await cdp('Page.navigate', { url: `http://127.0.0.1:${port}/` });
await sleep(1500);
// headless CDP cannot fill a folder picker; the walk uses the same input's multi-photo path
await ev(`document.querySelector('#files').removeAttribute('webkitdirectory')`);
await ev(`document.querySelector('#files').addEventListener('change', () => { window.__fired = true; })`);
const doc = await cdp('DOM.getDocument');
const { nodeId } = await cdp('DOM.querySelector', { nodeId: doc.root.nodeId, selector: '#files' });
await cdp('DOM.setFileInputFiles', { nodeId, files });
const picked = await ev(`document.querySelector('#files').files.length`);
if (picked && !(await ev('window.__fired'))) await ev(`document.querySelector('#files').dispatchEvent(new Event('change'))`);
console.log('files picked:', picked);
let rows = 0;
for (let i = 0; i < 200 && !rows; i++) { await sleep(500); rows = await ev(`document.querySelectorAll('#rows tr').length && /photos read/.test(document.querySelector('#status').textContent) ? document.querySelectorAll('#rows tr').length : 0`); }
const table = await ev(`[...document.querySelectorAll('#rows tr')].map(r => r.textContent.trim()).join(' | ')`);
await ev(`(() => { const tr = document.querySelector('#rows tr'); tr.querySelector('input').value = '12'; tr.querySelector('button').click(); })()`);
let saved = '';
for (let i = 0; i < 20 && !/saved/.test(saved); i++) { await sleep(250); saved = await ev(`document.querySelector('#status').textContent`); }
chrome.kill();
const ok = rows > 0 && /saved/.test(saved) && errors.length === 0;
console.log(`${ok ? 'PASS' : 'FAIL'} rows=${rows} status="${saved}" console_errors=${errors.length}\n  table: ${table}`);
if (errors.length) console.log(errors.join('\n'));
process.exit(ok ? 0 : 1);
