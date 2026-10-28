const fs = require('node:fs');
const path = require('node:path');
const {createHash} = require('node:crypto');
const {bundle} = require('@remotion/bundler');
const {openBrowser, selectComposition, renderMedia, makeCancelSignal} = require('@remotion/renderer');
async function main() {
  const {jobRoot} = JSON.parse(fs.readFileSync(0, 'utf8'));
  const propsPath = path.join(jobRoot, 'props.json');
  const propsBytes = fs.readFileSync(propsPath);
  const inputProps = JSON.parse(propsBytes);
  const atomic = (name, value) => {const file=path.join(jobRoot,name); fs.writeFileSync(file+'.tmp',JSON.stringify(value),{mode:0o600}); fs.renameSync(file+'.tmp',file);};
  const {cancel, cancelSignal} = makeCancelSignal(); let cancelled = false;
  process.on('SIGTERM', () => {cancelled = true; cancel();});
  atomic('progress.json',{progress:0});
  const serveUrl = await bundle({entryPoint: path.join(__dirname, 'src/workspace-entry.tsx'), publicDir: path.join(jobRoot, 'public')});
  if (cancelled) throw new Error('Cancelled');
  const chromiumOptions = {gl: 'angle'};
  const browserExecutable = path.join(__dirname,'node_modules/.remotion/chrome-headless-shell/mac-arm64/chrome-headless-shell-mac-arm64/chrome-headless-shell');
  if (!fs.existsSync(browserExecutable)) throw new Error('Provision the pinned local browser first');
  const browser = await openBrowser('chrome', {chromiumOptions,browserExecutable});
  try {
    if (cancelled) throw new Error('Cancelled');
    const composition = await selectComposition({serveUrl, id: 'StoryShortV1', inputProps, puppeteerInstance: browser, chromiumOptions});
    await renderMedia({composition, serveUrl, inputProps, outputLocation: path.join(jobRoot, 'video.mp4'), codec: 'h264', audioCodec: 'aac', enforceAudioTrack: true,
      crf: 20, pixelFormat: 'yuv420p', concurrency: 2, chromiumOptions, puppeteerInstance: browser, cancelSignal, overwrite: true, timeoutInMilliseconds: 120000,
      onProgress: ({progress}) => atomic('progress.json',{progress})});
    if (cancelled) throw new Error('Cancelled');
    atomic('render-receipt.json',{props_sha256:createHash('sha256').update(propsBytes).digest('hex'),sha256:createHash('sha256').update(fs.readFileSync(path.join(jobRoot,'video.mp4'))).digest('hex')});
  } finally {await browser.close({silent: true});}
}
main().catch(error => {console.error(error); process.exitCode = 1;});
