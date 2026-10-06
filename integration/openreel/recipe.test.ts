import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { executeRecipe } from './execute-recipe';
import { createEmptyProject, saveProjectFile, loadProjectFile } from '../../vendor/openreel/packages/agent-runner/src/project-io';
import { HeadlessHost, executeTool, toMcpTools, generateCapabilityMarkdown } from '../../vendor/openreel/packages/agent/src/index';

it('executes actual Python KEEP recipe through upstream tools, preserves source timings, round-trips project', async () => {
  const recipe = JSON.parse(readFileSync('output/openreel-recipe.json', 'utf8'));
  const host = new HeadlessHost(createEmptyProject('Astel synthetic A/B', { width: 1080, height: 1920 }));
  const added = await executeTool('add_track', { trackType: 'video' }, host);
  expect(added.ok).toBe(true);
  const project = host.getProject();
  const track = project.timeline.tracks[0];
  recipe.preconditions.empty_track_id = track.id;
  recipe.calls.forEach((call: any) => { if (call.arguments.trackId) call.arguments.trackId = track.id; });
  project.mediaLibrary.items.push({ id: 'synthetic-media', name: 'synthetic.mp4', type: 'video', fileHandle: null, blob: null, thumbnailUrl: null, waveformData: null,
    metadata: { duration: 10, width: 1080, height: 1920, frameRate: 30, sampleRate: 48000, channels: 2, codec: 'h264', fileSize: 0 } });
  await saveProjectFile('output/openreel-empty.project.json', project);
  writeFileSync('output/openreel-bound.recipe.json', JSON.stringify(recipe, null, 2));
  const result = await executeRecipe(project, recipe);
  expect(project.timeline.tracks[0].clips).toHaveLength(0);
  expect(result.timeline.tracks[0].clips.map(c => ({ start: c.startTime, duration: c.duration, in: c.inPoint, out: c.outPoint }))).toEqual([
    { start: 0, duration: 2, in: 1, out: 3 }, { start: 2, duration: 3, in: 5, out: 8 },
  ]);
  await saveProjectFile('output/openreel-synthetic.project.json', result);
  const loaded = await loadProjectFile('output/openreel-synthetic.project.json');
  expect(loaded.timeline.tracks[0].clips).toHaveLength(2);
  await expect(executeRecipe(result, recipe)).rejects.toThrow('preconditions');
  const bad = structuredClone(recipe);
  bad.calls[1].arguments.clipId = '$missing';
  await expect(executeRecipe(project, bad)).rejects.toThrow('Unresolved');
  expect(project.timeline.tracks[0].clips).toHaveLength(0);
});

it('records the current upstream MCP catalog, not a historical tool count', () => {
  const tools = toMcpTools();
  expect(tools.some(t => t.name === 'split_clip')).toBe(true);
  expect(tools.some(t => t.name === 'render_motion_frame')).toBe(true);
  mkdirSync('output', { recursive: true });
  writeFileSync('output/openreel-tools.json', JSON.stringify(tools, null, 2));
  writeFileSync('output/openreel-capabilities.md', generateCapabilityMarkdown());
  console.log(`Current upstream tool count: ${tools.length}`);
});
