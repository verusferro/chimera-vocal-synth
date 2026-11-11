/**
 * A costume for the 3D head (see costume.ts): Niko, from OneShot (`look: "niko"`). A smooth
 * round face with large cat's eyes, the bobbed hair with its fringe and the three tufts at each
 * side, the wide hat whose crown ends in two ears, and the bulky scarf with its ends down the
 * back. The face's surface passes through the lips so the mouth sits on it.
 *
 * Proportions follow pungsun3497's Niko model (measured, as ratios of the head's size) and the
 * game's art; the ears are a little taller than the model's, as the art draws them.
 */

import { type Costume, type CostumeGroup, type HeadFrame, lerp, Pen, range, smooth, TAU, type V3 } from "./costume.ts";

/** Niko's colours, bright enough to read as beams on black */
export const NIKO = {
  hat: "#d2664a",
  hatDim: "#9e5040",
  earInside: "#ff9db0",
  hair: "#6f6ff0",
  scarf: "#4a86ff",
  eye: "#ffe94d",
  pupil: "#ff7a3a",
  skin: "#d9a48a",
} as const;

/** an eye on the face: its centre, and the plane it lies in (u across, v up) */
interface NikoEye {
  c: V3;
  u: V3;
  v: V3;
  r: number;
}

/** superellipse exponent of the head's rounding (2 = an ellipsoid; more = fuller cheeks) */
const E = 2.5;
const sgnPow = (c: number, p: number) => Math.sign(c) * Math.pow(Math.abs(c), p);

interface Ball {
  cx: number;
  cy: number;
  rx: number;
  ry: number;
  rz: number;
}
/** a ball's surface at height y, th round it (0 = front, π/2 = the right side) */
function on(b: Ball, y: number, th: number): V3 {
  const d = Math.min(1, Math.abs((y - b.cy) / b.ry));
  const g = Math.pow(1 - Math.pow(d, E), 1 / E);
  return [b.cx + b.rx * g * sgnPow(Math.cos(th), 2 / E), y, b.rz * g * sgnPow(Math.sin(th), 2 / E)];
}

