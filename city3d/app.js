// 3D pop-up city: drawn flat on paper by a 3D pencil, coloured by a marker,
// then every piece folds up into a 3D model and the camera flies around it.
// The whole video is a pure function of the frame number (renderFrame(i)),
// so the headless driver can capture it deterministically.
import * as THREE from 'three';
import { LineSegments2 } from 'three/addons/lines/LineSegments2.js';
import { LineSegmentsGeometry } from 'three/addons/lines/LineSegmentsGeometry.js';
import { LineMaterial } from 'three/addons/lines/LineMaterial.js';
import { CITIES, setLayout, LAYOUT } from './cities.js';

const Q = new URLSearchParams(location.search);
const W = +Q.get('w') || 1920, H = +Q.get('h') || 1080;
const FPS = +Q.get('fps') || 30;
const T = {
  hook: +(Q.get('hook') ?? 3), rewind: +(Q.get('rewind') ?? 1.8), blank: 0.5,
  draw: +(Q.get('draw') ?? 30), color: +(Q.get('color') ?? 30),
  pop: +(Q.get('pop') ?? 5), orbit: +(Q.get('orbit') ?? 7),
};
const CITY = CITIES[Q.get('city') || 'paris'];
const SHORT = H > W;
setLayout(SHORT);
const INK = 0x26242c;
const PAPER = new THREE.Color('#f7f4ec');
const SQUASH = 0.015, LAYER = 0.012;

// ---------------------------------------------------------------- renderer
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(W, H);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.outputColorSpace = THREE.SRGBColorSpace;
document.body.appendChild(renderer.domElement);
const scene = new THREE.Scene();
scene.background = new THREE.Color('#2b2620');
const camera = new THREE.PerspectiveCamera(36, W / H, 0.1, 200);

scene.add(new THREE.HemisphereLight(0xffffff, 0xb9ad98, 1.25));
const sun = new THREE.DirectionalLight(0xffffff, 1.9);
sun.position.set(-5, 13, 14);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
Object.assign(sun.shadow.camera, { left: -13, right: 13, top: 13, bottom: -13, near: 1, far: 50 });
sun.shadow.bias = -0.0008;
sun.shadow.radius = 4;
scene.add(sun);

// table + paper
function noiseTex(w, h, base, amp, streak = 1) {
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  const g = c.getContext('2d'); g.fillStyle = base; g.fillRect(0, 0, w, h);
  let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  for (let i = 0; i < w * h / 6; i++) {
    const v = (rnd() - .5) * amp; g.fillStyle = v > 0 ? `rgba(255,255,255,${v})` : `rgba(0,0,0,${-v})`;
    g.fillRect(rnd() * w, rnd() * h, 1 + rnd() * 2 * streak, 1);
  }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping; return t;
}
const table = new THREE.Mesh(new THREE.PlaneGeometry(80, 60),
  new THREE.MeshLambertMaterial({ map: noiseTex(512, 512, '#8a6748', .18, 30) }));
table.material.map.repeat.set(6, 6);
table.rotation.x = -Math.PI / 2; table.position.y = -0.03; table.receiveShadow = true;
scene.add(table);
const PW = LAYOUT.X1 - LAYOUT.X0 + 1.2, PH = LAYOUT.ZBOT - LAYOUT.ZTOP + 0.8, PZ = (LAYOUT.ZBOT + LAYOUT.ZTOP) / 2;
const paper = new THREE.Mesh(new THREE.BoxGeometry(PW, 0.03, PH),
  new THREE.MeshLambertMaterial({ color: PAPER, map: noiseTex(1024, 600, '#ffffff', .05) }));
paper.position.set(0, -0.015, PZ); paper.receiveShadow = true;
scene.add(paper);

