// Headless walk of the betadoc site + demo app (CDP, no dependencies).
//   node scripts/site_walk.mjs <base-url> <admin-pin> <photo.jpg> [shots-dir]
// Checks: every page at 1280 and 390 px in light and dark: 0 console errors, no horizontal scroll; index section
// order; no internal text; theme toggle survives reload; status rows = built count; tour player loads, one chapter button per chapters.vtt cue,
// a chapter seeks; app: back-to-home on sign-in, wrong PIN refused, sign in, 127 tiles, open a photo, live read.
import { spawn } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

const [base, pin, photo, shots = 'walk-shots'] = process.argv.slice(2);
const built = JSON.parse(readFileSync('docs/project_data.json', 'utf8')).features.filter((f) => f.status === 'built').length;
mkdirSync(shots, { recursive: true });
const CHROME = process.env.CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const chrome = spawn(CHROME, ['--headless=new', '--remote-debugging-port=9341', '--autoplay-policy=no-user-gesture-required', `--user-data-dir=${mkdtempSync(join(tmpdir(), 'sw-'))}`, 'about:blank'], { stdio: 'ignore' });
setTimeout(() => { console.log('FAIL watchdog 240s'); chrome.kill(); process.exit(1); }, 240000).unref();
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let t;
for (let i = 0; i < 40 && !t; i++) { await sleep(250); try { t = (await (await fetch('http://127.0.0.1:9341/json')).json()).find((x) => x.type === 'page'); } catch {} }
const ws = new WebSocket(t.webSocketDebuggerUrl); await new Promise((r) => (ws.onopen = r));
let id = 0; const pend = {}; let errors = [];
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pend[d.id]) { pend[d.id](d.result ?? d.error); delete pend[d.id]; }
  if (d.method === 'Runtime.exceptionThrown') errors.push(d.params.exceptionDetails.exception?.description || d.params.exceptionDetails.text);
  if (d.method === 'Runtime.consoleAPICalled' && d.params.type === 'error') errors.push(JSON.stringify(d.params.args).slice(0, 200));
  if (d.method === 'Log.entryAdded' && d.params.entry.level === 'error' && !/401|favicon/.test(d.params.entry.text + d.params.entry.url)) errors.push(d.params.entry.text + ' ' + (d.params.entry.url || '')); };
