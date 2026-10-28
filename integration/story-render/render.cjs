// Installed fixed renderer. Package data cannot select an executable or entry point.
const fs = require('node:fs');
const path = require('node:path');
const {createHash} = require('node:crypto');
const {bundle} = require('@remotion/bundler');
const {openBrowser, selectComposition, renderMedia, makeCancelSignal} = require('@remotion/renderer');

const atomic = (file, value) => {
  fs.writeFileSync(`${file}.tmp`, JSON.stringify(value), {mode: 0o600});
  fs.renameSync(`${file}.tmp`, file);
};
async function main() {
  const request = JSON.parse(fs.readFileSync(0, 'utf8'));
  const manifest = JSON.parse(fs.readFileSync(path.join(request.packageRoot, 'manifest.json'), 'utf8'));
  if (manifest.composition !== 'AstelStoryPilot-3D') throw new Error('Unsupported composition');
  const inputProps = JSON.parse(fs.readFileSync(path.join(request.packageRoot, 'props.json'), 'utf8'));
  const progress = (phase, value) => atomic(path.join(request.jobRoot, 'progress.json'), {phase, progress: value});
  const {cancel, cancelSignal} = makeCancelSignal();
  let cancelled = false;
  const stop = () => {cancelled = true; cancel();};
  process.on('SIGTERM', stop);
  progress('Подготовка сцен', .01);
  const serveUrl = await bundle({entryPoint: path.join(__dirname, 'src/index.ts'), publicDir: path.join(request.packageRoot, 'public')});
  if (cancelled) throw new Error('Cancelled');
  const chromiumOptions = {gl: 'angle'};
  const browser = await openBrowser('chrome', {chromiumOptions});
  try {
    const composition = await selectComposition({serveUrl, id: manifest.composition, inputProps, puppeteerInstance: browser, chromiumOptions});
    const outputLocation = path.join(request.jobRoot, 'video.mp4');
    await renderMedia({composition, serveUrl, inputProps, outputLocation,
      codec: 'h264', audioCodec: 'aac', enforceAudioTrack: true, pixelFormat: 'yuv420p', crf: 20,
      concurrency: 2, chromiumOptions, puppeteerInstance: browser, cancelSignal,
      timeoutInMilliseconds: 120000, overwrite: true,
      onProgress: ({progress: value}) => progress('Рендер видео и звука', .03 + value * .94),
    });
    if (cancelled) throw new Error('Cancelled');
    progress('Проверка MP4', .98);
    const sha256 = createHash('sha256').update(fs.readFileSync(outputLocation)).digest('hex');
    atomic(path.join(request.jobRoot, 'result.json'), {sha256});
  } finally {
    await browser.close({silent: true});
  }
}
main().catch(error => {console.error(error); process.exitCode = 1;});