// ---------------------------------------------------------------- reveal material
const revealMats = [];
function revealMaterial(color) {
  const m = new THREE.MeshLambertMaterial({ color, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 });
  m.userData.u = { uReveal: { value: 0 }, uBox: { value: new THREE.Vector4(0, 0, 1, 1) },
                   uRows: { value: 4 }, uPaper: { value: PAPER.clone() } };
  m.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, m.userData.u);
    sh.vertexShader = 'varying vec3 vW;\n' + sh.vertexShader.replace('#include <project_vertex>',
      '#include <project_vertex>\n vW = (modelMatrix * vec4(transformed, 1.0)).xyz;');
    sh.fragmentShader = `varying vec3 vW; uniform float uReveal; uniform vec4 uBox; uniform float uRows; uniform vec3 uPaper;
      float revealAt() {
        if (uReveal >= 0.999) return 1.0; if (uReveal <= 0.0) return 0.0;
        vec2 q = (vW.xz - uBox.xy) / max(uBox.zw - uBox.xy, vec2(1e-4));
        float rf = clamp(q.y, 0.0, 0.9999) * uRows;
        rf += 0.12 * sin(q.x * 37.0 + floor(rf) * 1.7);
        float row = floor(rf);
        float xf = mod(row, 2.0) < 0.5 ? q.x : 1.0 - q.x;
        float s = (row + clamp(xf, 0.0, 1.0)) / uRows;
        return 1.0 - smoothstep(uReveal - 0.002, uReveal + 0.002, s);
      }\n` + sh.fragmentShader.replace('vec4 diffuseColor = vec4( diffuse, opacity );',
      'float rv = revealAt();\n vec4 diffuseColor = vec4( mix(uPaper, diffuse, rv), opacity );')
      // unrevealed parts are lit like the flat paper (no facet shading)
      .replace('#include <normal_fragment_maps>',
               '#include <normal_fragment_maps>\n normal = normalize(mix((viewMatrix * vec4(0.0, 1.0, 0.0, 0.0)).xyz, normal, rv));');
  };
  m.customProgramCacheKey = () => 'reveal';
  revealMats.push(m);
  return m;
}

// ---------------------------------------------------------------- pieces
// A piece is a pop-up card: hinge on the paper at (x, z); its body stands on
// y=0 with the front face at local z=0.  fold=1 lies it flat (facade up).
const pieces = [];
export function makePiece(x, z, opts = {}) {
  const hinge = new THREE.Group(), body = new THREE.Group();
  hinge.position.set(x, 0, z); hinge.add(body); scene.add(hinge);
  const p = { hinge, body, meshes: [], x, z, order: opts.order ?? 50, popOrder: opts.popOrder ?? z,
              flatOnly: !!opts.flatOnly, fold: 1, layer: 0 };
  pieces.push(p);
  return p;
}
export function addMesh(p, geom, color, pos = [0, 0, 0], o = {}) {
  const mat = revealMaterial(new THREE.Color(color));
  const m = new THREE.Mesh(geom, mat);
  m.position.set(...pos);
  if (o.rot) m.rotation.set(...o.rot);
  if (o.scale) m.scale.set(...o.scale);
  m.castShadow = m.receiveShadow = true;
  m.userData = { color: new THREE.Color(color), extra: o.extra || [], job: o.job ?? true,
                 edges: o.edges ?? true, order: o.order ?? p.order, threshold: o.threshold ?? 28 };
  p.body.add(m); p.meshes.push(m);
  return m;
}

function setFold(p, f) {
  p.fold = f;
  if (p.flatOnly) { p.hinge.rotation.x = 0; p.hinge.position.y = p.layer; return; }
  const a = -Math.PI / 2 * f;
  p.hinge.rotation.x = a;
  p.body.scale.z = THREE.MathUtils.lerp(1, SQUASH, Math.min(1, f * 1.15));
  p.hinge.position.y = p.layer * f + 0.001;
  const cast = f < 0.9;           // flat cards must not shade each other (blank paper must look blank)
  if (p.cast !== cast) { p.cast = cast; for (const m of p.meshes) m.castShadow = cast; }
}

// ---------------------------------------------------------------- fat lines
const lineMats = [];
function lineMat(width, opacity = 1) {
  const m = new LineMaterial({ color: INK, linewidth: width * Math.min(W, H) / 1080, transparent: true, opacity,
                               depthTest: true, depthWrite: false });
  m.resolution.set(W, H); lineMats.push(m); return m;
}