const cdp = (method, params = {}) => new Promise((r) => { pend[++id] = r; ws.send(JSON.stringify({ id, method, params })); });
const ev = async (e) => (await cdp('Runtime.evaluate', { expression: e, awaitPromise: true, returnByValue: true })).result?.value;
await cdp('Runtime.enable'); await cdp('Log.enable'); await cdp('Page.enable'); await cdp('DOM.enable');
const fails = []; const ok = (cond, msg) => { console.log(`${cond ? 'PASS' : 'FAIL'} ${msg}`); if (!cond) fails.push(msg); };
async function go(url, width, scheme) {
  await cdp('Emulation.setDeviceMetricsOverride', { width, height: width < 500 ? 844 : 900, deviceScaleFactor: 1, mobile: width < 500 });
  await cdp('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: scheme }] });
  errors = []; await cdp('Page.navigate', { url });
  for (let i = 0; i < 40; i++) { await sleep(150); if ((await ev('document.readyState')) === 'complete') break; }
  await sleep(500);
}
async function shot(name) { const r = await cdp('Page.captureScreenshot', { format: 'png' }); writeFileSync(join(shots, name + '.png'), Buffer.from(r.data, 'base64')); }
const noScroll = 'document.documentElement.scrollWidth <= window.innerWidth + 1';

for (const page of ['index.html', 'documentation.html', 'app.html']) for (const width of [1280, 390]) for (const scheme of ['light', 'dark']) {
  await go(`${base}/${page}`, width, scheme);
  ok(errors.length === 0, `${page} ${width}px ${scheme}: console errors ${errors.length} ${errors.slice(0, 2).join(' | ')}`);
  ok(await ev(noScroll), `${page} ${width}px ${scheme}: no horizontal scroll (${await ev('document.documentElement.scrollWidth')} vs ${await ev('innerWidth')})`);
  const txt = await ev('document.body.innerText');
  ok(!/phasedoc|braindoc|\bP\d\.\d/.test(txt), `${page}: no internal tracking text`);
  await shot(`${page.replace('.html', '')}-${width}-${scheme}`);
}
// index spine and status
await go(`${base}/index.html`, 1280, 'light');
const order = await ev('[...document.querySelectorAll("main > section")].map(s => s.id).join(",")');
ok(order === 'hero,problem,product,architecture,status,roadmap,deployment,demo', `index section order: ${order}`);
ok((await ev('document.querySelectorAll("#matrix tbody tr").length')) === built, `status rows = built features (${built})`);
// theme toggle survives reload
await ev('document.querySelector("[data-theme-toggle]").click()');
const th = await ev('document.documentElement.getAttribute("data-theme")');
await go(`${base}/index.html`, 1280, 'light');
ok(th === 'dark' && (await ev('document.documentElement.getAttribute("data-theme")')) === 'dark', `theme toggle flips to dark and survives reload`);
await ev('localStorage.removeItem("cm-theme")');
// tour player
await go(`${base}/index.html`, 1280, 'light');
await ev('new Promise(r => { const v = document.getElementById("tourvid"); if (v.readyState >= 1) r(); else v.addEventListener("loadedmetadata", r); setTimeout(r, 8000); })');
ok((await ev('document.getElementById("tourvid").duration')) > 50, `tour video metadata loads (${(await ev('document.getElementById("tourvid").duration'))?.toFixed?.(1)} s)`);
const cues = ((await (await fetch(base + '/media/explainer.chapters.vtt')).text()).match(/-->/g) || []).length;
ok(cues > 0 && (await ev('document.querySelectorAll("#chapters button").length')) === cues, `tour has ${cues} chapters (one per VTT cue)`);
await ev('document.getElementById("tourvid").muted = true; document.querySelectorAll("#chapters button")[3].click()');
await sleep(800);
ok((await ev('document.getElementById("tourvid").currentTime')) >= 23.9, `chapter click seeks (t=${(await ev('document.getElementById("tourvid").currentTime'))?.toFixed?.(1)})`);
// app
await go(`${base}/app.html`, 1280, 'light');
ok(await ev('!document.getElementById("signin").hidden && /Back to home/.test(document.getElementById("signin").innerText)'), 'sign-in screen with back-to-home');
await ev('document.getElementById("pin").value = "000000"; document.getElementById("loginform").requestSubmit()'); await sleep(600);
ok(/wrong PIN/i.test(await ev('document.getElementById("loginmsg").textContent')), 'wrong PIN refused');
await ev(`document.getElementById("pin").value = ${JSON.stringify(pin)}; document.getElementById("loginform").requestSubmit()`);
let tiles = 0; for (let i = 0; i < 40 && tiles < 127; i++) { await sleep(250); tiles = await ev('document.querySelectorAll("#tiles .tile").length'); }
ok(tiles === 127, `gallery shows ${tiles} photos`);
ok(await ev('/Home/.test(document.querySelector("header.top").innerText)'), 'app header has Home');
await sleep(1500); await shot('app-gallery');
await ev('document.querySelectorAll("#tiles .tile")[44].click()'); await sleep(1200);
ok(/v0 \(current detector\)/.test(await ev('document.getElementById("detail").innerText')), 'photo detail lists every method');
await shot('app-detail');
await ev('document.getElementById("t-read").click()');
const doc = await cdp('DOM.getDocument'); const { nodeId } = await cdp('DOM.querySelector', { nodeId: doc.root.nodeId, selector: '#file' });
await cdp('DOM.setFileInputFiles', { nodeId, files: [resolve(photo)] });
await ev('document.getElementById("file").dispatchEvent(new Event("change"))');
let msg = ''; for (let i = 0; i < 120 && !/Accepted|review|No gauge|Could not|too large/.test(msg); i++) { await sleep(500); msg = await ev('document.getElementById("readmsg").textContent'); }
ok(/Accepted|review/.test(msg), `live read: ${msg}`);
await sleep(800); await shot('app-read');
ok(errors.length === 0, `app flow console errors ${errors.length} ${errors.join(' | ').slice(0, 300)}`);
chrome.kill();
console.log(fails.length ? `FAIL ${fails.length} checks` : 'ALL PASS');
process.exit(fails.length ? 1 : 0);
