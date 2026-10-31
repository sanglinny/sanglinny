// City definitions for the 3D pop-up renderer.
// World layout (paper 16 x 9.2, y up, -z = top of screen when looking down):
//   z = SPINE      the sky card is hinged here and folds up into a back wall
//   z ~ 1.2        back row of buildings (relief cards)
//   z ~ 1.9        front row
//   z ~ 2.6        hero landmark (full 3D)
//   z > 3          ground / water printed on the paper (stays flat)
// Every piece stands on y=0 with its front face at local z=0 and extends to -z.
import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';

const SPINE = 0.3;
let X0 = -7.4, X1 = 7.4, ZTOP = -4.3, ZBOT = 4.4;
export const LAYOUT = { X0, X1, ZTOP, ZBOT };
export function setLayout(short, custom) {    // 9:16 = narrower paper, taller sky
  if (short) { X0 = -4.3; X1 = 4.3; ZTOP = -8.2; }
  const c = custom && custom[short ? 'short' : 'wide'];
  if (c) ({ X0 = X0, X1 = X1, ZTOP = ZTOP, ZBOT = ZBOT } = c);
  Object.assign(LAYOUT, { X0, X1, ZTOP, ZBOT });
}

// deterministic rng
function rng(seed) { let s = seed * 9301 + 49297; return () => ((s = (s * 16807) % 2147483647) / 2147483647); }
const pick = (r, a) => a[Math.floor(r() * a.length) % a.length];

// ------------------------------------------------------------- geometry helpers
const box = (w, h, d, x = 0, y = 0, z = 0) => new THREE.BoxGeometry(w, h, d).translate(x, y, z);
function extrude(pts, depth, z0 = 0) {      // pts in xy; extruded from z0 back by depth
  const s = new THREE.Shape(pts.map(([x, y]) => new THREE.Vector2(x, y)));
  return new THREE.ExtrudeGeometry(s, { depth, bevelEnabled: false, curveSegments: 6 }).translate(0, 0, z0 - depth);
}
function frustum(rTop, rBot, h, seg, x, y0, z) { // square (seg=4) frustum standing on y0
  const g = new THREE.CylinderGeometry(rTop, rBot, h, seg, 1);
  if (seg === 4) g.rotateY(Math.PI / 4);
  return g.translate(x, y0 + h / 2, z);
}
function beam(a, b, r) {
  const A = new THREE.Vector3(...a), B = new THREE.Vector3(...b);
  const g = new THREE.CylinderGeometry(r, r * 1.25, A.distanceTo(B), 4, 1);
  g.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), B.clone().sub(A).normalize()));
  return g.translate((A.x + B.x) / 2, (A.y + B.y) / 2, (A.z + B.z) / 2);
}
const merge = (gs) => mergeGeometries(gs.map(g => g.index ? g.toNonIndexed() : g));
function circlePts(cx, cy, r, n = 16, a0 = 0, a1 = Math.PI * 2) {
  const out = []; for (let i = 0; i <= n; i++) { const a = a0 + (a1 - a0) * i / n; out.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]); } return out;
}
function cloudShape(s) {
  const c = [[-1.1, .05, .45], [-.45, .35, .62], [.25, .3, .55], [.85, .05, .4]];
  const pts = [[1.25, -.15], [-1.5, -.15]];
  for (let x = -1.5; x <= 1.25; x += .07) {
    let y = -.15;
    for (const [cx, cy, r] of c) if (Math.abs(x - cx) < r) y = Math.max(y, cy + Math.sqrt(r * r - (x - cx) ** 2));
    pts.push([x, y]);
  }
  return pts.map(([x, y]) => [x * s, y * s]);
}

// ------------------------------------------------------------- reusable parts
function skyCard(api, cfg, r) {
  const { makePiece, addMesh } = api;
  const h = SPINE - ZTOP, w = X1 - X0;
  const p = makePiece(0, SPINE, { order: 90, popOrder: -10 });
  const birds = [];
  for (let i = 0; i < 4; i++) {
    const bx = X0 + 2 + r() * (X1 - X0 - 4), by = h - 1.2 - r() * 1.2, s = 0.13;
    birds.push([[bx - s, by + s * .4, .045], [bx - s * .4, by + s * .55, .045]], [[bx - s * .4, by + s * .55, .045], [bx, by, .045]],
               [[bx, by, .045], [bx + s * .4, by + s * .55, .045]], [[bx + s * .4, by + s * .55, .045], [bx + s, by + s * .4, .045]]);
  }
  addMesh(p, box(w, h, 0.05, 0, h / 2, -0.025), cfg.sky, [0, 0, 0], { extra: birds, order: 92 });
  const sp = cfg.sunPos || [4.8, 3.55], sx = sp[0] * (X1 / 7.4), sy = h - (4.6 - sp[1]);
  if (cfg.sun) addMesh(p, new THREE.CylinderGeometry(.55, .55, .05, 20).rotateX(Math.PI / 2).translate(sx, sy, .03),
                       cfg.sun, [0, 0, 0], { order: 85, threshold: 40 });
  for (let i = 0; i < (cfg.clouds ?? 3); i++) {
    const nc = cfg.clouds ?? 3, cx = (X0 + 1.4) + (i + r() * .6) * ((X1 - X0 - 2.8) / nc), cy = h - 1.2 - r() * 0.7 - (i % 2) * (h > 6 ? 1.5 : .3);
    addMesh(p, extrude(cloudShape(.55 + r() * .25), .05, .09).translate(cx, cy, 0), '#ffffff', [0, 0, 0], { order: 80, threshold: 40 });
  }
  return p;
}