// ---------------------------------------------------------------- tools
function cyl(rt, rb, h, seg, color, y) {
  const m = new THREE.Mesh(new THREE.CylinderGeometry(rt, rb, h, seg), new THREE.MeshLambertMaterial({ color }));
  m.position.y = y; m.castShadow = false; return m;   // tools cast no shadow
}
function makePencil() {
  const g = new THREE.Group(), inner = new THREE.Group();
  inner.add(cyl(0.012, 0.0, 0.07, 8, 0x2a2a2a, 0.035));
  inner.add(cyl(0.065, 0.012, 0.28, 6, 0xeac393, 0.07 + 0.14));
  inner.add(cyl(0.065, 0.065, 2.2, 6, 0xf5b81c, 0.35 + 1.1));
  inner.add(cyl(0.067, 0.067, 0.16, 12, 0xb8b8c0, 2.45 + 0.08));
  inner.add(cyl(0.062, 0.062, 0.22, 12, 0xef8a99, 2.61 + 0.11));
  g.add(inner);
  inner.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), new THREE.Vector3(0.42, 1, 0.55).normalize());
  scene.add(g); return g;
}
function makeMarker() {
  const g = new THREE.Group(), inner = new THREE.Group();
  const tip = cyl(0.03, 0.012, 0.12, 10, 0xff0000, 0.06);
  const cap = cyl(0.115, 0.115, 0.7, 16, 0xff0000, 1.95);
  inner.add(tip, cyl(0.07, 0.04, 0.18, 16, 0xdddddd, 0.21), cyl(0.11, 0.08, 0.2, 16, 0xf2f2f2, 0.4),
            cyl(0.11, 0.11, 1.2, 16, 0xfafafa, 1.1), cap);
  g.add(inner);
  inner.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), new THREE.Vector3(0.45, 1, 0.5).normalize());
  g.userData.colorParts = [tip.material, cap.material];
  scene.add(g); return g;
}
const pencil = makePencil(), marker = makeMarker();
pencil.scale.setScalar(1.45); marker.scale.setScalar(1.35);

// ---------------------------------------------------------------- build the city
CITY.build({ makePiece, addMesh, THREE, short: SHORT });

// layer order (front pieces lie on top), flat state
pieces.sort((a, b) => a.z - b.z);
pieces.forEach((p, i) => { p.layer = p.flatOnly ? 0.004 : 0.02 + i * LAYER; setFold(p, 1); });
scene.updateMatrixWorld(true);
const allMeshes = pieces.flatMap(p => p.meshes);

// ---------------------------------------------------------------- cameras
const camTopPos = SHORT ? new THREE.Vector3(0, 25, PZ + 5.5) : new THREE.Vector3(0, 14.6, 4.6);
const camTopLook = SHORT ? new THREE.Vector3(0, 0, PZ + 0.2) : new THREE.Vector3(0, 0, 0.35);
const orbitTarget = SHORT ? new THREE.Vector3(0, 3.6, 0.6) : new THREE.Vector3(0, 2.5, 0.4);
const OR = SHORT ? 17 : 15, OH = SHORT ? 4.2 : 4.4;
function orbitPos(a, r = OR, h = OH) {
  return new THREE.Vector3(orbitTarget.x + Math.sin(a) * r, h, orbitTarget.z + Math.cos(a) * r);
}
function setCamTop(drift) {
  camera.position.copy(camTopPos).add(new THREE.Vector3(Math.sin(drift) * 0.5, 0, Math.cos(drift * 0.7) * 0.2 - 0.2));
  camera.lookAt(camTopLook);
}

