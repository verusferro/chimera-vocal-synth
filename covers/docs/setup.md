# Setup

We ran everything on Linux (Ubuntu 24.04 under WSL2) on a CPU only. A GPU is not necessary.

## 1. CHIMERA itself

You need [Rust](https://rustup.rs) with the WebAssembly target, [Bun](https://bun.sh), and ffmpeg
with the Rubber Band filter, libx264, aac and libmp3lame (the Ubuntu `ffmpeg` package has all of
them). The screenshot and recording tools also need a Chrome binary in the `CHROME` environment
variable, because Playwright's own Chromium cannot play the H.264 corner video.

```sh
rustup target add wasm32-unknown-unknown
bun install
bun run wasm                                  # builds src/wasm/chimera.wasm
cargo build --release -p chimera-cli          # the CLI: ./target/release/chimera
bunx vite --host 127.0.0.1 --port 5317 --strictPort   # dev server
```

Open a show at `http://127.0.0.1:5317/?show=<id>`. The CLI reads its dictionary from the repo, so
run it from the repo root.

## 2. Python

One virtual environment runs all `covers/` scripts. We used Python 3.12 and
[uv](https://docs.astral.sh/uv/).

```sh
uv venv -p 3.12 .venv
uv pip install --python .venv/bin/python \
  "audio-separator[cpu]" librosa soundfile pyworld cmudict scipy pillow faster-whisper rmvpe-onnx "setuptools<81"
```

`pyworld` needs `pkg_resources`, which `setuptools` 81 and later do not have. That is why
`setuptools` is pinned.

Run the scripts with this Python, for example `.venv/bin/python covers/sam/build_ab.py`.

### Optional: an AMD GPU for stem separation

Separating a song takes about 8 times its length on a 6-core CPU (a 109 s song: 15 minutes). On a
Radeon RX 9070 XT it takes about 0.6 times its length (the same song: 65 s). We used WSL2 with AMD's ROCm for WSL (7.2) already installed in `/opt/rocm`
(`/opt/rocm/bin/rocminfo` must list the GPU).

```sh
uv venv -p 3.12 covers/vendor/rocm/.venv
uv pip install --python covers/vendor/rocm/.venv/bin/python \
  --index-url https://download.pytorch.org/whl/rocm6.4 torch==2.8.0 torchaudio==2.8.0
uv pip install --python covers/vendor/rocm/.venv/bin/python "audio-separator[cpu]" audioread
# WSL: use the system HSA runtime (it talks to the Windows driver), not the bundled one
rm covers/vendor/rocm/.venv/lib/python3.12/site-packages/torch/lib/libhsa-runtime64.so*
```

Run it through `covers/song/separate.py` with `LD_LIBRARY_PATH=/opt/rocm/lib`. The wrapper
switches the RoFormer attention to PyTorch's plain kernel: with the default one, this GPU gives
noise instead of a vocal stem. We checked the wrapper's stem against the CPU stem: it matches to
-85 dB. AMD's own "lightweight" ROCm 7.2 wheels did not load here, because they need ROCm
libraries that the WSL install lacks. Whisper (faster-whisper) has no ROCm build, so it stays on
the CPU (a few minutes per song).

## 3. The work and vendor folders

All scripts find their files through [`covers/paths.py`](../paths.py):

| Name | Default | Override | Contents |
|---|---|---|---|
| `WORK` | `covers/work/` | `COVERS_WORK` | Song downloads, stems, notes, words, renders |
| `VENDOR` | `covers/vendor/` | `COVERS_VENDOR` | Outside tools, models and the voicebank |

Both folders are gitignored. They can be symlinks to a bigger disk.

`VENDOR` must contain:

| Path | What | Where to get it |
|---|---|---|
| `vendor/models/` | Stem separation models: `bs_roformer_vocals_resurrection_unwa`, `bs_roformer_karaoke_frazer_becruily` (`.ckpt` + `.yaml`) | audio-separator downloads them on first use with `--model_file_dir covers/vendor/models` |
| `vendor/sam-tts/` | S.A.M. text-to-speech: we used [vidarh/SAM](https://github.com/vidarh/SAM), a fork of [s-macke/SAM](https://github.com/s-macke/SAM). Build it with `make` (needs gcc; see [sam-singing.md](sam-singing.md) for the edit that drops SDL) | Only for S.A.M. speech |
| `vendor/sam-bank/` | The `Samparsing` folder of the S.A.M. UTAU voicebank | Only for S.A.M. singing, see [sam-singing.md](sam-singing.md) |
| `vendor/GAME/` | [openvpi/GAME](https://github.com/openvpi/GAME), a singing-note transcriber. Give it its own Python 3.12 `.venv` with CPU torch and its `requirements.txt`. Unzip the `GAME-1.0-medium` weights from its [releases](https://github.com/openvpi/GAME/releases) to `weights/GAME-1.0-medium/model.pt` | See [song-from-youtube.md](song-from-youtube.md) |
| `vendor/HubertFA/` | [wolfgitpr/HubertFA](https://github.com/wolfgitpr/HubertFA), a lyrics-to-audio aligner. Give it its own Python 3.10 `.venv` with `requirements_onnx.txt` (change `onnxruntime-gpu` to `onnxruntime`), plus `soundfile` and `setuptools<81`. Unzip the ONNX model `1218_hfa_model_new_dict.zip` (v0.0.7) from its [releases](https://github.com/wolfgitpr/HubertFA/releases) to `models/` | See [song-from-youtube.md](song-from-youtube.md) |
| `vendor/7z/` | [7-Zip](https://github.com/ip7z/7zip/releases) (`7zz`), to unpack the voicebank RAR | Any `7z` on your PATH also works |

Only `models`, `GAME` and `HubertFA` are needed for a CHIMERA-only cover.

## 4. Check

```sh
.venv/bin/python -c "import librosa, pyworld, soundfile, audio_separator"
./target/release/chimera --help
```

Next: [From a YouTube link to a show](song-from-youtube.md).
