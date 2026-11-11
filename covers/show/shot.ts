// Screenshot a show at a playhead time (from the repo root; the dev server must run):
//   bun covers/show/shot.ts <show> <seconds> <out.png> [width height]
// Env: CHROME = path to a Chrome/Chromium binary (default: Playwright's own Chromium, which cannot
// play the corner video's H.264); SHOW_URL = the server (default http://127.0.0.1:5317).
import { chromium } from "../../node_modules/playwright-core";
const [show, sec, out, w = "1600", h = "900"] = process.argv.slice(2);
if (!show || !sec || !out) throw new Error("usage: bun covers/show/shot.ts <show> <seconds> <out.png> [width height]");
const b = await chromium
  .launch({ headless: true, executablePath: process.env.CHROME, args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] })
  .catch((e) => { throw new Error(`cannot start the browser (set CHROME to a Chrome or Chromium binary): ${e.message}`); });
const p = await b.newPage({ viewport: { width: +w, height: +h }, deviceScaleFactor: 1 });
p.on("pageerror", (e) => console.error("page error:", e.message));
await p.addInitScript({ path: new URL("capture_init.js", import.meta.url).pathname });
await p.goto(`${process.env.SHOW_URL ?? "http://127.0.0.1:5317"}/?show=${show}`);
for (let i = 0; i < 400; i++) { await p.evaluate("window.__step(100, 0)"); if (await p.evaluate("!!document.querySelector('.duet-head canvas') && !document.querySelector('button.primary').disabled")) break; await Bun.sleep(200); }
for (let i = 0; i < 30; i++) await p.evaluate("window.__step(100, 0)");
const t0 = +sec;
await p.evaluate(`(() => { const i = document.querySelector('.duet-bar > input[type=range]'); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; set.call(i, '${t0}'); i.dispatchEvent(new Event('input', { bubbles: true })); i.dispatchEvent(new Event('change', { bubbles: true })); })()`);
await p.click("button.primary");
for (let i = 0; i < 45; i++) { await p.evaluate(`window.__step(${1000 / 30}, ${t0 + (i + 1) / 30})`); await Bun.sleep(20); }
await p.screenshot({ path: out });
await b.close();
