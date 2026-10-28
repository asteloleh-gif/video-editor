// Render a few inspection frames, including the same frame after a seek.
// No video export and no access to private voice references or source media.
const {bundle} = require('@remotion/bundler');
const {openBrowser, selectComposition, renderStill} = require('@remotion/renderer');
const {createHash} = require('node:crypto');
const fs = require('node:fs/promises');
const path = require('node:path');

async function verify() {
  const root = path.resolve(__dirname, '..');
  const destination = path.resolve(process.argv[2] || path.join(root, '../output/motion-study'));
  await fs.mkdir(destination, {recursive: true});
  const serveUrl = await bundle({entryPoint: path.join(root, 'src/index.ts')});
  const chromiumOptions = {gl: 'angle'};
  const browser = await openBrowser('chrome', {chromiumOptions});
  const results = [];
  const compositions = new Map();
  try {
    for (const [id, frame, name] of [
      ['AmazonMotion-Compare', 60, 'book'],
      ['AmazonMotion-Compare', 165, 'box'],
      ['AmazonMotion-Compare', 315, 'server'],
      ['AmazonMotion-Compare', 60, 'book-repeat'],
      ['AmazonMotion-2D', 315, 'portrait-2d'],
      ['AmazonMotion-3D', 315, 'portrait-3d'],
    ]) {
      let composition = compositions.get(id);
      if (!composition) {
        composition = await selectComposition({serveUrl, id, puppeteerInstance: browser, chromiumOptions});
        if (composition.fps !== 30 || composition.durationInFrames !== 360) {
          throw new Error('A/B compositions must share a 12-second, 30fps timeline');
        }
        compositions.set(id, composition);
      }
      const output = path.join(destination, `${name}.png`);
      const started = performance.now();
      await renderStill({serveUrl, composition, frame, output, puppeteerInstance: browser, chromiumOptions, imageFormat: 'png'});
      const sha256 = createHash('sha256').update(await fs.readFile(output)).digest('hex');
      const result = {composition: id, frame, name, sha256, render_ms: Math.round(performance.now() - started)};
      results.push(result);
      console.log(JSON.stringify(result));
    }
    const repeatMatches = results[0].sha256 === results[3].sha256;
    await fs.writeFile(path.join(destination, 'render-qa.json'), JSON.stringify({
      mode: 'still_render_QA_no_video_export', renderer: 'angle', results,
      repeat_matches: repeatMatches,
    }, null, 2) + '\n');
    if (!repeatMatches) throw new Error('Repeated frame differs after rendering later frames');
  } finally {
    await browser.close({silent: true});
  }
}
verify().catch(error => {console.error(error); process.exitCode = 1;});