function groundCard(api, cfg, r) {
  const { makePiece, addMesh } = api;
  const p = makePiece(0, 0, { flatOnly: true, order: 60 });
  const zw = cfg.waterFrom ?? 3.25;
  const kind = cfg.ground || 'river';
  addMesh(p, box(X1 - X0, .02, zw - SPINE, 0, .01, (SPINE + zw) / 2), cfg.groundColor || '#d9cdb8', [0, 0, 0], { order: 60 });
  if (kind === 'street') {
    const extra = [];
    for (let x = X0 + .6; x < X1 - .8; x += 1.6) { extra.push([[x, .023, 3.85], [x + .8, .023, 3.85]]); }
    addMesh(p, box(X1 - X0, .02, ZBOT - zw, 0, .01, (zw + ZBOT) / 2), '#8f9296', [0, 0, 0], { order: 62, extra });
  } else {
    const extra = [];
    for (let i = 0; i < 14; i++) {
      const x = X0 + .4 + r() * (X1 - X0 - 1), z = zw + .2 + r() * (ZBOT - zw - .4), s = .18 + r() * .2;
      extra.push([[x, .023, z], [x + s, .023, z - .05]], [[x + s, .023, z - .05], [x + 2 * s, .023, z]]);
    }
    addMesh(p, box(X1 - X0, .02, ZBOT - zw, 0, .01, (zw + ZBOT) / 2), cfg.water || '#5aa9e6', [0, 0, 0], { order: 62, extra });
  }
  return p;
}

function building(api, x, z, w, h, d, o, r) {
  const { makePiece, addMesh } = api;
  const p = makePiece(x, z, { order: o.order, popOrder: o.popOrder ?? z + r() * .3 });
  addMesh(p, box(w, h, d, 0, h / 2, -d / 2), o.wall, [0, 0, 0], { order: o.order });
  const rs = o.roofStyle;
  let rh = 0;
  if (rs === 'mansard') {
    rh = Math.min(.5, h * .18);
    addMesh(p, extrude([[-w / 2 - .05, 0], [w / 2 + .05, 0], [w / 2 - .12, rh], [-w / 2 + .12, rh]], d + .06, .03).translate(0, h, 0), o.roof, [0, 0, 0], { order: o.order + 1 });
    const dorm = []; const nd = Math.max(1, Math.floor(w / .45));
    for (let i = 0; i < nd; i++) dorm.push(box(.14, .2, .04, -w / 2 + (i + .5) * w / nd, h + rh * .45, .02));
    addMesh(p, merge(dorm), o.win || '#ffe9a8', [0, 0, 0], { order: o.order + 2 });
  } else if (rs === 'gable') {
    rh = Math.min(w * .45, h * .3);
    addMesh(p, extrude([[-w / 2 - .07, 0], [w / 2 + .07, 0], [0, rh]], d + .08, .04).translate(0, h, 0), o.roof, [0, 0, 0], { order: o.order + 1 });
  } else if (rs === 'asian') {
    rh = .3;
    addMesh(p, extrude([[-w / 2 - .2, -.02], [w / 2 + .2, -.02], [w / 2 + .1, .08], [w / 2 - .15, rh], [-w / 2 + .15, rh], [-w / 2 - .1, .08]], d + .12, .06).translate(0, h, 0),
            o.roof, [0, 0, 0], { order: o.order + 1 });
  } else {
    addMesh(p, box(w + .08, .1, d + .08, 0, h + .05, -d / 2), o.roof, [0, 0, 0], { order: o.order + 1 });
  }
  // windows
  const wins = [], cols = Math.max(1, Math.floor(w / .34)), rows = Math.max(1, Math.floor((h - .45) / .42));
  const cw = w / cols;
  for (let rr = 0; rr < rows; rr++) for (let c = 0; c < cols; c++) {
    const wx = -w / 2 + (c + .5) * cw, wy = h - .32 - rr * .42;
    if (wy < .5) continue;
    wins.push(box(cw * .42, .24, .04, wx, wy, .02));
    if (o.balcony && rr > 0) wins.push(box(cw * .7, .04, .1, wx, wy - .16, .05));
  }
  if (wins.length) addMesh(p, merge(wins), o.win || '#ffe9a8', [0, 0, 0], { order: o.order + 2 });
  addMesh(p, box(.22, .36, .05, 0, .18, .025), '#6d4c41', [0, 0, 0], { order: o.order + 2 });
  return p;
}

function rowOfBuildings(api, cfg, r, z, d, hRange, x0, x1, o) {
  let x = x0;
  while (x < x1 - .3) {
    const w = Math.min(x1 - x, o.wMin + r() * (o.wMax - o.wMin));
    if (w < .35) break;
    const h = hRange[0] + r() * (hRange[1] - hRange[0]);
    building(api, x + w / 2, z, w, h, d, { ...o, wall: pick(r, o.walls), roof: pick(r, o.roofs) }, r);
    x += w + .04 + r() * .08;
  }
}

function tree(api, x, z, s, r) {
  const { makePiece, addMesh } = api;
  const p = makePiece(x, z, { order: 40, popOrder: z + 1 });
  addMesh(p, frustum(.06 * s, .09 * s, .55 * s, 6, 0, 0, -.12 * s), '#8d6e63', [0, 0, 0], { order: 41, threshold: 40 });
  const leaf = merge([new THREE.IcosahedronGeometry(.36 * s, 0).translate(0, .78 * s, -.15 * s),
                      new THREE.IcosahedronGeometry(.27 * s, 0).translate(-.25 * s, .6 * s, -.12 * s),
                      new THREE.IcosahedronGeometry(.27 * s, 0).translate(.25 * s, .6 * s, -.12 * s)]);
  addMesh(p, leaf, '#5fae4e', [0, 0, 0], { order: 40, threshold: 50 });
}

