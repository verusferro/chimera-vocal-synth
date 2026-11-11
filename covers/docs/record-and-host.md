# Screenshots, video and hosting

This page shows how to take a screenshot of a show, record it as an mp4, and put the site on a
web server. Run all commands from the repo root unless a step says otherwise.

You need a finished show in `public/shows/<id>/` first. See [song-from-youtube.md](song-from-youtube.md)
or [sam-singing.md](sam-singing.md). The show file format is in [ui-changes.md](ui-changes.md).

## Before you start

The scripts in `covers/show/` drive a real browser with `playwright-core`. This package is already
in `devDependencies`, so `bun install` gets it. It does not come with a browser. Two options:

- **Chrome (recommended).** Point the `CHROME` variable at a Chrome or Chromium binary. Chrome can
  play the H.264 corner video. Playwright's own Chromium cannot.
- **Playwright's Chromium.** Run `bunx playwright-core install chromium` once and leave `CHROME`
  unset. The corner video will stay black in your screenshots and recordings.

```sh
export CHROME=/usr/bin/google-chrome        # or the path of your Chrome / Chromium
```

If the browser does not start, the scripts stop with the message `cannot start the browser (set
CHROME ...)`.

You also need the dev server (the scripts read the page from it):

```sh
bunx vite --host 127.0.0.1 --port 5317 --strictPort
```

To use another address, set `SHOW_URL`, for example `SHOW_URL=http://127.0.0.1:5318`.

There is no GPU on our machine. The browser draws with SwiftShader, a software renderer
(`--use-angle=swiftshader`). One frame takes about 0.2 s to draw.

## Screenshot of a show at a time

```sh
bun covers/show/shot.ts <show> <seconds> <out.png> [width height]
bun covers/show/shot.ts switch-off-v1 60 /tmp/shot.png          # 1600 x 900
bun covers/show/shot.ts switch-off-v1 60 /tmp/shot.png 1920 1080
```

What the script does:

