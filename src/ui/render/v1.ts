/**
 * A costume for the 3D head (see costume.ts): V1, from ULTRAKILL (`look: "v1"`). The long,
 * camera-like head with its yellow lens and the chin plate under it, the bent neck rod, the
 * armoured chest with its two light slits and "V1", the round knob on the upper back, and the
 * eight wing blades fanned out behind (no shoulders or arms). V1 has no mouth: the
 * engine's mouth opens on the chin plate, and the lens and slits glow with the voice.
 *
 * Shapes and proportions are measured from the game's own mesh (borbabcd's rig of it, on
 * GameBanana; reference only) in units of the head's width W, in the head's side view: u forward
 * from the head's front-top corner, v up from it, w to the right.
 */

import { type Costume, type CostumeGroup, type HeadFrame, lerp, Pen, range, smooth, TAU, type V3 } from "./costume.ts";

/** V1's colours, bright enough to read as beams on black */
export const V1 = {
  armor: "#5f78d6",
  armorHi: "#8fa5e8",
  steel: "#6a7a96",
  lens: "#ffe600",
  glow: "#ffa800",
  wing: "#ffd000",
  cable: "#e0303a",
} as const;

type UV = [number, number];

/**
 * The head: rings round it from the back to the front's rim, measured off the mesh's sections.
 * Each is the right half (u, v, w), in this order: 0 the top slot's floor on the midline, 1 its
 * corner, 2–3 the rail's top, inner and outer (two rails run along the top with the slot between
 * them), 4 the top's outer edge, 5 the widest point, 6 the side's foot, 7–8 the underside, out and
 * on the midline. A camera-like body: the top falls towards the front, the underside rises from the
 * chin to the back, and the front's rim is a hood over the lens, set back in it.
 */
const RINGS: V3[][] = [
  [[-1.55, 0.0, 0], [-1.55, 0.0, 0.12], [-1.5, 0.18, 0.12], [-1.5, 0.2, 0.3], [-1.6, 0.08, 0.4], [-1.62, -0.05, 0.4], [-1.63, -0.18, 0.36], [-1.6, -0.2, 0.2], [-1.58, -0.22, 0]],
  [[-1.4, 0.13, 0], [-1.4, 0.13, 0.12], [-1.42, 0.26, 0.13], [-1.42, 0.26, 0.32], [-1.42, 0.18, 0.45], [-1.4, 0.0, 0.48], [-1.4, -0.28, 0.42], [-1.4, -0.32, 0.2], [-1.4, -0.32, 0]],
  [[-1.0, 0.12, 0], [-1.0, 0.12, 0.13], [-1.0, 0.17, 0.13], [-1.0, 0.17, 0.3], [-1.0, 0.1, 0.47], [-1.0, -0.05, 0.5], [-1.0, -0.38, 0.42], [-1.0, -0.5, 0.2], [-1.0, -0.55, 0]],
  [[-0.65, -0.01, 0], [-0.65, -0.01, 0.13], [-0.65, 0.04, 0.13], [-0.65, 0.04, 0.28], [-0.65, 0.0, 0.42], [-0.65, -0.15, 0.45], [-0.62, -0.55, 0.38], [-0.62, -0.78, 0.22], [-0.6, -0.8, 0]],
  [[-0.35, -0.05, 0], [-0.35, -0.05, 0.13], [-0.35, 0.0, 0.13], [-0.35, 0.0, 0.27], [-0.35, -0.05, 0.37], [-0.35, -0.25, 0.44], [-0.33, -0.55, 0.37], [-0.38, -0.64, 0.28], [-0.4, -0.64, 0]],
  [[-0.09, -0.12, 0], [-0.09, -0.12, 0.12], [-0.06, -0.04, 0.12], [-0.05, -0.05, 0.25], [-0.02, -0.12, 0.35], [-0.06, -0.3, 0.4], [-0.23, -0.6, 0.33], [-0.3, -0.62, 0.22], [-0.33, -0.6, 0]],
];
/** the ring vertices that read as the head's edges */
const EDGES = [2, 3, 5, 6];