function boat(api, x, z) {
  const { makePiece, addMesh } = api;
  const p = makePiece(x, z, { order: 45, popOrder: 9 });
  addMesh(p, extrude([[-.7, .18], [.7, .18], [.55, 0], [-.55, 0]], .4, 0), '#ffffff', [0, 0, 0], { order: 45 });
  addMesh(p, box(.6, .25, .25, -.05, .3, -.2), '#e74c3c', [0, 0, 0], { order: 46 });
}

// ------------------------------------------------------------- landmarks
function eiffel(api, x, z, s = 1, col = '#9a6b43', deck = '#7d5434') {
  const { makePiece, addMesh } = api;
  const p = makePiece(x, z, { order: 10, popOrder: 0 });
  const k = s, D = 2.0 * k, cz = -D / 2;
  const legs = [];
  for (const sx of [-1, 1]) for (const sz of [-1, 1])
    legs.push(beam([sx * 1.0 * k, 0, cz + sz * 1.0 * k], [sx * .5 * k, 1.55 * k, cz + sz * .5 * k], .14 * k));
  addMesh(p, merge(legs), col, [0, 0, 0], { order: 10, threshold: 40,
    extra: [[[-.78 * k, .7 * k, 0], [-.48 * k, 1.1 * k, .0]], [[.78 * k, .7 * k, 0], [.48 * k, 1.1 * k, 0]]] });
  const arch = [];
  for (const az of [.02, -D - .02]) arch.push(new THREE.TorusGeometry(.62 * k, .06 * k, 4, 12, Math.PI).translate(0, .32 * k, az));
  addMesh(p, merge(arch), col, [0, 0, 0], { order: 11, threshold: 40 });
  addMesh(p, box(2.25 * k, .18 * k, 2.25 * k, 0, 1.64 * k, cz), deck, [0, 0, 0], { order: 12 });
  const m1 = frustum(.42 * k, .74 * k, 1.9 * k, 4, 0, 1.73 * k, cz);
  const lat = (y0, y1, hb, ht, n) => {
    const out = [];
    for (let i = 0; i < n; i++) {
      const a = y0 + (y1 - y0) * i / n, b = y0 + (y1 - y0) * (i + 1) / n;
      const wa = hb + (ht - hb) * i / n, wb = hb + (ht - hb) * (i + 1) / n;
      const za = cz + wa + .01, zb = cz + wb + .01;
      out.push([[-wa, a, za], [wb, b, zb]], [[wa, a, za], [-wb, b, zb]]);
    }
    return out;
  };
  addMesh(p, m1, col, [0, 0, 0], { order: 13, extra: lat(1.73 * k, 3.63 * k, .74 * k * .707, .42 * k * .707, 3) });
  addMesh(p, box(1.2 * k, .13 * k, 1.2 * k, 0, 3.69 * k, cz), deck, [0, 0, 0], { order: 14 });
  addMesh(p, frustum(.1 * k, .4 * k, 2.1 * k, 4, 0, 3.75 * k, cz), col, [0, 0, 0], { order: 15, extra: lat(3.75 * k, 5.85 * k, .4 * k * .707, .1 * k * .707, 5) });
  addMesh(p, box(.3 * k, .22 * k, .3 * k, 0, 5.95 * k, cz), deck, [0, 0, 0], { order: 16 });
  addMesh(p, frustum(.01 * k, .05 * k, .45 * k, 4, 0, 6.06 * k, cz), deck, [0, 0, 0], { order: 16 });
}

function clockTower(api, x, z, s = 1, stone = '#d9b77a', roof = '#4c5a6b') {
  const { makePiece, addMesh } = api;
  const p = makePiece(x, z, { order: 10, popOrder: 0 });
  const D = .9 * s, cz = -D / 2;
  addMesh(p, box(.9 * s, 3.6 * s, D, 0, 1.8 * s, cz), stone, [0, 0, 0], { order: 10 });
  addMesh(p, box(1.1 * s, 1.0 * s, D + .2 * s, 0, 4.1 * s, cz), stone, [0, 0, 0], { order: 11 });
  addMesh(p, new THREE.CylinderGeometry(.38 * s, .38 * s, .06, 20).rotateX(Math.PI / 2).translate(0, 4.1 * s, .14 * s), '#fff6dc', [0, 0, 0],
    { order: 12, threshold: 40, extra: [[[0, 4.1 * s, .18 * s], [0, 4.36 * s, .18 * s]], [[0, 4.1 * s, .18 * s], [.18 * s, 4.04 * s, .18 * s]]] });
  addMesh(p, box(.95 * s, .5 * s, D, 0, 4.85 * s, cz), '#c9a76c', [0, 0, 0], { order: 13 });
  addMesh(p, frustum(.0, .72 * s, 1.3 * s, 4, 0, 5.1 * s, cz), roof, [0, 0, 0], { order: 14 });
  const wins = [];
  for (let i = 0; i < 6; i++) for (const sx of [-.2, .2]) wins.push(box(.14 * s, .3 * s, .04, sx * s, (.5 + i * .5) * s, .02));
  for (const sx of [-.28, 0, .28]) wins.push(box(.16 * s, .28 * s, .04, sx * s, 4.85 * s, .02));
  addMesh(p, merge(wins), '#5d4630', [0, 0, 0], { order: 15 });
}

