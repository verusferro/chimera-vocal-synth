/**
 * The duet page (`?show=<id>`): a pre-rendered song with two (or more) voices, each on its own 3D
 * head, side by side, moving exactly as the engine did when it sang. Nothing is synthesized here:
 * the page plays the mixed track and replays each voice's recorded telemetry at the playhead.
 *
 * A show is a folder `public/shows/<id>/` (gitignored: shows are made locally, often of songs that
 * mustn't be published) holding `show.json`, the mix and one `.tele` per voice from
 * `chimera render notes … --tele`. The voices' renders and the mix must share sample 0.
 *
 *   { "title": "…", "audio": "mix.mp3", "bpm": 103, "downbeat": 0,
 *     "voices": [{ "name": "Lower", "tele": "male.tele" }, { "name": "Upper", "tele": "female.tele" }] }
 *
 * Optional: `bpm` and `downbeat` (s, a bar's first beat) nod the heads on the beat; a voice's
 * `melody` (the melody file it was rendered from) writes its words at its mouth, and the show's
 * `spell` ({"owr": "our"}) writes a syllable spelled for the dictionary as it should read;
 * `video` (a silent picture on the mix's clock, e.g. the original's lyric video) plays in a corner.
 */
import { useEffect, useRef, useState } from "react";
import { AnatomyView3D, type HeadFeed } from "./AnatomyView3D.tsx";
import { Screen } from "./Screen.tsx";
import { TeleTrack } from "../../show/tele.ts";
import { Transport } from "../../show/transport.ts";
import { getModel } from "../useModel.ts";
import { VoiceModel } from "../analysis.ts";
import { bodyLabel } from "../body.ts";
import type { ViewFlags } from "../render/anatomy.ts";
import type { Look } from "../render/anatomy3d.ts";
import { mouthWords } from "../mouthWords.ts";
import { V } from "../colors.ts";
import { g2p } from "../speech.ts";
import { lyricsToSyllables } from "../../wasm/engine.ts";
import { sungWords, wordAt, type Melody, type SungWords } from "../../show/words.ts";
import type { OverlayFn } from "./AnatomyView.tsx";

interface ShowFile {
  title: string;
  audio: string;
  video?: string;
  /** the backing track apart from `audio` (then the voices alone), on the same clock: gets a volume slider */
  backing?: string;
  bpm?: number;
  downbeat?: number;
  spell?: Record<string, string>;
  /** `on` (s): when the head is on screen, `[[from, to], …]` (`to` null: to the end); before, after
   * and between, it is off screen, the others sharing the width. Absent: always on.
   * `facing`: 1 looks right, -1 left; absent: the last of several looks left, the others right */
  voices: { name: string; tele: string; melody?: string; look?: Look; on?: [number, number | null][]; facing?: 1 | -1 }[];
}

interface Loaded {
  show: ShowFile;
  voices: { name: string; track: TeleTrack; words: SungWords | null; look?: Look; on: [number, number | null][]; facing: 1 | -1 }[];
}

const isOn = (v: { on: [number, number | null][] }, t: number): boolean => v.on.some(([a, b]) => t >= a && (b === null || t < b));
/** s: a head's growing in or shrinking away (the CSS keyframes' length) */
const MOVE_S = 0.7;
/** a head that went off less than MOVE_S ago: still shrinking away in its place */
const isLeaving = (v: { on: [number, number | null][] }, t: number): boolean => !isOn(v, t) && v.on.some(([, b]) => b !== null && t >= b && t < b + MOVE_S);
/** a head that comes (or goes) during the song: it grows in each time it comes on */
const late = (v: { on: [number, number | null][] }): boolean => v.on.length > 1 || v.on[0][0] > 0 || v.on[0][1] !== null;
/** some head of the row is growing in or shrinking away (each head waits to refit its canvas) */
const isMoving = (vs: { on: [number, number | null][] }[], t: number): boolean =>
  vs.some((v) => v.on.some(([a, b]) => (a > 0 && t >= a && t < a + MOVE_S) || (b !== null && t >= b && t < b + MOVE_S)));
/** s: windows of different heads less than this apart are one section (a dialogue, a shared verse) */
const SECTION_GAP_S = 2;

/** heads that sing in one section stay until its last line, and all go together at its end: each
 * window that ends is stretched to the end of the section it belongs to (windows of any head that
 * overlap or follow within SECTION_GAP_S) */
function together(ons: [number, number | null][][]): [number, number | null][][] {
  const wins = ons.flat().filter((w): w is [number, number] => w[1] !== null).sort((x, y) => x[0] - y[0]);
  const sections: [number, number][] = [];
  for (const [a, b] of wins) {
    const s = sections.at(-1);
    if (s && a <= s[1] + SECTION_GAP_S) s[1] = Math.max(s[1], b);
    else sections.push([a, b]);
  }
  return ons.map((on) => on.map(([a, b]) => [a, b === null ? null : sections.find(([s0, s1]) => a >= s0 && a <= s1)![1]]));
}

