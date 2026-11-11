/**
 * Record a duet show to an mp4, frame by frame (no GPU here: a frame takes about 0.2 s to draw,
 * so a live screen recording would stutter). The page runs on a stepped clock (capture_init.js);
 * each step is one frame of 1/30 s, screenshotted and piped to ffmpeg, with the show's audio
 * (the mix, and the backing track if the show has one) under it.
 *
 *   bun covers/show/record_show.ts <show> [out.mp4] [seconds]
 *
 * Defaults: out = covers/work/<show>.mp4 (or $COVERS_WORK/<show>.mp4); seconds = the mix's length.
 * Needs the dev server on 127.0.0.1:5317 (bunx vite --host 127.0.0.1 --port 5317), ffmpeg and
 * ffprobe on PATH. Env: CHROME = path to Chrome/Chromium (default: Playwright's own Chromium,
 * which cannot play the corner video's H.264); SHOW_URL = another server.
 */
import { chromium } from "../../node_modules/playwright-core";

const REPO = new URL("../..", import.meta.url).pathname;
const [show, outArg, secArg] = process.argv.slice(2);
if (!show) throw new Error("usage: bun covers/show/record_show.ts <show> [out.mp4] [seconds]");
const SHOW = `${REPO}public/shows/${show}`;
// file names in show.json carry a ?v=hash for the browser's cache
const info = (await Bun.file(`${SHOW}/show.json`).json()) as { audio: string; backing?: string };
const file = (f: string) => `${SHOW}/${f.split("?")[0]}`;
const out = outArg ?? `${process.env.COVERS_WORK ?? `${REPO}covers/work`}/${show}.mp4`;
const FPS = 30;
const length = async () => Number((await Bun.$`ffprobe -v error -show_entries format=duration -of csv=p=0 ${file(info.audio)}`.text()).trim());
const seconds = secArg ? Number(secArg) : await length();
const TOTAL = Math.ceil(seconds * FPS);

// Use Chrome (CHROME=/path/to/chrome): unlike Playwright's Chromium it plays H.264, which the corner video is.
const browser = await chromium
  .launch({ headless: true, executablePath: process.env.CHROME, args: ["--autoplay-policy=no-user-gesture-required", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] })
  .catch((e) => { throw new Error(`cannot start the browser (set CHROME to a Chrome or Chromium binary): ${e.message}`); });
// 1600 x 900 CSS px at 1.2 = 1920 x 1080
const page = await browser.newPage({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1.2 });
page.on("pageerror", (e) => console.error("page error:", e.message));
await page.addInitScript({ path: new URL("capture_init.js", import.meta.url).pathname });
await page.goto(`${process.env.SHOW_URL ?? "http://127.0.0.1:5317"}/?show=${show}`);

// nothing draws until the clock is stepped: step while the show loads, then through the heads' opening turn
for (let i = 0; ; i++) {
  await page.evaluate("window.__step(100, 0)");
  if (await page.evaluate("!!document.querySelector('.duet-head canvas') && !document.querySelector('button.primary').disabled")) break;
  if (i > 400) throw new Error("the show did not load");
  await Bun.sleep(200);
}
for (let i = 0; i < 30; i++) await page.evaluate("window.__step(100, 0)");

const ff = Bun.spawn(
  ["ffmpeg", "-v", "error", "-y", "-f", "image2pipe", "-framerate", String(FPS), "-c:v", "mjpeg", "-i", "-", "-i", file(info.audio), ...(info.backing ? ["-i", file(info.backing)] : []),
    // the voices and the backing sum above full scale: limit to 0.94 (-0.3 dB), no auto level
    "-filter_complex", `${info.backing ? "[1:a][2:a]amix=inputs=2:normalize=0," : "[1:a]"}alimiter=limit=0.94:level=0[a]`, "-map", "0:v", "-map", "[a]",
    "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-vf", "scale=1920:1080", "-c:a", "aac", "-b:a", "192k", "-t", String(seconds), "-movflags", "+faststart", out],
  { stdin: "pipe", stdout: "inherit", stderr: "inherit" },
);

await page.click("button.primary");
const t0 = Date.now();
for (let i = 0; i < TOTAL; i++) {
  await page.evaluate(`window.__step(${1000 / FPS}, ${(i + 1) / FPS})`);
  ff.stdin.write(await page.screenshot({ type: "jpeg", quality: 93 }));
  if (i % 300 === 299) {
    await ff.stdin.flush();
    console.log(`${i + 1}/${TOTAL} frames, ${((Date.now() - t0) / 60000).toFixed(1)} min, playhead ${await page.evaluate("document.querySelector('.duet-time').textContent")}`);
  }
}
await ff.stdin.end();
console.log("ffmpeg exit", await ff.exited, "->", out);
await browser.close();