function pagoda(api, x, z, s = 1, tiers = 5, wall = '#c0392b', roof = '#2f3b4a', order = 10) {
  const { makePiece, addMesh } = api;
  const p = makePiece(x, z, { order, popOrder: order === 10 ? 0 : 1 });
  const D = 1.4 * s, cz = -D / 2;
  addMesh(p, box(1.9 * s, .25 * s, D + .3 * s, 0, .125 * s, cz), '#b9a58a', [0, 0, 0], { order });
  const th = 4.6 * s / tiers; let y = .25 * s;
  const walls = [], roofs = [], doors = [];
  for (let i = 0; i < tiers; i++) {
    const ww = 1.25 * s * (1 - i * .11);
    walls.push(box(ww, th * .62, D * (1 - i * .11), 0, y + th * .31, cz));
    doors.push(box(ww * .35, th * .45, .04, 0, y + th * .25, cz + D * (1 - i * .11) / 2 + .02));
    roofs.push(frustum(ww * .45, ww * 1.0, th * .38, 4, 0, y + th * .62, cz));
    y += th;
  }
  addMesh(p, merge(walls), wall, [0, 0, 0], { order: order + 1 });
  addMesh(p, merge(doors), '#f1c40f', [0, 0, 0], { order: order + 2 });
  addMesh(p, merge(roofs), roof, [0, 0, 0], { order: order + 1 });
  addMesh(p, frustum(.02 * s, .06 * s, .9 * s, 6, 0, y - th * .1, cz), '#444', [0, 0, 0], { order: order + 3, threshold: 50 });
}

function mountain(api, x, z, s = 1, rock = '#6b7fa8', snow = '#ffffff') {
  const { makePiece, addMesh } = api;
  const p = makePiece(x, z, { order: 70, popOrder: -5 });
  const g = new THREE.ConeGeometry(4.2 * s, 3.4 * s, 9, 1).translate(0, 1.7 * s, 0).scale(1, 1, .1).translate(0, 0, -.45);
  addMesh(p, g, rock, [0, 0, 0], { order: 70, threshold: 20 });
  const cap = new THREE.ConeGeometry(1.45 * s, 1.18 * s, 9, 1).translate(0, 3.4 * s - .59 * s + .02, 0).scale(1, 1, .1).translate(0, 0, -.43);
  addMesh(p, cap, snow, [0, 0, 0], { order: 71, threshold: 20 });
}

function ferrisWheel(api, x, z, s = 1) {
  const { makePiece, addMesh } = api;
  const p = makePiece(x, z, { order: 30, popOrder: 2 });
  const R = 1.9 * s, cy = R + .5 * s;
  addMesh(p, merge([beam([-1 * s, 0, -.25], [0, cy, -.25], .07 * s), beam([1 * s, 0, -.25], [0, cy, -.25], .07 * s)]), '#bdc3c7', [0, 0, 0], { order: 31, threshold: 40 });
  const spokes = [];
  for (let i = 0; i < 16; i++) { const a = i / 16 * Math.PI * 2; spokes.push([[0, cy, -.16], [R * Math.cos(a), cy + R * Math.sin(a), -.16]]); }
  addMesh(p, new THREE.TorusGeometry(R, .06 * s, 4, 32).translate(0, cy, -.2), '#ffffff', [0, 0, 0], { order: 30, threshold: 50, extra: spokes });
  const pods = [];
  for (let i = 0; i < 16; i++) { const a = (i + .5) / 16 * Math.PI * 2; pods.push(new THREE.IcosahedronGeometry(.12 * s, 0).translate(R * 1.05 * Math.cos(a), cy + R * 1.05 * Math.sin(a), -.2)); }
  addMesh(p, merge(pods), '#e74c3c', [0, 0, 0], { order: 32, threshold: 50 });
  addMesh(p, new THREE.CylinderGeometry(.12, .12, .2, 8).rotateX(Math.PI / 2).translate(0, cy, -.2), '#7f8c8d', [0, 0, 0], { order: 32, threshold: 50 });
}

function domeChurch(api, x, z, s = 1, wall = '#f4efe6', domec = '#e3dccb') {
  const { makePiece, addMesh } = api;
  const p = makePiece(x, z, { order: 35, popOrder: 1 });
  const D = .35;
  addMesh(p, box(2.2 * s, 1.0 * s, D, 0, .5 * s, -D / 2), wall, [0, 0, 0], { order: 35 });
  addMesh(p, box(1.0 * s, .5 * s, D, 0, 1.25 * s, -D / 2), wall, [0, 0, 0], { order: 35 });
  const dm = new THREE.SphereGeometry(.55 * s, 10, 5, 0, Math.PI * 2, 0, Math.PI / 2).scale(1, 1.25, .3).translate(0, 1.5 * s, -D / 2);
  const small = [-.8, .8].map(sx => new THREE.SphereGeometry(.25 * s, 8, 4, 0, Math.PI * 2, 0, Math.PI / 2).scale(1, 1.3, .3).translate(sx * s, 1.0 * s, -D / 2));
  addMesh(p, merge([dm, ...small, frustum(.0, .1 * s, .35 * s, 6, 0, 2.15 * s, -D / 2)]), domec, [0, 0, 0], { order: 36, threshold: 35 });
  const wins = []; for (let i = 0; i < 6; i++) wins.push(box(.14 * s, .45 * s, .04, (-.85 + i * .34) * s, .4 * s, .02));
  addMesh(p, merge(wins), '#8e7b62', [0, 0, 0], { order: 37 });
}

