#!/usr/bin/env node
// Headless driver: serves the page, steps renderFrame(i), pipes JPEG frames to
// ffmpeg, then synthesises foley (pencil / marker / rewind / paper pops).
//   node render.js --city paris [--short] [--draw 30 --color 30] [--out ../output/paris_3d.mp4]
const http = require('http'), fs = require('fs'), path = require('path'), { spawn, execFileSync } = require('child_process');
const { chromium } = require('playwright');

const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, arr) => {
  if (v.startsWith('--')) a.push([v.slice(2), arr[i + 1] && !arr[i + 1].startsWith('--') ? arr[i + 1] : true]); return a; }, []));
const city = args.city || 'paris';
const short = !args.wide;          // 9:16 by default, --wide for 16:9
const W = +(args.w || (short ? 1080 : 1920)), H = +(args.h || (short ? 1920 : 1080));
const ROOT = path.resolve(__dirname, '..');
const out = path.resolve(args.out || path.join(ROOT, 'output', `${city}_3d${short ? '_short' : ''}.mp4`));
fs.mkdirSync(path.dirname(out), { recursive: true });
const limit = args.frames ? +args.frames : Infinity;      // debug: render only N frames
const every = args.every ? +args.every : 1;               // debug: render every Nth frame

const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.ttf': 'font/ttf', '.json': 'application/json' };
const server = http.createServer((req, res) => {
  const p = path.join(ROOT, decodeURIComponent(req.url.split('?')[0]));
  if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(p)] || 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
});

(async () => {
  await new Promise(r => server.listen(0, r));
  const port = server.address().port;
  const q = new URLSearchParams({ city, w: W, h: H, fps: args.fps || 30 });
  for (const k of ['draw', 'color', 'pop', 'orbit', 'hook', 'rewind', 'speed']) if (args[k]) q.set(k, args[k]);
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  page.on('console', m => { if (m.type() === 'error') console.error('[page]', m.text()); });
  page.on('pageerror', e => console.error('[page error]', e.message));
  const t0 = Date.now();
  await page.goto(`http://localhost:${port}/city3d/index.html?${q}`);
  await page.waitForFunction(() => window.ready === true, null, { timeout: 300000 });
  await page.evaluate(() => document.fonts.ready);
  const info = await page.evaluate(() => window.info);
  console.log(`scene ready in ${((Date.now() - t0) / 1000).toFixed(1)}s:`, JSON.stringify({ ...info, pops: info.pops.length }));
  const fps = info.fps / every;
  const tmpVideo = out.replace(/\.mp4$/, '.video.mp4');
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-c:v', 'mjpeg', '-r', String(fps), '-i', '-',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', tmpVideo], { stdio: ['pipe', 'inherit', 'inherit'] });
  const acts = [];
  const N = Math.min(info.total, limit);
  for (let i = 0; i < N; i += every) {
    const a = await page.evaluate(i => window.renderFrame(i), i);
    for (let k = 0; k < every; k++) acts.push(a);
    const buf = await page.screenshot({ type: 'jpeg', quality: 92 });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
    if (i % 150 === 0) process.stdout.write(`\r  frame ${i}/${N}  ${((Date.now() - t0) / 1000).toFixed(0)}s   `);
  }
  ff.stdin.end();
  await new Promise(r => ff.on('close', r));
  await browser.close(); server.close();
  console.log('\n  frames done, making audio');
  const actsFile = out.replace(/\.mp4$/, '.acts.json');
  fs.writeFileSync(actsFile, JSON.stringify({ acts, fps: info.fps, pops: info.pops, hook: info.hook / info.fps, rewind: info.rewind / info.fps }));
  const wav = out.replace(/\.mp4$/, '.wav');
  execFileSync('python3', ['-c', `
import json, sys
sys.path.insert(0, ${JSON.stringify(ROOT)})
from citydraw.audio import make_soundtrack
d = json.load(open(${JSON.stringify(actsFile)}))
make_soundtrack(${JSON.stringify(wav)}, d['acts'], d['fps'], rewind_start=d['hook'], rewind_len=d['rewind'], pops=d['pops'])
`], { stdio: 'inherit' });
  const mux = ['-y', '-loglevel', 'error', '-i', tmpVideo, '-i', wav];
  if (args.music) mux.push('-stream_loop', '-1', '-i', args.music, '-filter_complex',
    `[2:a]volume=${args['music-volume'] || 0.25}[m];[1:a][m]amix=inputs=2:duration=first:normalize=0[a]`, '-map', '0:v', '-map', '[a]');
  else mux.push('-map', '0:v', '-map', '1:a');
  mux.push('-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', out);
  execFileSync('ffmpeg', mux, { stdio: 'inherit' });
  for (const f of [tmpVideo, wav, actsFile]) fs.rmSync(f, { force: true });
  console.log(`done -> ${out}  (${((Date.now() - t0) / 1000).toFixed(0)}s)`);
})().catch(e => { console.error(e); process.exit(1); });