// ---------------------------------------------------------------- strokes (flat drawing)
camera.position.copy(camTopPos); camera.lookAt(camTopLook); camera.updateMatrixWorld();
const ray = new THREE.Raycaster();
const tmpA = new THREE.Vector3(), tmpB = new THREE.Vector3();
function visible(P) {
  const lifted = P.clone(); lifted.y += 0.004;
  const dir = lifted.clone().sub(camera.position); const d = dir.length(); dir.normalize();
  ray.set(camera.position, dir); ray.far = d + 1;
  const hit = ray.intersectObjects(allMeshes, false)[0];
  return !hit || hit.distance >= d - 0.006;
}
function meshSegments(m) {
  const segs = [];
  if (m.userData.edges) {
    const e = new THREE.EdgesGeometry(m.geometry, m.userData.threshold).attributes.position.array;
    for (let i = 0; i < e.length; i += 6) segs.push([[e[i], e[i + 1], e[i + 2]], [e[i + 3], e[i + 4], e[i + 5]]]);
  }
  for (const s of m.userData.extra) segs.push(s);
  return segs;
}
// strokes: {pts:[Vector3...], mesh} in world flat coords, split where hidden
const strokesByMesh = new Map();
for (const m of allMeshes) {
  const out = [];
  const seen = new Set();
  for (const [a, b] of meshSegments(m)) {
    tmpA.set(...a).applyMatrix4(m.matrixWorld); tmpB.set(...b).applyMatrix4(m.matrixWorld);
    const L = Math.hypot(tmpA.x - tmpB.x, tmpA.z - tmpB.z);
    if (L < 0.015) continue;
    const key = [tmpA.x, tmpA.z, tmpB.x, tmpB.z].map(v => Math.round(v * 60)).join(',');
    const key2 = [tmpB.x, tmpB.z, tmpA.x, tmpA.z].map(v => Math.round(v * 60)).join(',');
    if (seen.has(key) || seen.has(key2)) continue;
    seen.add(key);
    const n = Math.max(2, Math.ceil(L / 0.04));
    let run = [];
    for (let k = 0; k <= n; k++) {
      const P = tmpA.clone().lerp(tmpB, k / n);
      if (visible(P)) run.push(P);
      else { if (run.length > 1) out.push(run); run = []; }
    }
    if (run.length > 1) out.push(run);
  }
  strokesByMesh.set(m, out);
}
// global order: by mesh order, nearest neighbour chaining inside each mesh
function chain(list, start) {
  const res = []; let pos = start.clone(); const left = list.slice();
  while (left.length) {
    let bi = 0, bd = 1e9, rev = false;
    left.forEach((s, i) => {
      const d0 = pos.distanceToSquared(s[0]), d1 = pos.distanceToSquared(s[s.length - 1]);
      if (d0 < bd) { bd = d0; bi = i; rev = false; }
      if (d1 < bd) { bd = d1; bi = i; rev = true; }
    });
    let s = left.splice(bi, 1)[0]; if (rev) s = s.slice().reverse();
    res.push(s); pos = s[s.length - 1];
  }
  return res;
}
const orderedMeshes = allMeshes.slice().sort((a, b) => a.userData.order - b.userData.order);
let strokes = [];
{
  let pos = new THREE.Vector3(-8, 0, -5);
  // group meshes with equal order and chain them by proximity
  const groups = new Map();
  for (const m of orderedMeshes) {
    const k = m.userData.order; if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(...strokesByMesh.get(m));
  }
  for (const k of [...groups.keys()].sort((a, b) => a - b)) {
    const c = chain(groups.get(k), pos);
    strokes.push(...c); if (c.length) pos = c[c.length - 1][c[c.length - 1].length - 1];
  }
}
// flatten into segment list with schedule
const segs = [];            // {a, b, len, cum, strokeStart}
for (const s of strokes) for (let i = 0; i < s.length - 1; i++)
  segs.push({ a: s[i], b: s[i + 1], first: i === 0 });
const TRAVEL = 0.25;
let cost = 0, prev = new THREE.Vector3(-8, 0, -5);
for (const g of segs) {
  if (g.first) cost += prev.distanceTo(g.a) * TRAVEL;
  g.t0 = cost; g.len = g.a.distanceTo(g.b); cost += g.len; g.t1 = cost; prev = g.b;
}
const drawCost = cost;
const drawnGeom = new LineSegmentsGeometry();
const segArr = new Float32Array(segs.length * 6);
segs.forEach((g, i) => { segArr.set([g.a.x, g.a.y + 0.003, g.a.z, g.b.x, g.b.y + 0.003, g.b.z], i * 6); });
drawnGeom.setPositions(segArr);
const segOrig = segArr.slice();
const drawnLines = new LineSegments2(drawnGeom, lineMat(3.2));
drawnLines.material.depthTest = false;
drawnLines.renderOrder = 5;
scene.add(drawnLines);
pencil.renderOrder = 6; marker.renderOrder = 6;

