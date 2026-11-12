#!/usr/bin/env bash
# Render the voices, mix them with the instrumental and write the duet show.
#   covers/song/build_show.sh        then open http://127.0.0.1:5317/?show=switch-off
#   Needs: a built CLI (cargo build --release -p chimera-cli), ffmpeg, covers/work/{song,stems} (see docs/song-from-youtube.md)
#   and public/shows/switch-off/video.mp4 (the corner video).
set -euo pipefail
COVERS="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(dirname "$COVERS")"
WORK="${COVERS_WORK:-$COVERS/work}"
PY="${PYTHON:-python3}" # a Python with librosa, soundfile etc. (the main venv)
SONG="$WORK/song"
SHOW="$REPO/public/shows/switch-off"
INST="$WORK/stems/song_(other)_bs_roformer_vocals_resurrection_unwa.wav"
# the bodies: the lead sings G3..G4 (a low woman's range); the second voice is Niko, a child
LEAD_BODY=female
SECOND_BODY=child

"$PY" "$COVERS/song/make_song.py"
mkdir -p "$SHOW"
cd "$REPO" # the CLI reads its dictionary from the repo
./target/release/chimera render notes "$SONG/lead.json" "$SONG/lead" $LEAD_BODY --tele "$SHOW/lead.tele" &
./target/release/chimera render notes "$SONG/second.json" "$SONG/second" $SECOND_BODY --tele "$SHOW/second.tele" &
wait
cp "$SONG/lead.json" "$SONG/second.json" "$SHOW/"

# Two tracks on one clock, both from sample 0 (the page plays them together): the voices
# (mix.mp3, as long as the song) and the instrumental (backing.mp3, which has the page's volume
# slider). A short room on the voices so they sit in the track; the second voice a little lower.
# Levels leave room for the two to add up without clipping.
ffmpeg -v error -y -i "$INST" -i "$SONG/lead.wav" -i "$SONG/second.wav" -filter_complex "
  [1:a]aresample=48000,highpass=f=90,volume=1.7,asplit=2[l][lr];[lr]aecho=0.6:0.5:60|110:0.25|0.18,volume=0.5[lw];
  [2:a]aresample=48000,highpass=f=120,volume=1.15,asplit=2[s][sr];[sr]aecho=0.6:0.5:70|130:0.25|0.18,volume=0.5[sw];
  [l][lw]amix=inputs=2:normalize=0,pan=stereo|c0=0.95*c0|c1=0.8*c0[lv];
  [s][sw]amix=inputs=2:normalize=0,pan=stereo|c0=0.75*c0|c1=0.95*c0[sv];
  [0:a]asplit=2[i0][i1];[i0]volume=0[len];[i1]volume=0.6[b];
  [len][lv][sv]amix=inputs=3:normalize=0:duration=first,volume=0.7,alimiter=limit=0.6:level=0[m]" \
  -map "[m]" -c:a libmp3lame -q:a 2 "$SHOW/mix.mp3" -map "[b]" -c:a libmp3lame -q:a 2 "$SHOW/backing.mp3"

# Each file's address carries its content's hash: a CDN (Cloudflare keeps .mp3 and .mp4 for
# hours) or a browser would otherwise go on serving the old sound under the new mouths.
v() { echo "$1?v=$(md5sum "$SHOW/$1" | cut -c1-8)"; }
cat > "$SHOW/show.json" <<EOF
{
  "title": "Switch Off The Game (Musiclide) - CHIMERA cover",
  "audio": "$(v mix.mp3)",
  "backing": "$(v backing.mp3)",
  "video": "$(v video.mp4)",
  "bpm": 96,
  "downbeat": 0,
  "voices": [
    { "name": "World Machine", "tele": "$(v lead.tele)", "melody": "$(v lead.json)" },
    { "name": "Niko", "tele": "$(v second.tele)", "melody": "$(v second.json)", "look": "niko", "on": [[179, null]] }
  ]
}
EOF
ls -la "$SHOW"
