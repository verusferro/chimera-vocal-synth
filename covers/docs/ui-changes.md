# UI and CLI changes

This fork changes upstream CHIMERA in a few places. All changes serve the duet show page
(`/?show=<id>`). The rest of the app is as upstream.

To list the changes yourself, add upstream as a remote and diff against it:

```sh
git remote add upstream https://github.com/jamesondh/chimera-vocal-synth
git fetch upstream
git diff upstream/main --stat -- src crates
```

| Area | File | What changed |
|---|---|---|
| Backing track | `src/show/transport.ts` | A second audio track on the same clock, with its own volume |
| Duet page | `src/ui/components/DuetPage.tsx` | Corner video, Music slider, cover picker, late-entering heads, `look` |
| 3D head | `src/ui/components/AnatomyView3D.tsx` | `look` in the feed, redraw after a resize |
| 3D renderer | `src/ui/render/anatomy3d.ts` | Costume hooks |
| Costumes (new) | `src/ui/render/costume.ts`, `niko.ts`, `v1.ts` | Character heads, see [wireframe-heads.md](wireframe-heads.md) |
| Styles | `src/ui/styles.css` | Video, entrance animation, backing slider |
| CLI | `crates/chimera-cli/src/render.rs` | `--syllables` option for `render notes` |
| Ignore list | `.gitignore` | `covers/work`, `covers/vendor`, `__pycache__/` |

Upstream already ignores `public/shows/`. Shows are made locally, often from songs you have no
right to publish, so they never go into git.

## Backing track in the transport

A show can have two audio files: `audio` (the voices) and `backing` (the instrumental).
`Transport.load(data, backing?)` decodes both. `play()` starts both sources at the same
`AudioContext` time and the same offset. So they stay in sync for seek, pause and resume.

The backing track goes through its own gain node. `Transport.setBackingVolume(v)` sets it
(1 = as mixed). The page shows a "Music" slider (0 to 1.25) in the footer when the show has a
backing file. The idea: a viewer can turn down the instrumental to hear the synthetic voices.

`audio` also sets the show's length. When there is a backing file, `audio` holds the voices only,
padded with silence to the song's length. `build_show.sh` and `build_ab.py` make it that way.

## Cover picker

If the site has `shows/index.json` (`[{"id": "grinch", "title": "You're a Mean One, Mr. Grinch"}, ...]`)
with two or more entries, the top right of the page shows a list of them. Picking one opens
`?show=<id>`. Write the file by hand next to the show folders; it is not built.

## Duet page

All of this is in `DuetPage.tsx`. The file header holds the show format (see the next section).

- **Corner video.** If `video` is set, a muted `<video>` plays in the lower left corner over the
  first head. A small component (`CornerVideo`) keeps it on the transport's playhead. When playing,
  it takes up a drift of more than 0.05 s by playing up to 10% faster or slower, and seeks only
  if the picture is more than 1 s off (a seek stalls the decoder, which then falls behind again:
  with a 0.2 s limit a busy page can seek over and over). When paused, it seeks at
  0.03 s. The video has no sound: the sound is the mix. A **Hide
  video** button in the bottom bar takes it off and puts it back.
- **Heads that come and go (`on`).** A voice with `on: [[179, null]]` stays off screen until
  second 179 and then stays (`null`: to the end). `on: [[80, 86.5], [156, 162]]` is on screen only
  in those windows. Each time it comes on it grows in from nothing where it stands, fading in,
  while the heads already there narrow to make room; when it goes it is the same, backwards: it
  fades and narrows to nothing while the others widen into its room (0.7 s each way; the row is a
  flexbox and the CSS animates the head's `flex-grow`, so nothing passes over another head). Heads that sing in one section (their windows overlap or follow within 2 s,
  `together()` in `DuetPage.tsx`) stay until the section's last line and all go together at its
  end: the Stubborn voice stays on while the Broken voice answers, and Ragatha waits for Pomni in
  the intro of *ARTIST BLOCK*. The CSS classes `.waiting`, `.entering` and `.leaving` do
  this. A waiting head is drawn off screen at its final size for its first 2 s (it turns to its
  pose there), then not drawn at all until it comes on (`HeadFeed.hidden`): seven heads with six
  waiting cost about one. Without `on`, a head is on screen the whole song. We used
  it for a surprise (Niko joins late in *Switch Off*) and for singers who only have a few lines
  (the three Voices in *Won't Be Slain Here*, the six guests in *ARTIST BLOCK*: 0.3 s before
  their line to 0.3 s after, breaks under 4 s joined).