// 3D edge lines attached to every mesh (shown once things pop up)
const edgeMat = lineMat(2.4, 0);
for (const m of allMeshes) {
  const arr = [];
  for (const [a, b] of meshSegments(m)) arr.push(...a, ...b);
  if (!arr.length) continue;
  const g = new LineSegmentsGeometry(); g.setPositions(arr);
  const l = new LineSegments2(g, edgeMat); l.renderOrder = 3; m.add(l);
}

// ---------------------------------------------------------------- colouring jobs
const jobs = [];
for (const m of orderedMeshes) {
  if (!m.userData.job) continue;
  const box = new THREE.Box3().setFromObject(m);
  const w = box.max.x - box.min.x, d = box.max.z - box.min.z;
  if (w < 1e-3 || d < 1e-3) continue;
  const brush = THREE.MathUtils.clamp(Math.sqrt(w * d) / 4.5, 0.09, 0.5);
  const rows = Math.max(1, Math.round(d / brush));
  const u = m.material.userData.u;
  u.uBox.value.set(box.min.x, box.min.z, box.max.x, box.max.z); u.uRows.value = rows;
  // visible fraction -> skip work on fully hidden meshes
  let vis = 0; const N = 12;
  for (let i = 0; i < N; i++) {
    const P = new THREE.Vector3(box.min.x + w * ((i * 0.618) % 1), box.max.y, box.min.z + d * (i + .5) / N);
    ray.set(camera.position, P.clone().sub(camera.position).normalize());
    const h = ray.intersectObjects(allMeshes, false)[0]; if (h && h.object === m) vis++;
  }
  jobs.push({ m, box, rows, len: rows * w, y: box.max.y, hidden: vis === 0, color: m.userData.color });
}
// keep order by mesh order, chain by proximity inside equal order
{
  const res = []; let pos = new THREE.Vector3(0, 0, 0);
  const byOrder = new Map();
  for (const j of jobs) { const k = j.m.userData.order; if (!byOrder.has(k)) byOrder.set(k, []); byOrder.get(k).push(j); }
  for (const k of [...byOrder.keys()].sort((a, b) => a - b)) {
    const left = byOrder.get(k);
    while (left.length) {
      let bi = 0, bd = 1e9;
      left.forEach((j, i) => { const d = Math.hypot(j.box.min.x - pos.x, j.box.min.z - pos.z); if (d < bd) { bd = d; bi = i; } });
      const j = left.splice(bi, 1)[0]; res.push(j); pos = new THREE.Vector3(j.box.max.x, 0, j.box.max.z);
    }
  }
  jobs.length = 0; jobs.push(...res);
}
cost = 0; prev = new THREE.Vector3(0, 0, 0);
for (const j of jobs) {
  const len = j.hidden ? 0 : j.len;
  cost += prev.distanceTo(new THREE.Vector3(j.box.min.x, 0, j.box.min.z)) * TRAVEL * (j.hidden ? 0 : 1);
  j.t0 = cost; cost += len; j.t1 = cost;
  prev = new THREE.Vector3(j.box.max.x, 0, j.box.max.z);
}
const colorCost = cost;
function jobPoint(j, r) {  // marker position for reveal fraction r
  const s = r * j.rows, row = Math.min(j.rows - 1, Math.floor(s)); let xf = s - row;
  if (row % 2) xf = 1 - xf;
  return new THREE.Vector3(j.box.min.x + (j.box.max.x - j.box.min.x) * xf, j.y + 0.004,
                           j.box.min.z + (j.box.max.z - j.box.min.z) * (row + .5) / j.rows);
}

// pop-up schedule
const popPieces = pieces.filter(p => !p.flatOnly).sort((a, b) => a.popOrder - b.popOrder);
popPieces.forEach((p, i) => { p.popDelay = 0.25 + 0.55 * (i / Math.max(1, popPieces.length - 1)); });

