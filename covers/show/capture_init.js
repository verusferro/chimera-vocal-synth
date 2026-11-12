// Injected before the page's scripts when recording the show frame by frame (see record_show.ts).
// The page runs on a clock that only moves when the recorder steps it, so a frame that takes
// a second to draw in software still lands 1/30 s after the one before:
//  - performance.now and requestAnimationFrame: the stepped clock;
//  - the AudioContext's clock (the show's playhead is read from it): the same clock;
//  - CSS animations (the second head's slide-in): paused and moved along it;
//  - the corner video: never plays by itself, it is put on the playhead each step.
(() => {
  const cap = (window.__cap = { now: performance.now(), queue: [], nextId: 1, anims: new Map() });
  performance.now = () => cap.now;
  window.requestAnimationFrame = (cb) => {
    const id = cap.nextId++;
    cap.queue.push([id, cb]);
    return id;
  };
  window.cancelAnimationFrame = (id) => {
    cap.queue = cap.queue.filter(([i]) => i !== id);
  };
  Object.defineProperty(BaseAudioContext.prototype, "currentTime", { get: () => cap.now / 1000 });
  AudioContext.prototype.getOutputTimestamp = () => ({ contextTime: cap.now / 1000, performanceTime: cap.now });
  HTMLMediaElement.prototype.play = () => Promise.resolve();

  /** advance the clock by dt ms and draw one frame; resolves when the video is on the playhead (s) */
  window.__step = async (dt, playhead) => {
    cap.now += dt;
    for (const a of document.getAnimations()) {
      if (!cap.anims.has(a)) {
        cap.anims.set(a, cap.now);
        a.pause();
      }
      a.currentTime = cap.now - cap.anims.get(a);
    }
    const v = document.querySelector(".duet-video > video");
    if (v && playhead !== null && Math.abs(v.currentTime - playhead) > 1 / 120) {
      await new Promise((done) => {
        const t = setTimeout(done, 1500);
        v.addEventListener("seeked", () => (clearTimeout(t), done()), { once: true });
        v.currentTime = playhead;
      });
    }
    for (const [, cb] of cap.queue.splice(0)) cb(cap.now);
  };
})();
