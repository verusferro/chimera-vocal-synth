/**
 * A costume over the 3D head (a show's `voices[i].look`): a character's head and body in place of
 * our skull, face and neck (anatomy3d.ts leaves those out), built once per body as wire meshes in
 * the head's frame (body cm: x forward, y up, z to the head's right; the glottis at the origin).
 * The vocal tract inside is the engine's, unchanged, and the mouth's opening is drawn on the
 * costume's face.
 */

export type V3 = [number, number, number];

export interface CostumeGroup {
  lines: Float32Array[];
  color: string;
  width: number;
  alpha: number;
  hot?: boolean;
}

/** what a costume needs of the head it replaces (body cm) */
export interface HeadFrame {
  /** the body's scale */
  k: number;
  /** template height → body y */
  By(Y: number): number;
  /** the lips' edge at rest (jaw closed) */
  lip: { x: number; y: number };
}

/** the moment's state for a costume's moving parts */
export interface LiveState {
  /** the camera, in the head's frame */
  cam: V3;
  /** where the eyes look (yaw towards the face's right, pitch up; radians) */
  yaw: number;
  pitch: number;
  /** lids shut (0 open … 1 shut), and eyes widened (0 … 1) */
  lid: number;
  wide: number;
  /** the voice's output level (RMS) */
  level: number;
}

export interface Costume {
  /** static lines */
  groups: CostumeGroup[];
  /** the face's own lines: drawn each frame, with the open mouth cut out of them */
  face: CostumeGroup[];
  /** x of the face's surface at body y and z: the mouth's opening is drawn on it */
  faceX(y: number, z: number): number;
  /** the middle of the whole figure, and its half-width and half-height, for framing */
  centerY: number;
  halfWidth: number;
  halfHeight: number;
  /** the home view's turn from the side view towards the front (radians) */
  turn: number;
  /** the mouth opening's colour (default: the lips' pink) */
  mouth?: string;
  /** how far past the head's centre lines still show before the fog hides them (default 30 cm
   *  at a male's size: a head's depth) */
  fogDepth?: number;
  /** the moving parts this frame (eyes, lights) */
  live(s: LiveState): CostumeGroup[];
}

export class Pen {
  readonly lines: Float32Array[] = [];
  path(pts: V3[], close = false): void {
    if (pts.length < 2) return;
    const a = new Float32Array((pts.length + (close ? 1 : 0)) * 3);
    pts.forEach((p, i) => a.set(p, 3 * i));
    if (close) a.set(pts[0], 3 * pts.length);
    this.lines.push(a);
  }
}

export const TAU = Math.PI * 2;
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export const range = (n: number) => Array.from({ length: n + 1 }, (_, i) => i / n);
export const smooth = (a: number, b: number, x: number): number => {
  const t = Math.max(0, Math.min(1, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};