/** the heads as the face screen shows them by default, less the measurement labels */
const VIEW: ViewFlags = { pressure: true, particles: true, grid: false, calipers: false };

async function fetchOk(url: string): Promise<Response> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status} ${r.statusText}`);
  return r;
}

const clock = (t: number) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;

export function DuetPage(props: { id: string }) {
  const base = `${import.meta.env.BASE_URL}shows/${props.id}/`;
  // one transport per mount (its context closes on unmount)
  const [transport, setTransport] = useState<Transport | null>(null);
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [, setTick] = useState(0);
  const [backingVol, setBackingVol] = useState(1);
  const [videoOn, setVideoOn] = useState(true);
  // the other shows on this site (shows/index.json: [{id, title}]), for the picker; none = no picker
  const [shows, setShows] = useState<{ id: string; title: string }[]>([]);
  useEffect(() => {
    fetchOk(`${import.meta.env.BASE_URL}shows/index.json`).then((r) => r.json()).then(setShows, () => {});
  }, []);

  useEffect(() => {
    const t = new Transport();
    setTransport(t);
    return () => t.dispose();
  }, []);

  useEffect(() => {
    if (!transport) return;
    let live = true;
    setLoaded(null);
    (async () => {
      const show = (await (await fetchOk(base + "show.json")).json()) as ShowFile;
      if (!show.voices?.length || !show.audio) throw new Error("show.json needs audio and voices");
      const [audio, backing, ...teles] = await Promise.all([fetchOk(base + show.audio).then((r) => r.arrayBuffer()), show.backing ? fetchOk(base + show.backing).then((r) => r.arrayBuffer()) : undefined, ...show.voices.map((v) => fetchOk(base + v.tele).then((r) => r.arrayBuffer()))]);
      // the words: syllables as the CLI splits them (the pronouncing dictionary first, as it does)
      const melodies = await Promise.all(show.voices.map((v) => (v.melody ? fetchOk(base + v.melody).then((r) => r.json() as Promise<Melody>) : null)));
      if (melodies.some(Boolean)) await g2p.load().catch(() => {});
      const words = melodies.map((m) => {
        if (!m) return null;
        try {
          return sungWords(m, lyricsToSyllables(m.lyrics), show.spell);
        } catch (e) {
          console.warn("duet: no words for a voice:", e);
          return null;
        }
      });
      const ons = together(show.voices.map((v) => v.on ?? [[0, null]]));
      const voices = show.voices.map((v, i, all) => ({ name: v.name, track: new TeleTrack(teles[i]), words: words[i], look: v.look, on: ons[i], facing: v.facing ?? (i > 0 && i === all.length - 1 ? -1 : 1) }));
      await transport.load(audio, backing);
      if (live) setLoaded({ show, voices });
    })().catch((e: unknown) => live && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      live = false;
    };
  }, [base, transport]);

  // the readouts follow the transport: at once on a change, and a few times a second while it plays
  useEffect(() => {
    if (!transport) return;
    const off = transport.subscribe(() => setTick((n) => n + 1));
    const id = setInterval(() => transport.isPlaying && setTick((n) => n + 1), 100);
    return () => {
      off();
      clearInterval(id);
    };
  }, [transport]);

  // keys: space plays and pauses, the left and right arrows step 5 s back and on (a focused button
  // or text field keeps its own use of the key; on the sliders these keys go to the song)
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (!transport || !loaded || (e.target as HTMLElement).closest?.("button, select, textarea, input:not([type=range])")) return;
      const step = e.code === "ArrowRight" ? 5 : e.code === "ArrowLeft" ? -5 : 0;
      if (e.code === "Space") {
        if (transport.isPlaying) transport.pause();
        else transport.play();
      } else if (step) transport.seek(transport.state.time + step); // seek clamps to the song
      else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [transport, loaded]);

  if (error)
    return (
      <div className="duet">
        <p className="duet-msg error">This show could not load: {error}</p>
      </div>
    );
  const st = transport?.state ?? { playing: false, time: 0, duration: 0, epoch: 0 };
  const title = loaded?.show.title ?? "Loading…";
  const moving = !!loaded && isMoving(loaded.voices, st.time);
  return (
    <div className="duet">
      <header className="duet-top">
        <span className="wordmark">Chimera</span>
        <span className="duet-title">{title}</span>
        {shows.length > 1 && (
          <select className="duet-pick" aria-label="Cover" value={props.id} onChange={(e) => (location.search = `?show=${encodeURIComponent(e.target.value)}`)}>
            {shows.map((s) => (
              <option key={s.id} value={s.id}>
                {s.title}
              </option>
            ))}
          </select>
        )}
      </header>
      <main className="duet-heads">
        {loaded && transport ? loaded.voices.map((v, i) => <Head key={i} name={v.name} track={v.track} words={v.words} look={v.look} stage={isLeaving(v, st.time) ? " leaving" : !isOn(v, st.time) ? " waiting" : late(v) ? " entering" : ""} moving={moving} show={loaded.show} transport={transport} facing={v.facing} />) : <p className="duet-msg">Loading the song…</p>}
        {loaded?.show.video && transport && videoOn && <CornerVideo src={base + loaded.show.video} transport={transport} />}
      </main>
      <footer className="duet-bar">
        <button className="primary large" disabled={!loaded} onClick={() => (st.playing ? transport?.pause() : transport?.play())}>
          {st.playing ? "Pause" : st.duration > 0 && st.time >= st.duration - 0.05 ? "Again" : "Play"}
        </button>
        <span className="duet-time">
          {clock(st.time)} / {clock(st.duration)}
        </span>
        <input
          type="range"
          aria-label="Position in the song"
          min={0}
          max={st.duration || 1}
          step={0.1}
          value={st.time}
          disabled={!loaded}
          onChange={(e) => transport?.seek(Number(e.target.value))}
          style={{ "--pos": `${st.duration ? (100 * st.time) / st.duration : 0}%` } as React.CSSProperties}
        />
        {loaded?.show.video && (
          <button className="ghost" aria-pressed={videoOn} title={videoOn ? "Hide the video" : "Show the video"} onClick={() => setVideoOn((on) => !on)}>
            {videoOn ? "Hide video" : "Show video"}
          </button>
        )}
        {loaded?.show.backing && (
          <label className="duet-backing">
            Music
            <input
              type="range"
              min={0}
              max={1.25}
              step={0.05}
              value={backingVol}
              onChange={(e) => {
                const v = Number(e.target.value);
                setBackingVol(v);
                transport?.setBackingVolume(v);
              }}
              style={{ "--pos": `${(100 * backingVol) / 1.25}%` } as React.CSSProperties}
            />
          </label>
        )}
      </footer>
    </div>
  );
}

/** the show's video in a corner of the heads, kept at the transport's playhead (the sound is the mix's) */
function CornerVideo(props: { src: string; transport: Transport }) {
  const ref = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    const sync = () => {
      const v = ref.current;
      if (!v) return;
      const t = props.transport.time(), playing = props.transport.isPlaying;
      // playing: a small drift is taken up by playing a little faster or slower; only a big one
      // (a seek, a stall) seeks, since a seek makes the decoder stall again and fall further behind
      const d = t - v.currentTime;
      if (Math.abs(d) > (playing ? 1 : 0.03)) v.currentTime = t;
      v.playbackRate = playing && Math.abs(d) > 0.05 ? 1 + Math.max(-0.1, Math.min(0.1, d / 2)) : 1;
      if (playing && v.paused) void v.play().catch(() => {});
      else if (!playing && !v.paused) v.pause();
    };
    const off = props.transport.subscribe(sync);
    const id = setInterval(sync, 200);
    return () => {
      off();
      clearInterval(id);
    };
  }, [props.transport]);
  return (
    <div className="duet-video">
      <video ref={ref} src={props.src} muted playsInline preload="auto" aria-label="The original video" />
    </div>
  );
}

/** one voice's head; the last of several turns to face the others */
function Head(props: { name: string; track: TeleTrack; words: SungWords | null; look?: Look; stage: "" | " waiting" | " entering" | " leaving"; moving: boolean; show: ShowFile; transport: Transport; facing: 1 | -1 }) {
  const { track, show, transport, words } = props;
  const stageRef = useRef(props.stage);
  stageRef.current = props.stage;
  const movingRef = useRef(props.moving);
  movingRef.current = props.moving;
  const feedRef = useRef<HeadFeed | null>(null);
  // the syllable at the mouth, written on the side the face looks to
  const overlayRef = useRef<OverlayFn | undefined>(undefined);
  if (words && !overlayRef.current) overlayRef.current = mouthWords(() => wordAt(words, transport.time()), V.green, props.facing);
  if (!feedRef.current) {
    const model = getModel(track.body, track.sampleRate);
    const beatStep = (t: number) => {
      if (!show.bpm) return -1;
      const s = Math.floor(((t - (show.downbeat ?? 0)) * show.bpm * 4) / 60);
      return s < 0 ? -1 : s % 16;
    };
    feedRef.current = {
      model,
      view: VIEW,
      maxDpr: 1.5,
      facing: props.facing,
      look: props.look,
      hidden: () => stageRef.current === " waiting",
      holdFit: () => movingRef.current,
      frame: () => {
        const t = transport.time();
        const i = track.indexAt(t);
        const msg = track.message(i, beatStep(t));
        // paused: the head keeps its shape, the voice and the face come to rest
        if (!transport.isPlaying) return { tele: null, artic: VoiceModel.articFromArray(msg.t.artic), epoch: transport.epoch };
        return { tele: msg, artic: VoiceModel.articFromArray(msg.t.artic), epoch: transport.epoch };
      },
    };
  }
  return (
    <Screen className={"duet-head" + props.stage} focus title={props.name} sub={bodyLabel(track.body)} label={`${props.name} voice, ${bodyLabel(track.body)}, in 3D`}>
      <AnatomyView3D feed={feedRef.current} readouts={false} overlay={overlayRef.current} />
    </Screen>
  );
}