- **Keys.** Space plays and pauses; the left and right arrows step 5 s back and on. A focused
  button or text field keeps the key for itself; on a slider the keys go to the song.
- **Look.** `voices[i].look` is passed down to the 3D view as `HeadFeed.look`. Allowed values are
  `"niko"` and `"v1"`. Without `look`, the head is CHIMERA's own skull and face.
- **Redraw rate.** The clock text and slider refresh every 100 ms (was 250 ms).
- **Resizing a head (`AnatomyView3D`).** While a head grows or shrinks its pane changes size every
  frame. Refitting the canvas, the GL buffers and the framing every frame lagged the page, so it
  refits at most every 120 ms (and once after the last change); in between the picture is only
  scaled to the pane with `object-fit: cover`, keeping its shape.

## show.json

A show is a folder `public/shows/<id>/`. The page fetches `show.json` first, then everything it
names, relative to the folder.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `title` | string | yes | Shown in the page header |
| `audio` | string | yes | The mix (or the voices only, if `backing` is set). Sets the length |
| `backing` | string | no | The instrumental, on the same clock. Adds the volume slider |
| `video` | string | no | A silent picture on the same clock, drawn in the corner |
| `bpm` | number | no | Tempo. With `downbeat`, the heads nod on the beat |
| `downbeat` | number | no | Time (s) of a bar's first beat |
| `spell` | object | no | Respells a syllable at the mouth: `{"owr": "our"}` |
| `voices` | array | yes | One entry per head, left to right. At least one |

Each voice:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `name` | string | yes | Label above the head |
| `tele` | string | yes | The `.tele` file from `chimera render notes ... --tele` |
| `melody` | string | no | The melody JSON the voice was rendered from. Writes the sung syllables at the mouth |
| `look` | `"niko"` or `"v1"` | no | A costume over the head |
| `on` | `[[from, to or null], ...]` | no | When the head is on screen (s). Absent: the whole song |
| `facing` | `1` or `-1` | no | Which way the head looks: right or left |

Without `facing`, the last voice (if there is more than one) looks to the left and the others
look to the right. In *ARTIST BLOCK* every guest has `facing: -1`: they look left, towards Caine.

The heads on screen stand side by side in one row (a flexbox: each on-screen head takes an equal
share). The corner `<video>` sits in a box of its own (`.duet-video`): a browser extension (a
video speed controller) puts its controls next to the video, and next to it in the heads' row
they took a head's place and broke the row.

The voices' renders and the mix must start at sample 0. The page only plays the mix and replays
each `.tele` at the playhead. It does not synthesize anything.

A melody file is `{"bpm", "t0"?, "lyrics", "notes": [[midi, beats], ...]}`. A `midi` of 0 or less
is a rest. See [song-from-youtube.md](song-from-youtube.md) for how we make them.

Example (this is the *Switch Off* show; file names are ours):

```json
{
  "title": "Switch Off The Game (Musiclide) - CHIMERA cover",
  "audio": "mix.mp3?v=59ffb0a1",
  "backing": "backing.mp3?v=852b3a3e",
  "video": "video.mp4?v=8c26c24c",
  "bpm": 96,
  "downbeat": 0,
  "voices": [
    { "name": "World Machine", "tele": "lead.tele?v=bc77f959", "melody": "lead.json?v=caaf05bb" },
    { "name": "Niko", "tele": "second.tele?v=51afbc0b", "melody": "second.json?v=18be3cb1", "look": "niko", "on": [[179, null]] }
  ]
}
```

### Hashed `?v=` URLs

Every file name in `show.json` ends with `?v=<8 hex digits>`. This is the first 8 digits of the
file's MD5. The page appends the string to the URL as written, and the file server ignores it.

Why: when you rebuild a show and keep the file names, a CDN or browser can keep serving the old
`mix.mp3` under the new `.tele` files. The mouths and the sound then disagree. A new hash gives a
new URL, so nothing stale is used. Cloudflare, for example, keeps `.mp3` and `.mp4` files for
hours.

The build scripts write the hashes for you:

```sh
md5sum public/shows/<id>/mix.mp3 | cut -c1-8      # what build_show.sh does for each file
```

`show.json` itself is fetched without a hash. If you host the show, do not let it be cached for
long. See [record-and-host.md](record-and-host.md).

## 3D head

### `AnatomyView3D.tsx`