export function nikoHead(h: HeadFrame): Costume {
  const k = h.k;
  const groups: CostumeGroup[] = [];
  const face_: CostumeGroup[] = [];
  const group = (color: string, width: number, alpha: number, fill: (L: Pen) => void, hot = false, into = groups) => {
    const L = new Pen();
    fill(L);
    into.push({ lines: L.lines, color, width, alpha, hot });
  };

  // ---------------------------------------------------------------- the face
  // A smooth ball from the chin to the top of the head, as wide as ours, its front through the lips.
  const chinY = h.By(4.4), topY = h.By(23);
  const face: Ball = { cx: -0.6 * k, cy: (chinY + topY) / 2, rx: 1, ry: (topY - chinY) / 2, rz: 7.6 * k };
  face.rx = (h.lip.x - 0.3 * k - face.cx) / (on({ ...face, rx: 1, cx: 0 }, h.lip.y, 0)[0] || 1);
  const H = topY - chinY, W = 2 * face.rz;
  const faceX = (y: number, z: number): number => {
    const g = Math.pow(1 - Math.pow(Math.min(1, Math.abs((y - face.cy) / face.ry)), E), 1 / E);
    return face.cx + face.rx * g * Math.pow(1 - Math.pow(Math.min(1, Math.abs(z) / (face.rz * g || 1)), E), 1 / E);
  };
  // the hat's brim hides the forehead: the face is drawn up to there
  const browY = h.By(16.6);
  group(NIKO.skin, 1.5, 0.95, (L) => {
    // the jaw's line round to each side (no line down the middle: it would cross the mouth)
    for (const s of [1, -1]) L.path(range(24).map((t) => on(face, lerp(chinY + 0.02 * H, h.By(12), t * t), s * lerp(0.2, 1.5, Math.sqrt(t)))));
  }, true, face_);
  group(NIKO.skin, 0.9, 0.55, (L) => {
    for (let y = chinY + 0.1 * H; y < browY; y += 0.085 * H) L.path(range(40).map((t) => on(face, y, lerp(-1.75, 1.75, t))));
    for (const th of [-1.2, -0.6, 0.6, 1.2]) L.path(range(30).map((t) => on(face, lerp(chinY + 0.03 * H, browY, t), th)));
  }, false, face_);

  // the eyes: large, low on the face, wide apart
  const eyeY = chinY + 0.42 * H, eyeR = 0.145 * W;
  const eyes: NikoEye[] = [1, -1].map((s) => {
    const th = s * 0.6;
    const p = on(face, eyeY, th);
    // facing between straight ahead and straight out of the face
    const n: V3 = [Math.cos(0.55 * th), 0.04, Math.sin(0.55 * th)];
    const nl = Math.hypot(...n);
    const u: V3 = [-n[2] / nl, 0, n[0] / nl];
    return { c: [p[0] + 0.25 * k * n[0], p[1], p[2] + 0.25 * k * n[2]], u, v: [0, 1, 0], r: eyeR };
  });

  // ---------------------------------------------------------------- the hat
  // The crown's base is a ring well clear of the head; the brim droops from it to a wide edge,
  // tipped back (front up). The crown's front and back slope in to a ridge from side to side,
  // and the ridge's two ends rise into the ears.
  const hatX = face.cx + 1.3 * k;
  const baseY = (x: number) => h.By(17.2) + 0.08 * (x - face.cx);
  const edgeY = (x: number) => h.By(14.6) + 0.18 * (x - face.cx);
  const brim = (th: number, u: number): V3 => {
    const bx = hatX + 10.2 * k * Math.cos(th), ex = face.cx + 0.2 * k + 15.2 * k * Math.cos(th);
    return [lerp(bx, ex, u), lerp(baseY(bx), edgeY(ex), Math.pow(u, 1.4)), lerp(10.4, 16.6, u) * k * Math.sin(th)];
  };
  const RIDGE = h.By(24.4) - h.By(17.2), EAR = 5.2;
  /** how far an ear stands above the ridge, by distance from the middle (template cm) */
  const earRise = (a: number) => (a < 2.6 ? 0 : a < 7.6 ? EAR * Math.pow((a - 2.6) / 5, 1.25) : Math.max(0, EAR - (EAR - 0.8) * ((a - 7.6) / 1.8)));
  /** the crown: s across it (−1 left … 1 right), f = 1 front or −1 back, t from its base (0) to the ridge (1) */
  const crown = (s: number, f: number, t: number): V3 => {
    const q = Math.pow(1 - Math.pow(Math.abs(s), 2.6), 1 / 2.6);
    const az = (10.4 - 1.0 * t) * k;
    const x0 = hatX + f * 10.2 * k * q;
    // steep at the base, then sloping in to the ridge: a rounded crown
    const x = hatX + f * (10.2 * Math.pow(1 - Math.pow(t, 1.5), 0.9) + 0.45) * k * q;
    return [x, baseY(x0) + t * RIDGE + earRise(Math.abs(s * az) / k) * k * Math.pow(t, 2.5), s * az];
  };
  const across = range(48).map((t) => 2 * t - 1);
  const crownRing = (t: number): V3[] => [...across.map((s) => crown(s, 1, t)), ...across.slice(1, -1).reverse().map((s) => crown(s, -1, t))];
  const round = range(64).map((t) => t * TAU);
  group(NIKO.hat, 1.7, 1, (L) => {
    L.path(round.map((th) => brim(th, 1)));
    L.path(crownRing(0), true);
    // the ridge and the ears: the hat's outline from the front
    L.path(across.map((s) => crown(s, 1, 1)));
  }, true);
  group(NIKO.hatDim, 1.0, 0.75, (L) => {
    L.path(round.map((th) => brim(th, 0.5)));
    for (let i = 0; i < 16; i++) L.path(range(6).map((u) => brim((i / 16) * TAU, u)));
    for (const t of [0.4, 0.75, 0.93]) L.path(crownRing(t), true);
    for (const s of [-0.62, 0, 0.62]) for (const f of [1, -1]) L.path(range(14).map((t) => crown(s, f, t)));
  });
  group(NIKO.earInside, 1.2, 0.9, (L) => {
    for (const side of [1, -1]) L.path([crown(side * 0.5, 1, 0.9), crown(side * 0.8, 1, 0.985), crown(side * 0.95, 1, 0.9)], true);
  });

  // ---------------------------------------------------------------- the hair
  // A bob to the chin over a ball a little larger than the face's; the hat hides its top, so the
  // strands start at the crown's base. A fringe down to the eyes with a lock between them, a
  // longer lock framing each cheek.
  const hair: Ball = { cx: face.cx - 0.5 * k, cy: face.cy + 0.03 * H, rx: face.rx + 1.1 * k, ry: 0.68 * H, rz: face.rz + 1.3 * k };
  const hemY = chinY + 0.04 * H;
  /** where a strand at th ends: the fringe, the cheek locks, the bob's hem */
  const strandEnd = (th: number, i: number): number => {
    const a = Math.abs(th), zig = (i % 2 ? 0.022 : -0.022) * H;
    if (a < 0.72) return eyeY + 1.02 * eyeR - 0.95 * eyeR * Math.exp(-((th / 0.13) ** 2)) + 0.6 * zig + 0.35 * eyeR * (a / 0.72) ** 2;
    if (a < 1.2) return chinY + 0.17 * H + zig;
    return hemY + zig;
  };
  const N_STRANDS = 36;
  const strands = Array.from({ length: N_STRANDS }, (_, i) => {
    const th = ((i + 0.5) / N_STRANDS) * TAU - Math.PI;
    const y0 = baseY(on(hair, h.By(17.2), th)[0]) + 0.4 * k;
    return { th, pts: range(12).map((t) => on(hair, lerp(y0, strandEnd(th, i), t), th)) };
  });
  group(NIKO.hair, 1.0, 0.45, (L) => {
    for (const s of strands) L.path(s.pts);
    for (const y of [h.By(13.5), h.By(9.5)]) for (const s of [1, -1]) L.path(range(30).map((t) => on(hair, y, s * lerp(1.22, Math.PI, t))));
  });
  group(NIKO.hair, 1.6, 1, (L) => {
    // the hair's edge: the tips of the strands, joined
    L.path(strands.map((s) => s.pts[s.pts.length - 1]), true);
    // the three tufts at each side, at eye height: leaves fanned up, out and down
    const tuftY = chinY + 0.47 * H;
    for (const side of [1, -1]) {
      const root = on(hair, tuftY, side * 1.62);
      for (const an of [0.52, 0, -0.52]) {
        const len = 0.33 * W, wid = 0.035 * W;
        const dir: V3 = [-0.12, Math.sin(an), side * Math.cos(an)], nrm: V3 = [0, Math.cos(an), -side * Math.sin(an)];
        const leaf = (e: number): V3[] =>
          range(10).map((t) => {
            const w = e * wid * Math.sin(Math.PI * Math.pow(t, 0.75));
            return [root[0] + dir[0] * len * t, root[1] + 0.25 * len * Math.sin(an) + dir[1] * len * t + nrm[1] * w, root[2] + dir[2] * len * t + nrm[2] * w];
          });
        L.path([...leaf(1), ...leaf(-1).reverse()], true);
      }
    }
  }, true);

  // ---------------------------------------------------------------- the scarf
  // Three soft loops round the neck, up to the chin, and its two ends hanging down the back.
  const neckX = face.cx - 0.2 * k;
  const LOOPS: { Y: number; s: number; a: number; b: number }[] = [
    { Y: -2.5, s: 1.08, a: 0.13, b: 0.1 },
    { Y: 1.1, s: 0.94, a: -0.1, b: -0.08 },
  ];
  const TUBE = 2.3 * k;
  const loop = (l: (typeof LOOPS)[number], i: number, ph: number, ps: number): V3 => {
    const r = TUBE * (1 + 0.12 * Math.sin(4 * ph + 2 * i));
    const x = neckX + (6.0 * k * l.s + r * Math.cos(ps)) * Math.cos(ph), z = (7.7 * k * l.s + r * Math.cos(ps)) * Math.sin(ph);
    return [x, h.By(l.Y) + r * Math.sin(ps) + l.a * (x - neckX) + l.b * z, z];
  };
  group(NIKO.scarf, 1.5, 1, (L) => {
    LOOPS.forEach((l, i) => L.path(round.map((ph) => loop(l, i, ph, 0))));
  }, true);
  group(NIKO.scarf, 1.0, 0.5, (L) => {
    LOOPS.forEach((l, i) => {
      for (const ps of [0.5, 1, 1.5].map((v) => v * Math.PI)) L.path(round.map((ph) => loop(l, i, ph, ps)));
      for (let j = 0; j < 16; j++) L.path(range(12).map((t) => loop(l, i, (j / 16) * TAU, t * TAU)));
    });
  });
  const TAIL = 20 * k;
  /** a scarf end: t down its length, e across it (−1 … 1) */
  const tail = (side: number, len: number, t: number, e: number): V3 => {
    const sway = Math.sin(TAU * (0.8 * t + 0.2 * side));
    return [neckX - 6.6 * k - 0.3 * len * t - 0.9 * k * sway * t, h.By(-3.3) - 0.95 * len * t, side * 3.3 * k * (1 + 0.5 * t) + e * 2.1 * k * (1 + 0.2 * t) + 0.8 * k * sway * t];
  };
  const ENDS: [number, number][] = [[1, TAIL], [-1, 0.82 * TAIL]];
  group(NIKO.scarf, 1.5, 1, (L) => {
    for (const [side, len] of ENDS) {
      for (const e of [1, -1]) L.path(range(24).map((t) => tail(side, len, t, e)));
      L.path([tail(side, len, 1, 1), tail(side, len, 1, -1)]);
      // the fringe
      for (const e of [-0.8, -0.4, 0, 0.4, 0.8]) {
        const p = tail(side, len, 1, e);
        L.path([p, [p[0] - 0.5 * k, p[1] - 2.2 * k, p[2] + 0.2 * k * e]]);
      }
    }
  }, true);
  group(NIKO.scarf, 1.0, 0.5, (L) => {
    for (const [side, len] of ENDS) {
      L.path(range(24).map((t) => tail(side, len, t, 0)));
      for (let i = 1; i < 7; i++) L.path([tail(side, len, i / 7, 1), tail(side, len, i / 7, -1)]);
    }
  });

  const top = h.By(24.4) + EAR * k, bottom = h.By(-3.3) - 0.55 * TAIL;
  return {
    groups, face: face_, faceX, centerY: (top + bottom) / 2, halfWidth: 16.6 * k, halfHeight: (top - bottom) / 2,
    // turned well towards the camera, to show both eyes
    turn: 1.0,
    live: (s) =>
      eyes.flatMap((eye) => {
        // an eye turned away from the camera is behind the face: fade it out
        const n: V3 = [eye.u[2], 0, -eye.u[0]];
        const to: V3 = [s.cam[0] - eye.c[0], s.cam[1] - eye.c[1], s.cam[2] - eye.c[2]];
        const facing = smooth(0.1, 0.4, (n[0] * to[0] + n[2] * to[2]) / (Math.hypot(...to) || 1));
        if (facing <= 0) return [];
        return nikoEye(eye, s.yaw, s.pitch, s.lid, s.wide).map((g) => ({ ...g, alpha: g.alpha * facing }));
      }),
  };
}