function turtleTower(api, x, z, s = 1, wall = '#e9dcc0', roof = '#b0563f') {
  const { makePiece, addMesh } = api;
  const p = makePiece(x, z, { order: 10, popOrder: 0 });
  addMesh(p, new THREE.CylinderGeometry(1.7 * s, 1.9 * s, .15, 10).scale(1, 1, .45).translate(0, .075, -.8 * s), '#6aa84f', [0, 0, 0], { order: 12, threshold: 40 });
  const ws = [1.2, .9, .6], hs = [1.4, 1.0, .8]; let y = .15;
  const walls = [], roofs = [], wins = [];
  for (let i = 0; i < 3; i++) {
    const w = ws[i] * s, h = hs[i] * s, d = w * .8;
    walls.push(box(w, h, d, 0, y + h / 2, -.8 * s));
    const n = 3 - i;
    for (let k = 0; k < n; k++) wins.push(extrude([[-.08 * s, 0], [.08 * s, 0], [.08 * s, h * .45], [0, h * .58], [-.08 * s, h * .45]], .04, .02)
                                        .translate(-w / 2 + (k + .5) * w / n, y + h * .15, -.8 * s + d / 2));
    roofs.push(frustum(w * .55, w * .85, .22 * s, 4, 0, y + h, -.8 * s));
    y += h + .22 * s;
  }
  roofs.push(frustum(0, .3 * s, .55 * s, 4, 0, y, -.8 * s));
  addMesh(p, merge(walls), wall, [0, 0, 0], { order: 10 });
  addMesh(p, merge(roofs), roof, [0, 0, 0], { order: 11 });
  addMesh(p, merge(wins), '#4a3a2c', [0, 0, 0], { order: 12 });
}

// ------------------------------------------------------------- cities
function standardCity(api, cfg) {
  const r = rng(cfg.seed || 1);
  if (api.short) { const k = .58; for (const g of ['gap', 'backGap']) if (cfg[g]) cfg[g] = cfg[g].map(v => v * k); if (cfg.boat) cfg.boat *= k; cfg.trees = Math.min(cfg.trees ?? 5, 3); }
  skyCard(api, cfg, r);
  groundCard(api, cfg, r);
  const gap = cfg.gap || [-1.5, 1.5];
  const back = cfg.backGap || gap;
  rowOfBuildings(api, cfg, r, 1.2, .4, cfg.backH || [1.3, 2.3], X0 + .1, back[0], { wMin: .8, wMax: 1.3, walls: cfg.backWalls || ['#c9d6e3'], roofs: ['#aab7c4'], roofStyle: 'flat', order: 30 });
  rowOfBuildings(api, cfg, r, 1.2, .4, cfg.backH || [1.3, 2.3], back[1], X1 - .1, { wMin: .8, wMax: 1.3, walls: cfg.backWalls || ['#c9d6e3'], roofs: ['#aab7c4'], roofStyle: 'flat', order: 30 });
  const fo = { wMin: cfg.tube ? .55 : .8, wMax: cfg.tube ? .8 : 1.2, walls: cfg.walls, roofs: cfg.roofs, roofStyle: cfg.roofStyle, win: cfg.win, balcony: cfg.tube, order: 20 };
  rowOfBuildings(api, cfg, r, 1.95, .55, cfg.frontH || [1.8, 2.9], X0 + .05, gap[0], fo);
  rowOfBuildings(api, cfg, r, 1.95, .55, cfg.frontH || [1.8, 2.9], gap[1], X1 - .05, fo);
  for (let i = 0; i < (cfg.trees ?? 5); i++) {
    let tx = X0 + .5 + r() * (X1 - X0 - 1);
    if (tx > gap[0] - .3 && tx < gap[1] + .3) tx = tx < 0 ? gap[0] - .5 : gap[1] + .5;
    tree(api, tx, 2.25 + r() * .3, .9 + r() * .4, r);
  }
  if (cfg.boat) boat(api, cfg.boat, 3.95);
}


// ------------------------------------------------------------- New York
function stripes(w, h, y0, z, cols, rowsH = .5) {   // window bands on a facade
  const g = [];
  const n = Math.max(1, Math.floor((h - .3) / rowsH));
  for (let i = 0; i < n; i++) for (let c = 0; c < cols; c++)
    g.push(box(w / cols * .55, rowsH * .55, .04, -w / 2 + (c + .5) * w / cols, y0 + .25 + i * rowsH + rowsH * .3, z));
  return g;
}

function skyscraper(api, x, z, w, h, d, o, r) {
  const { makePiece, addMesh } = api;
  const p = makePiece(x, z, { order: o.order, popOrder: o.popOrder ?? z + r() * .4 });
  const tiers = h > 3.2 && r() < .65 ? 2 + Math.floor(r() * 2) : 1;
  let y = 0, ww = w, dd = d;
  const bodies = [], wins = [];
  for (let t = 0; t < tiers; t++) {
    const th = tiers === 1 ? h : (t === 0 ? h * .6 : h * .4 / (tiers - 1));
    bodies.push(box(ww, th, dd, 0, y + th / 2, -d / 2));
    wins.push(...stripes(ww, th, y, -d / 2 + dd / 2 + .02, Math.max(2, Math.round(ww / .22)), o.glass ? .35 : .42));
    y += th; ww *= .78; dd *= .8;
  }
  addMesh(p, merge(bodies), o.wall, [0, 0, 0], { order: o.order });
  addMesh(p, merge(wins), o.win, [0, 0, 0], { order: o.order + 1 });
  if (r() < .45) addMesh(p, frustum(.015, .03, .5 + r() * .5, 4, 0, y, -d / 2), '#555', [0, 0, 0], { order: o.order + 2, threshold: 50 });
  return p;
}