- `HeadFeed.look` is copied to the renderer (`r.look`) before the first frame.
- The `ResizeObserver` now draws a frame right after it resizes the canvas. Resizing a canvas
  blanks it, and the observer runs after the frame's own draw. Without this fix, a pane whose size
  is being animated (the entrance) shows nothing until the animation ends. To allow this, the draw
  code moved from the `loop` callback to a `frame(now)` function that `loop` calls.

### `anatomy3d.ts`: costume hooks

A costume is a character's head and body in wire meshes (see [wireframe-heads.md](wireframe-heads.md)
for how they are made). The renderer keeps the vocal tract (tongue, velum, airway, particles) from
CHIMERA and replaces the outside of the head. The hooks are:

- `Look` and `COSTUMES`: `{ niko: nikoHead, v1: v1Head }`. Add a new costume here.
- `Anatomy3D.look`: set before the first frame. `buildRest(model, look)` leaves out the skull,
  brain, ears, nose and neck bones for a costume, and adds the costume's static lines. It also
  moves the camera target to `costume.centerY` and drops the template's skin shell.
- Framing: for a costume the camera distance also fits `halfWidth` and `halfHeight` (a hat or a
  scarf reaches past the head). `costume.turn` replaces the default three-quarter angle of 0.62
  rad, so the face turns to the viewer.
- Fog: the far plane is `dist + (costume.fogDepth ?? 30 * k)`. A costume with a deep body can
  raise `fogDepth` so lines behind the head do not fade out.
- `costumeFace(costume, mouth, k)`: draws the face mesh every frame, but cuts out the lines that
  lie inside the open mouth. `mouth` is the opening's outline from `lips()`. The mouth itself is
  drawn on the costume's face surface with `costume.faceX(y, z)` (plus a small offset), in
  `costume.mouth` colour.
- `costumeLive(costume, tele, dt)`: draws the moving parts. It passes the camera position in the
  head frame, the gaze (`yaw`, `pitch`), the lids (`lid`, 0 open to 1 shut), the eye widening
  (`wide`), and the voice's output level `level` (`tele.t.outRms`). The costume returns line
  groups: eyes that look about and blink, or lights that pulse with the voice. The costume's eyes
  replace CHIMERA's own (`eyes()`), so the blink and gaze code is shared.
- With a costume, the lips' pink skin rows, the lip profile and the chin line are not drawn. The
  skull, brain and skin-profile lines are skipped too. Only the engine's tract remains inside.

## styles.css

New rules only (all near the `.duet-*` block):

- `.duet-heads`: `position: relative; overflow: hidden`, so the corner video and the off-screen
  head stay inside.
- `.duet-video`: absolute, 10 px from the lower left, `clamp(200px, 24vw, 400px)` wide, 16:9,
  `pointer-events: none`.
- `.duet-head.waiting`, `.duet-head.entering`, `.duet-heads.split`, and the keyframes
  `duet-slide-in` and `duet-make-room`: the entrance (0.7 s). With `prefers-reduced-motion` there
  is no animation.
- `.duet-backing`: the footer's backing slider (110 px wide).

## CLI: `--syllables`

`chimera render notes` has a new option. It writes each sounding note with its syllable:

```sh
./target/release/chimera render notes in.json out male \
  --tele out.tele --syllables out.syl.json
```

Run it from the repo root: the CLI reads its dictionary from there. The output is a JSON array.
Times are in seconds, on the render's clock:

```json
[
  {"t": 0.272, "dur": 0.25,  "midi": 69.0,
   "syl": {"text": "Ga", "onset": [{"ipa": "g", "stress": 0}], "nucleus": {"ipa": "æ", "stress": 1},
           "coda": [], "wordEnd": false, "phraseEnd": false}},
  {"t": 0.522, "dur": 0.125, "midi": 63.0,
   "syl": {"text": "ther", "onset": [{"ipa": "ð", "stress": 0}], "nucleus": {"ipa": "ɚ", "stress": 0},
           "coda": [], "wordEnd": true, "phraseEnd": false}}
]
```

The command prints `<file>: N syllables`, where N is the number of sounding notes. Rests (midi
0 or less) give no entry. A note that holds the previous vowel (a melisma, `-` in the lyrics) does
get an entry. Its `syl` has `"melisma": true` (we read this from how `covers/sam/make_ab.py`
filters the file; we did not check the engine's code for it). Filter these out if you want
one entry per written syllable.

Why: another singer can then sing the same syllables on the same beats. We feed this file to the
S.A.M. voicebank renderer, while CHIMERA only moves the heads. See [sam-singing.md](sam-singing.md).