// ---------------------------------------------------------------- timeline
const F = s => Math.round(s * FPS);
const nHook = F(T.hook), nRew = F(T.rewind), nBlank = F(T.blank);
const P0 = nHook + nRew + nBlank;                        // process starts
const pDraw = F(T.draw), pColor = F(T.color), pPop = F(T.pop), pOrbit = F(T.orbit);
const PROC = pDraw + pColor + pPop + pOrbit;             // process frames
const TOTAL = P0 + PROC;
const ease = t => t * t * (3 - 2 * t);
const easeOutBack = t => { const c1 = 1.5, c3 = c1 + 1; return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2); };
const A0 = -0.55, A1 = 0.5;     // orbit angles

const titleEl = document.getElementById('title'), badgeEl = document.getElementById('badge');
titleEl.innerHTML = `${CITY.title}<span class="sub">${CITY.subtitle || ''}</span>`;
titleEl.style.fontSize = `${Math.round(Math.min(W, H) * 0.12)}px`;
badgeEl.style.fontSize = `${Math.round(Math.min(W, H) * 0.035)}px`;
document.getElementById('btxt').textContent = Q.get('speed') || 'x16';
function badge(kind, a) {
  badgeEl.style.opacity = a;
  document.getElementById('ico').innerHTML = kind === 'ff'
    ? '<path d="M0 0 L9 5 L0 10Z M10 0 L19 5 L10 10Z" fill="#fff"/>'
    : '<path d="M9 0 L0 5 L9 10Z M19 0 L10 5 L19 10Z" fill="#fff"/>';
  document.getElementById('btxt').style.display = kind === 'ff' ? '' : 'none';
}

// state at process time k (frames since process start, may be fractional)
function applyProcess(k, opts = {}) {
  const dk = THREE.MathUtils.clamp(k / pDraw, 0, 1) * drawCost;
  const ck = THREE.MathUtils.clamp((k - pDraw) / pColor, 0, 1) * colorCost;
  const pk = THREE.MathUtils.clamp((k - pDraw - pColor) / pPop, 0, 1);
  const ok = THREE.MathUtils.clamp((k - pDraw - pColor - pPop) / pOrbit, 0, 1);
  // --- lines
  segArr.set(segOrig);
  let n = 0, pen = null, lifted = 0;
  if (dk > 0) {
    let lo = 0, hi = segs.length;
    while (lo < hi) { const mid = (lo + hi) >> 1; if (segs[mid].t1 <= dk) lo = mid + 1; else hi = mid; }
    n = lo;
    if (n < segs.length) {
      const g = segs[n];
      if (dk > g.t0) {
        const t = (dk - g.t0) / g.len; const P = g.a.clone().lerp(g.b, t);
        segArr.set([P.x, P.y + 0.003, P.z], n * 6 + 3); n += 1; pen = P;
      } else {
        const from = n ? segs[n - 1].b : new THREE.Vector3(-8, 0, -5);
        const span = g.t0 - (n ? segs[n - 1].t1 : 0);
        const t = span > 0 ? 1 - (g.t0 - dk) / span : 1;
        pen = from.clone().lerp(g.a, t); lifted = Math.sin(Math.PI * t);
      }
    } else pen = segs.length ? segs[segs.length - 1].b.clone() : null;
  }
  drawnGeom.attributes.instanceStart.data.needsUpdate = true;
  drawnGeom.instanceCount = n;
  // --- colours
  let mpos = null, mcol = null, mlift = 0, mactive = false;
  for (const j of jobs) {
    let r = 0;
    if (ck >= j.t1) r = 1; else if (ck > j.t0) r = (ck - j.t0) / (j.t1 - j.t0);
    if (k >= pDraw + pColor) r = 1;
    j.m.material.userData.u.uReveal.value = r;
    if (!mpos && ck > 0 && ck < j.t1 && !j.hidden) {
      if (ck > j.t0) { mpos = jobPoint(j, r); mactive = true; }
      else { mpos = jobPoint(j, 0); mlift = 1; }
      mcol = j.color;
    }
  }
  // cards only exist visually once colouring starts (blank paper must be blank)
  const show = k >= pDraw - 1;
  if (show !== applyProcess.shown) { applyProcess.shown = show; for (const m of allMeshes) m.visible = show; }
  // --- pop-up
  const lineFade = THREE.MathUtils.clamp(pk / 0.06, 0, 1);
  drawnLines.material.opacity = 1 - lineFade;
  edgeMat.opacity = lineFade;
  drawnLines.visible = lineFade < 1;
  for (const p of popPieces) {
    const t = THREE.MathUtils.clamp((pk - p.popDelay) / 0.32, 0, 1);
    setFold(p, 1 - (t > 0 ? easeOutBack(t) : 0));
  }
  // --- camera
  const drift = k / FPS * 0.06;
  if (pk <= 0) setCamTop(drift);
  else {
    const c = ease(THREE.MathUtils.clamp((pk - 0.05) / 0.85, 0, 1));
    const a = THREE.MathUtils.lerp(A0, A1, ok > 0 ? ease(ok) : 0);
    setCamTop(drift);
    const from = camera.position.clone();
    const to = orbitPos(A0 + (a - A0));
    camera.position.lerpVectors(from, to, c);
    const look = camTopLook.clone().lerp(orbitTarget, c);
    camera.lookAt(look);
    if (ok > 0) { camera.position.copy(orbitPos(a)); camera.lookAt(orbitTarget); }
  }
  // --- tools
  const toolsOn = !opts.noTools;
  pencil.visible = toolsOn && pen && k < pDraw + 2;
  if (pencil.visible) {
    pencil.position.copy(pen); pencil.position.y += 0.02 + lifted * 0.25;
    if (k >= pDraw) {  // fly away at end of drawing
      const e = (k - pDraw) / 2; pencil.position.add(new THREE.Vector3(6, 6, 6).multiplyScalar(e));
    }
  }
  marker.visible = toolsOn && k >= pDraw && k < pDraw + pColor + F(0.8) && !!(mpos || k >= pDraw + pColor);
  if (marker.visible) {
    if (!mpos) { // leaving
      const e = (k - pDraw - pColor) / F(0.8);
      const last = jobs.length ? jobPoint(jobs[jobs.length - 1], 1) : new THREE.Vector3();
      mpos = last.add(new THREE.Vector3(7, 7, 7).multiplyScalar(e * e));
    }
    marker.position.copy(mpos); marker.position.y += 0.02 + mlift * 0.3;
    if (mcol) marker.userData.colorParts.forEach(mm => mm.color.copy(mcol));
  }
  return { drawing: n > 0 && !lifted && k < pDraw && dk < drawCost, coloring: mactive, pk };
}