export function v1Head(h: HeadFrame): Costume {
  const k = h.k;
  const W = 15.5 * k;
  // the mouth (the lips' edge) lands on the chin's front
  const LIP_U = -0.26, LIP_V = -0.8;
  const ox = h.lip.x - LIP_U * W + 0.3 * k, oy = h.lip.y - LIP_V * W;
  const P = (u: number, v: number, w: number): V3 => [ox + u * W, oy + v * W, w * W];
  const groups: CostumeGroup[] = [];
  const face: CostumeGroup[] = [];
  const group = (color: string, width: number, alpha: number, fill: (L: Pen) => void, hot = false, into = groups) => {
    const L = new Pen();
    fill(L);
    into.push({ lines: L.lines, color, width, alpha, hot });
  };
  /** a closed ring through (u, v, w) points, and its mirror image as one loop */
  const loop = (half: V3[]): V3[] => [...half.map(([u, v, w]) => P(u, v, w)), ...half.slice().reverse().map(([u, v, w]) => P(u, v, -w))];

  // ---------------------------------------------------------------- the head
  const along = (i: number, side: number): V3[] => RINGS.map((r) => P(r[i][0], r[i][1], side * r[i][2]));
  group(V1.armor, 1.6, 1, (L) => {
    L.path(loop(RINGS[0]), true);
    L.path(loop(RINGS[RINGS.length - 1].slice(0, 7)));
    for (const i of EDGES) for (const side of [1, -1]) L.path(along(i, side));
  }, true);
  group(V1.armor, 1.0, 0.5, (L) => {
    for (const r of RINGS.slice(1, -1)) L.path(loop(r), true);
    for (const i of [0, 1, 4, 7]) for (const side of i === 0 ? [1] : [1, -1]) L.path(along(i, side));
    L.path(along(8, 1).slice(0, -1));
  });
  // on the left side: the barcode near the top at the back, and a long slot below it
  group(V1.armorHi, 1.0, 0.8, (L) => {
    for (let i = 0; i < 11; i++) {
      const u = -1.25 + 0.022 * i + (i % 3 === 0 ? 0.008 : 0);
      L.path([P(u, 0.02, -0.495), P(u, i % 4 === 1 ? 0.09 : 0.12, -0.49)]);
    }
    L.path([P(-1.15, -0.12, -0.5), P(-0.6, -0.26, -0.47), P(-0.6, -0.31, -0.46), P(-1.15, -0.17, -0.5)], true);
  });

  // the lens, set back under the hood, looking forward and down
  const n: UV = [Math.cos(0.65), -Math.sin(0.65)];
  const lc: UV = [-0.2, -0.33];
  /** a point on the lens' plane: a across (to the right), b up it (W units) */
  const lens = (a: number, b: number, out = 0): V3 => P(lc[0] - n[1] * b + n[0] * out, lc[1] + n[0] * b + n[1] * out, a);
  const circle = (r: number, ca = 0, cb = 0, out = 0, m = 32): V3[] => range(m).map((t) => lens(ca + r * Math.cos(t * TAU), cb + r * Math.sin(t * TAU), out));
  group(V1.steel, 1.4, 0.9, (L) => {
    // the octagonal housing
    const oct = (out: number) => range(8).map((t) => lens(0.27 * Math.cos((t + 0.5) * (TAU / 8)), 0.27 * Math.sin((t + 0.5) * (TAU / 8)), out));
    L.path(oct(-0.06));
    L.path(oct(0.02));
    const a = oct(-0.06), b = oct(0.02);
    for (let i = 0; i < 8; i++) L.path([a[i], b[i]]);
    // the recess behind the hood, on the midline: down from the brow to the chin
    L.path([[-0.09, -0.12], [-0.28, -0.3], [-0.37, -0.53], [-0.3, -0.68]].map(([u, v]) => P(u, v, 0)));
  });
  group(V1.armorHi, 1.2, 0.85, (L) => L.path(circle(0.23, 0, 0, 0.03)));

  // the chin under the lens: a block narrowing downwards, on a plate that juts out either side;
  // its front carries the mouth
  const CHIN = { ft: [-0.3, -0.68], fb: [-0.22, -0.93], bt: [-0.47, -0.66], bb: [-0.47, -0.93], wt: 0.22, wb: 0.13 };
  const chinFront = (s: number): UV => [lerp(CHIN.ft[0], CHIN.fb[0], s), lerp(CHIN.ft[1], CHIN.fb[1], s)];
  const chinBack = (s: number): UV => [lerp(CHIN.bt[0], CHIN.bb[0], s), lerp(CHIN.bt[1], CHIN.bb[1], s)];
  const chinW = (s: number) => lerp(CHIN.wt, CHIN.wb, s);
  group(V1.steel, 1.5, 1, (L) => {
    for (const side of [1, -1]) {
      L.path([0, 1].map((s) => P(...chinBack(s), side * chinW(s))));
      L.path([P(...chinFront(1), side * chinW(1)), P(...chinBack(1), side * chinW(1))]);
      L.path([P(...chinFront(0), side * chinW(0)), P(...chinBack(0), side * chinW(0))]);
    }
    L.path(loop([[...CHIN.bt, CHIN.wt] as V3, [...CHIN.bb, CHIN.wb] as V3]), true);
    // the plate
    L.path(loop([[-0.29, -0.66, 0.36], [-0.46, -0.66, 0.36]]), true);
  }, true);
  group(V1.steel, 1.5, 1, (L) => {
    for (const side of [1, -1]) L.path([0, 1].map((s) => P(...chinFront(s), side * chinW(s))));
    L.path([P(...chinFront(0), -CHIN.wt), P(...chinFront(0), CHIN.wt)]);
    L.path([P(...chinFront(1), -CHIN.wb), P(...chinFront(1), CHIN.wb)]);
  }, true, face);
  group(V1.steel, 1.0, 0.6, (L) => {
    for (let s = 0.15; s < 0.95; s += 0.14) L.path(range(16).map((t) => P(...chinFront(s), lerp(-1, 1, t) * chinW(s))));
  }, false, face);
  const faceX = (y: number): number => {
    const s = Math.max(0, Math.min(1, ((y - oy) / W - CHIN.ft[1]) / (CHIN.fb[1] - CHIN.ft[1])));
    return ox + chinFront(s)[0] * W;
  };

  // ---------------------------------------------------------------- neck and back
  /** a tube between two side-view points, r in W */
  const tube = (L: Pen, a: UV, b: UV, r: number, rings = true) => {
    const du = b[0] - a[0], dv = b[1] - a[1], l = Math.hypot(du, dv);
    const nu = -dv / l, nv = du / l;
    const at = (p: UV, an: number): V3 => P(p[0] + nu * r * Math.cos(an), p[1] + nv * r * Math.cos(an), r * Math.sin(an));
    for (let i = 0; i < 6; i++) L.path([at(a, (i * TAU) / 6), at(b, (i * TAU) / 6)]);
    if (rings) for (const p of [a, b]) L.path(range(16).map((t) => at(p, t * TAU)));
  };
  group(V1.steel, 1.3, 0.85, (L) => {
    tube(L, [-1.54, -0.3], [-1.12, -0.75], 0.125);
    tube(L, [-1.12, -0.75], [-0.82, -1.5], 0.15);
  });
  group(V1.steel, 1.2, 0.75, (L) => {
    // the knob on the upper back: a short drum looking backwards
    const drum = (u: number, r: number): V3[] => range(20).map((t) => P(u, -1.24 + r * Math.sin(t * TAU), r * Math.cos(t * TAU)));
    L.path(drum(-2.12, 0.2));
    L.path(drum(-1.95, 0.24));
    for (let i = 0; i < 8; i++) {
      const an = (i * TAU) / 8;
      L.path([P(-2.12, -1.24 + 0.2 * Math.sin(an), 0.2 * Math.cos(an)), P(-1.95, -1.24 + 0.24 * Math.sin(an), 0.24 * Math.cos(an))]);
    }
  });

  // ---------------------------------------------------------------- the chest
  // Rings round the armour from the collar down: [v, half-width, front u, back u]; the front is
  // two plates meeting at a ridge, their lower edges dropping to a V in the middle.
  const LEVELS: [number, number, number, number][] = [[-0.98, 0.62, -0.5, -1.85], [-1.25, 0.81, -0.2, -2.0], [-1.9, 0.8, -0.17, -2.04], [-2.25, 0.72, -0.3, -1.95]];
  const chestRing = ([v, hw, uf, ub]: (typeof LEVELS)[number], vee = 0): V3[] =>
    loop([[uf, v - vee, 0], [uf - 0.1, v - 0.6 * vee, 0.45 * hw], [uf - 0.35, v, hw], [ub + 0.3, v, hw], [ub, v, 0.55 * hw], [ub, v, 0]]);
  group(V1.armor, 1.6, 1, (L) => {
    L.path(chestRing(LEVELS[0]), true);
    L.path(chestRing(LEVELS[3], 0.22), true);
    const rings = LEVELS.map((l, i) => chestRing(l, i === 3 ? 0.22 : 0));
    for (const j of [2, 3, 9, 10]) L.path(rings.map((r) => r[j]));
    // the ridge down the middle of the front
    L.path(rings.map((r) => r[0]));
  }, true);
  group(V1.armor, 1.0, 0.5, (L) => {
    L.path(chestRing(LEVELS[1]), true);
    L.path(chestRing(LEVELS[2]), true);
    const rings = LEVELS.map((l, i) => chestRing(l, i === 3 ? 0.22 : 0));
    for (const j of [1, 4, 5, 6, 7, 8, 11]) L.path(rings.map((r) => r[j]));
  });
  // the collar: a low band round the neck's base
  group(V1.steel, 1.1, 0.7, (L) => {
    for (const v of [-0.98, -0.9]) L.path(range(24).map((t) => P(-1.2 + 0.42 * Math.cos(t * TAU), v, 0.5 * Math.sin(t * TAU))));
  });
  // the light slits, one each side low on the front plates, and "V1" over the left one
  const front = (w: number, v: number): V3 => {
    const hw = 0.8, uf = -0.17;
    const t = Math.abs(w) / hw;
    const u = t < 0.45 ? lerp(uf, uf - 0.1, t / 0.45) : lerp(uf - 0.1, uf - 0.35, (t - 0.45) / 0.55);
    return P(u + 0.02, v, w);
  };
  const slits = [1, -1].map((side) => ([[0, -1.86], [1, -1.82], [1, -1.88], [0, -1.92]] as UV[]).map(([e, v]) => front(side * lerp(0.3, 0.68, e), v)));
  group(V1.armorHi, 1.3, 0.95, (L) => {
    const s = (w: number, v: number) => front(-w, v);
    L.path([s(0.5, -1.62), s(0.56, -1.76), s(0.62, -1.62)]);
    L.path([s(0.67, -1.65), s(0.7, -1.62), s(0.7, -1.76)]);
  }, true);

  // ---------------------------------------------------------------- the wings
  // Four blades each side from the shoulder blades, fanned out (top to bottom) at these angles
  // from level, flat in a plane just behind the back: a dark root, then a long yellow blade with
  // a slanted tip. ponytail: at 60 % of the game's size, so the near side's blades stay mostly in
  // a close three-quarter view.
  const WING = 0.6;
  const blade = (side: number, i: number, e: number, t: number): V3 => {
    const an = ([50, 20, -17, -40][i] * Math.PI) / 180, len = WING * [3.9, 4.4, 4.4, 3.9][i];
    const half = WING * (t < 0.18 ? lerp(0.08, 0.2, t / 0.18) : 0.3);
    // the tip slants: the upper edge runs on further than the lower
    const l = len * Math.min(t, e > 0 ? 1 : 0.86);
    return P(-2.1 - 0.05 * i, -1.45 - 0.1 * i + Math.sin(an) * l + e * half * Math.cos(an), side * (0.45 + Math.cos(an) * l - e * half * Math.sin(an)));
  };
  group(V1.wing, 1.4, 0.8, (L) => {
    for (const side of [1, -1])
      for (let i = 0; i < 4; i++) L.path([...[0.18, 0.4, 1].map((t) => blade(side, i, 1, t)), ...[1, 0.4, 0.18].map((t) => blade(side, i, -1, t))], true);
  }, true);
  group(V1.steel, 1.1, 0.7, (L) => {
    for (const side of [1, -1]) for (let i = 0; i < 4; i++) L.path([blade(side, i, 1, 0), blade(side, i, 1, 0.18), blade(side, i, -1, 0.18), blade(side, i, -1, 0)], true);
  });

  const top = oy + 0.26 * W, bottom = oy - 2.5 * W;
  return {
    groups, face, faceX, centerY: (top + bottom) / 2, halfWidth: 0.9 * W, halfHeight: (top - bottom) / 2,
    // turned towards the camera, to show the lens
    turn: 0.95,
    mouth: V1.glow,
    // the chest and the far wing reach well behind the head
    fogDepth: 3.5 * W,
    live: (s) => {
      // behind the head, the lens is hidden: fade it out
      const c = lens(0, 0);
      const to: V3 = [s.cam[0] - c[0], s.cam[1] - c[1], s.cam[2] - c[2]];
      const facing = smooth(0, 0.35, (n[0] * to[0] + n[1] * to[1]) / (Math.hypot(...to) || 1));
      const lit = smooth(0.01, 0.12, s.level);
      const out: CostumeGroup[] = [];
      if (facing > 0) {
        // a shutter for the lids; the iris follows the gaze
        const open = Math.max(0.06, 1 - s.lid);
        const r = 0.2 * (1 + 0.06 * lit);
        const fill: Float32Array[] = [];
        for (let b = -0.92 * r; b < r; b += 0.09 * r) {
          const half = r * Math.sqrt(1 - (b / r) ** 2);
          fill.push(new Float32Array([...lens(-half, b * open, 0.05), ...lens(half, b * open, 0.05)]));
        }
        const gx = Math.max(-1, Math.min(1, s.yaw / 0.5)) * 0.05, gy = Math.max(-1, Math.min(1, s.pitch / 0.4)) * 0.05;
        const flat = (pts: V3[]) => new Float32Array(pts.flat());
        out.push(
          { lines: [flat(range(32).map((t) => lens(r * Math.cos(t * TAU), r * Math.sin(t * TAU) * open, 0.05)))], color: V1.lens, width: 1.8, alpha: facing, hot: true },
          { lines: fill, color: V1.lens, width: 1.2, alpha: (0.45 + 0.4 * lit) * facing },
          { lines: [flat(circle(0.08, gx, gy * open, 0.06, 20)), flat(circle(0.035, gx, gy * open, 0.065, 12))], color: V1.glow, width: 1.4, alpha: (open > 0.3 ? 1 : 0) * facing },
          { lines: [flat(circle(0.27 + 0.05 * lit, 0, 0, 0.05, 40))], color: V1.glow, width: 2, alpha: lit * facing, hot: true },
        );
      }
      out.push({ lines: slits.map((p) => new Float32Array([...p, p[0]].flat())), color: V1.lens, width: 1.6, alpha: 0.45 + 0.55 * lit, hot: true });
      return out;
    },
  };
}