function skylineRow(api, r, z, d, hr, x0, x1, o, skip = []) {
  let x = x0;
  while (x < x1 - .3) {
    const w = Math.min(x1 - x, o.wMin + r() * (o.wMax - o.wMin));
    if (w < .35) break;
    const cx = x + w / 2;
    if (!skip.some(([a, b]) => cx > a && cx < b)) {
      const h = hr[0] + r() * (hr[1] - hr[0]);
      const glass = r() < .35;
      skyscraper(api, cx, z, w, h, d, { ...o, glass, wall: glass ? pick(r, o.glassWalls) : pick(r, o.walls), win: glass ? '#cfe8ff' : o.win }, r);
    }
    x += w + .03 + r() * .06;
  }
}

function empireState(api, x, z, s = 1) {
  const { makePiece, addMesh } = api;
  const p = makePiece(x, z, { order: 10, popOrder: -3 });
  const st = '#d9cbb0', D = .75 * s, cz = -D / 2;
  const tiers = [[1.5, 1.2], [1.15, 3.0], [.85, 1.0], [.62, .6], [.45, .35]];
  let y = 0; const bodies = [], wins = [];
  for (const [w, h] of tiers) {
    bodies.push(box(w * s, h * s, D * w / 1.5 + .05, 0, y + h * s / 2, cz));
    wins.push(...stripes(w * s, h * s, y, cz + (D * w / 1.5 + .05) / 2 + .02, Math.max(2, Math.round(w * s / .16)), .3));
    y += h * s;
  }
  addMesh(p, merge(bodies), st, [0, 0, 0], { order: 10 });
  addMesh(p, merge(wins), '#7f8fa6', [0, 0, 0], { order: 11 });
  addMesh(p, frustum(.12 * s, .2 * s, .5 * s, 8, 0, y, cz), '#c7c9cc', [0, 0, 0], { order: 12, threshold: 50 });
  addMesh(p, frustum(.01 * s, .05 * s, 1.0 * s, 4, 0, y + .5 * s, cz), '#888', [0, 0, 0], { order: 12, threshold: 50 });
}

function chrysler(api, x, z, s = 1) {
  const { makePiece, addMesh } = api;
  const p = makePiece(x, z, { order: 12, popOrder: -2 });
  const D = .7 * s, cz = -D / 2;
  addMesh(p, merge([box(1.25 * s, 2.0 * s, D, 0, 1.0 * s, cz), box(.95 * s, 2.6 * s, D * .8, 0, 3.3 * s, cz)]), '#cfd3d8', [0, 0, 0], { order: 12 });
  addMesh(p, merge([...stripes(1.25 * s, 2.0 * s, 0, cz + D / 2 + .02, 6, .3), ...stripes(.95 * s, 2.6 * s, 2.0 * s, cz + D * .4 + .02, 5, .3)]), '#6f7d8c', [0, 0, 0], { order: 13 });
  // stacked art-deco crown with sunburst arches
  const crown = [], arches = [];
  let y = 4.6 * s;
  for (let i = 0; i < 5; i++) {
    const w = (.8 - i * .14) * s;
    crown.push(box(w, .38 * s, w * .7, 0, y + .19 * s, cz));
    arches.push(new THREE.TorusGeometry(w * .42, .03 * s, 3, 10, Math.PI).translate(0, y + .02, cz + w * .35 + .02));
    y += .38 * s;
  }
  addMesh(p, merge(crown), '#e3e6ea', [0, 0, 0], { order: 14 });
  addMesh(p, merge(arches), '#8a96a3', [0, 0, 0], { order: 15, threshold: 50 });
  const tri = [];
  for (let i = 0; i < 4; i++) tri.push(box(.07 * s, .1 * s, .04, (-.3 + i * .2) * s * (1 - .1 * i), 4.8 * s + i * .38 * s, cz + .4 * s));
  addMesh(p, frustum(.005 * s, .07 * s, 1.3 * s, 4, 0, y, cz), '#d0d4d9', [0, 0, 0], { order: 16, threshold: 50 });
}

function oneWTC(api, x, z, s = 1) {
  const { makePiece, addMesh } = api;
  const p = makePiece(x, z, { order: 14, popOrder: -2.5 });
  const D = .95 * s, cz = -D / 2;
  addMesh(p, box(1.25 * s, .8 * s, D, 0, .4 * s, cz), '#9fb7c9', [0, 0, 0], { order: 14 });
  // tapering glass tower: square frustum twisted 45 degrees -> octagon facets
  const g = new THREE.CylinderGeometry(.35 * s, .88 * s, 6.6 * s, 4, 1);
  g.rotateY(Math.PI / 4).translate(0, .8 * s + 3.3 * s, cz);
  const pos = g.attributes.position;
  for (let i = 0; i < pos.count; i++) if (pos.getY(i) > .8 * s + 3.3 * s) {  // top ring rotated 45deg
    const vx = pos.getX(i), vz = pos.getZ(i) - cz, a = Math.PI / 4, c = Math.cos(a), sn = Math.sin(a);
    pos.setXYZ(i, vx * c - vz * sn, pos.getY(i), cz + vx * sn + vz * c);
  }
  g.computeVertexNormals();
  addMesh(p, g, '#8fc1e3', [0, 0, 0], { order: 15, threshold: 15 });
  addMesh(p, box(.48 * s, .2 * s, .48 * s, 0, 7.5 * s, cz), '#b8c6d1', [0, 0, 0], { order: 16 });
  addMesh(p, frustum(.01 * s, .05 * s, 1.7 * s, 6, 0, 7.6 * s, cz), '#cfd8dc', [0, 0, 0], { order: 16, threshold: 50 });
}