1. It opens `/?show=<show>` with `capture_init.js` injected (see the next section).
2. It steps the page clock while the show loads, then for 3 s more (the heads' opening turn).
3. It sets the seek slider to `<seconds>`, presses play, and steps the clock for 45 frames
   (1.5 s). Heads need this time to move from their rest pose into the sound at that second.
4. It writes the PNG.

Use it to check a costume, a lyric position or the layout without a full recording. Do not take
the screenshot with a normal browser tab: the playhead would run on real time, and drawing is
too slow.

## Record an mp4

```sh
bun covers/show/record_show.ts <show> [out.mp4] [seconds]
bun covers/show/record_show.ts switch-off-v1                 # whole song -> covers/work/switch-off-v1.mp4
bun covers/show/record_show.ts artist-block /tmp/ab.mp4 20   # first 20 s, as a test
```

Defaults: `out.mp4` is `covers/work/<show>.mp4` (`$COVERS_WORK/<show>.mp4` if you set it).
`seconds` is the length of the show's `audio` file, from `ffprobe`. You need `ffmpeg` and `ffprobe`
on your PATH. A full song (about four minutes, 7,000 frames or more) takes a long time on a CPU: each frame needs
about 0.2 s to draw plus the screenshot and the encode. [INFERENCE: we did not time a full run
for this page; expect well over half an hour.] Test with a
short `seconds` value first. The script prints progress every 300 frames.

### Why the clock is stepped

A live screen recording would stutter, because one frame takes longer than 1/30 s to draw. So the
page runs on a clock that only moves when the recorder says so. `covers/show/capture_init.js` is
injected before the page's own scripts. It replaces:

- `performance.now` and `requestAnimationFrame`: they use the stepped clock. Each step draws
  exactly one frame.
- The `AudioContext` clock (`currentTime`, `getOutputTimestamp`): the show's playhead is read from
  it, so it must be the same clock.
- CSS animations (the second head's slide-in): paused, then moved along the same clock.
- `HTMLMediaElement.play`: does nothing. The corner video never plays by itself. Each step puts it
  on the playhead and waits for the `seeked` event.

`window.__step(dt, playhead)` moves the clock by `dt` ms and draws one frame.

### What the script does

1. Starts the browser at 1600 x 900 CSS px with a device scale factor of 1.2. The screenshots are
   1920 x 1080.
2. Steps the clock until the show has loaded, then for 3 s of opening turn.
3. Starts `ffmpeg`, which reads JPEG frames (quality 93) from a pipe at 30 fps.
4. Presses play. Then for each frame: step 1000/30 ms, put the video on the playhead, screenshot,
   write the frame to `ffmpeg`.

The audio is not recorded from the browser. `ffmpeg` reads the show's audio files directly:
`audio` and, if the show has one, `backing` (the names come from `show.json`, without the `?v=`).
They are mixed at full level (`amix=normalize=0`) and then limited. The filter is
`alimiter=limit=0.94:level=0`: peaks stop at 0.94 of full scale (about -0.3 dB), and `level=0`
turns off the limiter's automatic gain. The voices and the instrumental add up, and without the
limiter they could clip. The mp4 uses H.264 (`crf 18`) and AAC at 192 kb/s.

The recording does not match what a live viewer hears when they change the Backing slider. It
uses both tracks at volume 1.

Common problems:

| Symptom | Cause and fix |
|---|---|
| `the show did not load` | The dev server is not running, or the show folder has a wrong file name. Open the page by hand and look at the console |
| Corner video is black | The browser has no H.264. Set `CHROME` |
| Video drifts away from the mouths | The `.tele` files and the mix do not start at the same sample. Rebuild the show |

## Build the site

```sh
bun install
rustup target add wasm32-unknown-unknown
bun run build
```

`bun run build` runs three things:

1. `bun run wasm`: `cargo build -p chimera-wasm --release --target wasm32-unknown-unknown`,
   then copies the result to `src/wasm/chimera.wasm`. This needs `cargo` and the `wasm32` target.
2. `tsc --noEmit`: a type check. The build stops on an error.
3. `vite build`: writes the site to `dist/`.

Vite copies everything in `public/` into `dist/`, including `public/shows/`. So the build contains
**all** your local shows. Remove the ones you do not want to publish:

```sh
rm -rf dist/shows/switch-off dist/shows/artist-block      # keep only what you host
ls dist/shows
```

Remember: a cover of a song is a derivative work. Only publish what you have the right to share.
The `.gitignore` already keeps `public/shows/` out of git. Do not commit the shows, and do not
publish the original video if you do not own it.

You can try the build locally with `bun run preview` (port 5318).

## Host it

`dist/` is a static site: any web server works. The page reads `show.json`, audio and video with
normal HTTP requests. The server must support byte ranges for the mp4 (nginx does by default).

Example nginx server block for `https://covers.example.com`. It sends `/` to one show and asks
search engines not to index the site. The paths are examples.

```nginx
server {
    listen 80;
    server_name covers.example.com;
    root /var/www/covers;                      # the contents of dist/
    index index.html;

    add_header X-Robots-Tag "noindex, nofollow" always;

    # the front page opens the show directly
    location = / {
        return 302 /?show=artist-block;
    }

    # the page and the show file: always check for a new version
    location = /index.html { add_header Cache-Control "no-cache"; add_header X-Robots-Tag "noindex, nofollow" always; }
    location ~ ^/shows/[^/]+/show\.json$ { add_header Cache-Control "no-cache"; add_header X-Robots-Tag "noindex, nofollow" always; }

    location / {
        try_files $uri $uri/ =404;
    }
}
```

Note that `add_header` inside a `location` replaces the headers from the `server` level, so the
`X-Robots-Tag` line is repeated there. Add a `robots.txt` file with `User-agent: *` and
`Disallow: /` to `dist/` too if you want a second signal.

Copy the build and test the config:

```sh
rsync -a --delete dist/ user@your-server:/var/www/covers/
ssh user@your-server 'sudo nginx -t && sudo systemctl reload nginx'
```

Use HTTPS. The main app's audio engine is an AudioWorklet, which browsers only allow in a secure
context (HTTPS or `localhost`). We ran our shows behind a tunnel that adds HTTPS, see below.

### Optional: Cloudflare Tunnel

A tunnel lets you host from a machine without open ports or a public IP. `cloudflared` makes an
outbound connection, and Cloudflare serves the HTTPS side. We used this for the shows: nginx
listened on a local port, and the tunnel pointed a host name at it. (The tunnel steps below are
reconstructed from the usual `cloudflared` setup. We did not keep the exact config file in the
repo.)

Add an ingress rule to the tunnel's config (`config.yml`), before the final catch-all rule:

```yaml
tunnel: <TUNNEL-ID>
credentials-file: /etc/cloudflared/<TUNNEL-ID>.json

ingress:
  - hostname: covers.example.com
    service: http://127.0.0.1:8080          # the port nginx listens on
  - service: http_status:404
```

Make nginx listen on that port (`listen 127.0.0.1:8080;`). Then create the DNS record and
restart the service:

```sh
cloudflared tunnel route dns <TUNNEL-NAME-OR-ID> covers.example.com
sudo systemctl restart cloudflared
```

`route dns` creates a CNAME from `covers.example.com` to `<TUNNEL-ID>.cfargotunnel.com`.

To take a show offline, remove the nginx `server` block (or the symlink in `sites-enabled`) and
reload nginx.

## Cache busting

Each show is a set of files that must match: the `.tele` files, the melody JSON, the audio and
the video. If a viewer's browser (or a CDN) keeps an old `mix.mp3` and gets a new `lead.tele`, the
mouths move to the wrong sound. This happens in practice: Cloudflare keeps `.mp3` and `.mp4` files
for hours.

The fix is in the show format. The build scripts write every file name in `show.json` as
`name?v=<first 8 hex digits of its MD5>`. A new content gives a new URL. Details and the
one-line command are in [ui-changes.md](ui-changes.md#hashed-v-urls).

What you must do when you host:

- Let `show.json` and `index.html` revalidate (`Cache-Control: no-cache`, as in the nginx
  example above). They are the only files without a hash in their address. Vite's own files in
  `assets/` carry a hash in the name, so they can be cached for a long time.
- After you rebuild a show, copy the whole show folder, with the new `show.json`.
- If you edit a file by hand, write the hash again (rerun the show's build script, or run
  `md5sum` and edit `show.json`).
- If a CDN still serves old data after a change, purge its cache for the show's folder.

## Dependencies for this page

- Bun, `playwright-core` (from `bun install`), Chrome or Chromium (`CHROME`).
- `ffmpeg` and `ffprobe` (with `libx264`, `aac`).
- Rust (`cargo`) with the `wasm32-unknown-unknown` target, for `bun run build`.
- A web server (nginx in the example). `rsync` and `ssh` for the copy command.
- Optional: `cloudflared` and a Cloudflare account with a domain.