/**
 * One eye this frame: where it looks (yaw towards the eye's own right, pitch up; radians) and
 * how far the lid is shut (0 open … 1 shut). A yellow disc, filled with strokes that leave the
 * tall pupil dark, and a glint in the pupil; the lid closes it to a line.
 */
function nikoEye(e: NikoEye, yaw: number, pitch: number, lid: number, wide: number): CostumeGroup[] {
  const open = Math.max(0.05, 1 - lid) * (1 + 0.1 * wide);
  const at = (a: number, b: number): V3 => [e.c[0] + e.u[0] * a + e.v[0] * b, e.c[1] + e.u[1] * a + e.v[1] * b, e.c[2] + e.u[2] * a + e.v[2] * b];
  const ring = (ca: number, cb: number, ra: number, rb: number, n = 28): Float32Array => {
    const o = new Float32Array((n + 1) * 3);
    for (let i = 0; i <= n; i++) o.set(at(ca + ra * Math.cos((i / n) * TAU), (cb + rb * Math.sin((i / n) * TAU)) * open), 3 * i);
    return o;
  };
  const r = e.r;
  const gx = Math.max(-1, Math.min(1, yaw / 0.5)) * 0.22 * r, gy = Math.max(-1, Math.min(1, pitch / 0.4)) * 0.2 * r;
  // the lash: a heavier arc over the top
  const lash = new Float32Array(17 * 3);
  for (let i = 0; i <= 16; i++) {
    const an = Math.PI * (0.08 + (0.84 * i) / 16);
    lash.set(at(1.1 * r * Math.cos(an), (1.12 * r * Math.sin(an) + 0.04 * r) * open), 3 * i);
  }
  const seen = open > 0.25 ? 1 : 0;
  const ra = 0.93 * r, rb = 1.04 * r, pa = 0.3 * r, pb = 0.58 * r;
  // the fill: strokes across the disc, broken where the pupil is
  const fill: Float32Array[] = [];
  const stroke = (a0: number, a1: number, b: number) => a1 - a0 > 0.04 * r && fill.push(new Float32Array([...at(a0, b * open), ...at(a1, b * open)]));
  for (let b = -0.91 * rb; b < rb; b += 0.13 * rb) {
    const half = ra * Math.sqrt(1 - (b / rb) ** 2), db = (b - gy) / pb;
    if (Math.abs(db) < 1) {
      const gap = pa * Math.sqrt(1 - db * db);
      stroke(-half, gx - gap, b);
      stroke(gx + gap, half, b);
    } else stroke(-half, half, b);
  }
  return [
    { lines: [ring(0, 0, ra, rb)], color: NIKO.eye, width: 1.8, alpha: 1, hot: true },
    { lines: fill, color: NIKO.eye, width: 1.3, alpha: 0.85 * seen },
    { lines: [ring(gx - 0.1 * r, gy + 0.3 * r, 0.11 * r, 0.11 * r, 10)], color: "#ffffff", width: 1.3, alpha: seen },
    { lines: [lash], color: NIKO.hatDim, width: 1.6, alpha: 0.8 },
  ];
}