function liberty(api, x, z, s = 1) {
  const { makePiece, addMesh } = api;
  const p = makePiece(x, z, { order: 9, popOrder: -4 });
  const cz = -.6 * s, G = '#6fb59a';
  addMesh(p, new THREE.CylinderGeometry(1.25 * s, 1.35 * s, .2, 12).scale(1, 1, .7).translate(0, .1, cz), '#7cbf6a', [0, 0, 0], { order: 9, threshold: 40 });
  addMesh(p, merge([frustum(.5 * s, .62 * s, .3 * s, 4, 0, .2, cz), frustum(.36 * s, .42 * s, .9 * s, 4, 0, .2 + .3 * s, cz)]), '#d8c7a3', [0, 0, 0], { order: 9 });
  const y0 = .2 + 1.2 * s;
  const body = [frustum(.16 * s, .3 * s, 1.15 * s, 7, 0, y0, cz),            // robe
                new THREE.IcosahedronGeometry(.12 * s, 0).translate(0, y0 + 1.27 * s, cz),   // head
                beam([.12 * s, y0 + 1.0 * s, cz], [.3 * s, y0 + 1.75 * s, cz], .045 * s),   // raised arm
                beam([-.12 * s, y0 + .9 * s, cz], [-.24 * s, y0 + .7 * s, cz + .05], .04 * s), // tablet arm
                box(.12 * s, .22 * s, .05 * s, -.26 * s, y0 + .72 * s, cz + .08)];        // tablet
  for (let i = 0; i < 5; i++) { const a = Math.PI * (.15 + .7 * i / 4); body.push(beam([0, y0 + 1.33 * s, cz], [Math.cos(a) * .2 * s, y0 + 1.33 * s + Math.sin(a) * .2 * s, cz], .012 * s)); }
  addMesh(p, merge(body), G, [0, 0, 0], { order: 10, threshold: 35 });
  addMesh(p, new THREE.ConeGeometry(.07 * s, .18 * s, 6).translate(.3 * s, y0 + 1.86 * s, cz), '#ffcf3f', [0, 0, 0], { order: 11, threshold: 50 });
}

function brooklynBridge(api, x0, x1, z, s = 1) {
  const { makePiece, addMesh } = api;
  const p = makePiece((x0 + x1) / 2, z, { order: 18, popOrder: 6 });
  const L = x1 - x0, D = .45 * s, cz = -D / 2, dy = .55 * s, th = 2.4 * s;
  const tx = [-L * .27, L * .27];
  addMesh(p, box(L, .1 * s, D, 0, dy, cz), '#8d6e63', [0, 0, 0], { order: 19 });
  const towers = [], cables = [];
  for (const t of tx) {
    towers.push(box(.6 * s, th, D + .1, t, th / 2, cz));
    // two gothic openings (extra lines)
    for (const o of [-.14, .14]) {
      const ox = t + o * s;
      cables.push([[ox - .07 * s, dy + .1 * s, .06], [ox - .07 * s, th * .72, .06]], [[ox + .07 * s, dy + .1 * s, .06], [ox + .07 * s, th * .72, .06]],
                  [[ox - .07 * s, th * .72, .06], [ox, th * .8, .06]], [[ox, th * .8, .06], [ox + .07 * s, th * .72, .06]]);
    }
  }
  // main cables: parabola between towers + to the ends, plus vertical suspenders
  const cab = (xa, xb, ya, yb, sag) => {
    const n = 14; let prev = null;
    for (let i = 0; i <= n; i++) {
      const t = i / n, xx = xa + (xb - xa) * t, yy = ya + (yb - ya) * t - sag * 4 * t * (1 - t);
      const pt = [xx, yy, .05];
      if (prev) cables.push([prev, pt]);
      if (i % 2 === 1) cables.push([pt, [xx, dy + .1 * s, .05]]);
      prev = pt;
    }
  };
  cab(tx[0], tx[1], th * .95, th * .95, th * .7);
  cab(-L / 2, tx[0], dy + .15, th * .95, -.1);
  cab(tx[1], L / 2, th * .95, dy + .15, -.1);
  addMesh(p, merge(towers), '#c9a27e', [0, 0, 0], { order: 18, extra: cables });
}

function taxi(api, x, z) {
  const { makePiece, addMesh } = api;
  const p = makePiece(x, z, { order: 44, popOrder: 7 });
  addMesh(p, merge([box(.55, .16, .28, 0, .11, -.14), box(.32, .13, .24, -.02, .25, -.14)]), '#f7c600', [0, 0, 0], { order: 44 });
  addMesh(p, merge([-.17, .17].map(wx => new THREE.CylinderGeometry(.06, .06, .3, 8).rotateX(Math.PI / 2).translate(wx, .05, -.14))), '#222', [0, 0, 0], { order: 45, threshold: 50 });
}

