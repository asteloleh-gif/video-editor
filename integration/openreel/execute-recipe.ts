import { HeadlessHost, executeTool } from '../../vendor/openreel/packages/agent/src/index';
import type { Project } from '../../vendor/openreel/packages/core/src/types/project';

export interface Recipe {
  preconditions: { empty_track_id: string; source_media_id: string; source_duration: number };
  calls: { name: string; arguments: Record<string, unknown>; bind?: string }[];
}

/** Execute on an isolated clone, never on the live editor. Commit only on success. */
export async function executeRecipe(project: Project, recipe: Recipe): Promise<Project> {
  const host = new HeadlessHost(structuredClone(project));
  const track = project.timeline.tracks.find(t => t.id === recipe.preconditions.empty_track_id);
  const media = project.mediaLibrary.items.find(m => m.id === recipe.preconditions.source_media_id);
  if (!track || track.clips.length || track.locked || !media || Math.abs(media.metadata.duration - recipe.preconditions.source_duration) > 0.001) {
    throw new Error('Recipe preconditions failed: require empty unlocked track and matching source media');
  }
  const transaction = host.beginTransaction('Astel KEEP recipe');
  const bindings = new Map<string, string>();
  try {
    for (const call of recipe.calls) {
      if (!['add_clip', 'trim_clip', 'move_clip'].includes(call.name)) throw new Error('Unsupported recipe tool');
      const args = { ...call.arguments };
      if (typeof args.clipId === 'string' && args.clipId.startsWith('$')) {
        const bound = bindings.get(args.clipId);
        if (!bound) throw new Error('Unresolved clip binding');
        args.clipId = bound;
      }
      const idsBefore = new Set(host.getProject().timeline.tracks.flatMap(t => t.clips.map(c => c.id)));
      const result = await executeTool(call.name, args, host);
      if (!result.ok) throw new Error(result.error?.message ?? result.summary);
      if (call.bind) {
        const added = host.getProject().timeline.tracks.flatMap(t => t.clips).filter(c => !idsBefore.has(c.id));
        if (added.length !== 1) throw new Error('Expected exactly one newly added clip');
        bindings.set(call.bind, added[0].id);
      }
    }
    host.commitTransaction(transaction, 'Astel KEEP recipe');
    return host.getProject();
  } catch (error) {
    await host.rollbackTransaction(transaction);
    throw error;
  }
}