const acts = [], pops = [];
window.info = { total: TOTAL, fps: FPS, strokes: strokes.length, segs: segs.length, jobs: jobs.length,
                pieces: pieces.length, hook: nHook, rewind: nRew };

window.renderFrame = (i) => {
  let act = 0;
  titleEl.style.opacity = 0; badge('ff', 0);
  if (i < nHook) {                                   // HOOK: finished model, orbit + title
    const t = i / Math.max(1, nHook - 1);
    applyProcess(PROC, { noTools: true });
    const a = A1 + 0.35 * (1 - ease(t));
    camera.position.copy(orbitPos(a, OR - 2.2 * (1 - ease(t)), OH + 1.4 * (1 - t))); camera.lookAt(orbitTarget);
    titleEl.style.opacity = Math.min(1, t / 0.15) * Math.min(1, (1 - t) / 0.12);
  } else if (i < nHook + nRew) {                     // REWIND: whole process backwards, fast
    const t = (i - nHook) / Math.max(1, nRew - 1);
    const k = PROC * (1 - ease(t));
    applyProcess(k, { noTools: true });
    badge('rw', 1);
    act = 3;
  } else if (i < P0) {                               // blank paper beat
    applyProcess(0, { noTools: true });
  } else {
    const k = i - P0;
    const st = applyProcess(k);
    if (k < pDraw + pColor) badge('ff', Math.min(1, k / FPS * 2) * Math.min(1, (pDraw + pColor - k) / FPS * 2));
    act = st.drawing ? 1 : st.coloring ? 2 : 0;
    if (k >= PROC - F(3.2)) titleEl.style.opacity = Math.min(1, (k - (PROC - F(3.2))) / F(0.7));
  }
  renderer.render(scene, camera);
  acts[i] = act;
  return act;
};
// pop times (seconds) for sound effects
window.info.pops = popPieces.map(p => (P0 + pDraw + pColor + (p.popDelay + 0.05) * pPop) / FPS);
window.ready = true;