function newYork(api) {
  const r = rng(31);
  const S = api.short;
  const cfg = { sky: '#ffd3a8', sun: '#ff8c42', sunPos: [S ? 3.2 : 6, 3.9], clouds: S ? 4 : 5, groundColor: '#bdbdbd', water: '#3f7fb5', waterFrom: 3.3 };
  skyCard(api, cfg, r);
  groundCard(api, cfg, r);
  const k = S ? .62 : 1;
  const E = 0, C = -2.7 * k, WTC = 3.0 * k;
  const keep = [[C - .7, C + .7], [E - .8, E + .8], [WTC - .7, WTC + .7]];
  const walls = ['#b0b7bf', '#c9bba3', '#9e9e9e', '#d6cfc2', '#a1887f', '#8d99a6'];
  const glass = ['#7fa7c9', '#6c93b8', '#9bb8cf'];
  skylineRow(api, r, .85, .45, [3.2, 6.2], X0 + .05, X1 - .05, { wMin: .6, wMax: 1.0, walls, glassWalls: glass, win: '#ffe7a3', order: 30 }, keep);
  empireState(api, E, 1.45, 1.05);
  chrysler(api, C, 1.4, .95);
  oneWTC(api, WTC, 1.5, 1.0);
  skylineRow(api, r, 2.0, .45, [1.8, 3.4], X0 + .05, X1 - .05, { wMin: .55, wMax: .95, walls, glassWalls: glass, win: '#ffe7a3', order: 22 }, [[E - .55, E + .55]]);
  skylineRow(api, r, 2.6, .4, [.9, 1.7], X0 + .05, X1 - .05, { wMin: .5, wMax: .85, walls: ['#c46b4e', '#a0522d', '#d9a066', '#b4553f'], glassWalls: glass, win: '#ffe7a3', order: 26 }, []);
  for (let i = 0; i < (S ? 3 : 5); i++) taxi(api, X0 + .8 + r() * (X1 - X0 - 1.6), 3.05);
  for (let i = 0; i < (S ? 3 : 5); i++) tree(api, X0 + .5 + r() * (X1 - X0 - 1), 2.9, .7, r);
  brooklynBridge(api, S ? -.6 : 1.0, X1 - .1, 4.0, S ? .8 : 1.0);
  liberty(api, S ? -2.9 : -5.0, 5.9, S ? 1.15 : 1.35);
  boat(api, S ? 2.6 : 3.2, 5.6);
}

export const CITIES = {
  newyork: {
    title: 'NEW YORK', subtitle: 'USA',
    layout: { short: { X0: -5.4, X1: 5.4, ZTOP: -11.5, ZBOT: 6.6 }, wide: { X0: -8.6, X1: 8.6, ZTOP: -9, ZBOT: 6.6 } },
    camScale: 1.45,
    timing: { draw: 55, color: 50, pop: 8, orbit: 14, hook: 3.5 },
    build: newYork,
  },
  paris: {
    title: 'PARIS', subtitle: 'France',
    build(api) {
      const X = v => api.short ? v * .58 : v;
      const cfg = { seed: 4, sky: '#9cc9f5', sun: '#ffcf5a', groundColor: '#dccfb6', water: '#5aa9e6', roofStyle: 'mansard',
                    walls: ['#f3e1c2', '#efd3a8', '#f6e9d4', '#e9cfae'], roofs: ['#5f6f86', '#6b7b94'], gap: [-1.6, 1.6], boat: 2.4 };
      standardCity(api, cfg);
      domeChurch(api, X(-4.4), .75, api.short ? .75 : 1.1);
      eiffel(api, X(0), 2.75, 1.0);
    },
  },
  london: {
    title: 'LONDON', subtitle: 'United Kingdom',
    build(api) {
      const X = v => api.short ? v * .58 : v;
      const cfg = { seed: 7, sky: '#a7c7e7', sun: null, clouds: 5, groundColor: '#cfc6b8', water: '#4f8fc0', roofStyle: 'gable',
                    walls: ['#c0573f', '#d9a066', '#e6d5b8', '#b4553f'], roofs: ['#3d4a5c', '#5b4a42'], gap: [-2.3, -.6], backGap: [-2.3, 4.0], boat: -4.5 };
      standardCity(api, cfg);
      // fill right side behind the wheel with front row only beyond it
      ferrisWheel(api, X(1.9), 1.0, 1.0);
      clockTower(api, X(-1.45), 2.7, 1.0);
      rowOfBuildings(api, cfg, rng(9), 1.95, .55, [1.6, 2.4], X(4.1), X1 - .05, { wMin: .8, wMax: 1.2, walls: cfg.walls, roofs: cfg.roofs, roofStyle: 'gable', order: 20 });
    },
  },
  tokyo: {
    title: 'TOKYO', subtitle: 'Japan',
    build(api) {
      const X = v => api.short ? v * .58 : v;
      const cfg = { seed: 11, sky: '#ffc2cc', sun: '#ff6b6b', sunPos: [-4.8, 3.4], ground: 'street', groundColor: '#d9d2c5', roofStyle: 'flat',
                    walls: ['#f7f1e3', '#dfe6e9', '#ffeaa7', '#fab1a0'], roofs: ['#636e72', '#2d3436'], gap: [-3.4, 3.2], backGap: [-3.4, 3.2], trees: 4 };
      standardCity(api, cfg);
      mountain(api, X(0), .85, api.short ? .62 : 1.0);
      pagoda(api, X(-1.9), 2.6, .95);
      eiffel(api, X(1.7), 2.75, .92, '#e8452c', '#ffffff');
    },
  },
  hanoi: {
    title: 'HÀ NỘI', subtitle: 'Việt Nam',
    build(api) {
      const X = v => api.short ? v * .58 : v;
      const cfg = { seed: 21, sky: '#9bd3f2', sun: '#ffd34e', ground: 'lake', groundColor: '#cfe3b5', water: '#7cc4b8', waterFrom: 2.4, roofStyle: 'asian', tube: true,
                    walls: ['#f6d26b', '#f3b562', '#9fd8cb', '#f7e3af', '#e8a0a0'], roofs: ['#a8462f', '#8d3b26'], gap: [-2.2, 2.2], backGap: [-1.0, 1.0] };
      standardCity(api, cfg);
      pagoda(api, X(4.6), 1.1, .55, 3, '#c8553d', '#5b3a29', 33);
      turtleTower(api, X(0), 3.9, 1.0);
    },
  },
};
