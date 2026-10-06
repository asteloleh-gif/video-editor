import { readFile, open } from 'node:fs/promises';
import path from 'node:path';
import { loadProjectFile } from '../../vendor/openreel/packages/agent-runner/src/project-io';
import { ProjectSerializer } from '../../vendor/openreel/packages/core/src/storage/project-serializer';
import type { IStorageEngine } from '../../vendor/openreel/packages/core/src/storage/types';
import { executeRecipe } from './execute-recipe';

async function main() {
  const [projectFile, recipeFile, outputFile] = process.argv.slice(2);
  if (!projectFile || !recipeFile || !outputFile) throw new Error('Usage: node astel-recipe.cjs INPUT.project.json RECIPE.json NEW_OUTPUT.project.json');
  if (path.resolve(outputFile) === path.resolve(projectFile) || path.resolve(outputFile) === path.resolve(recipeFile)) throw new Error('Output must be a new file');
  const recipe = JSON.parse(await readFile(recipeFile, 'utf8'));
  const result = await executeRecipe(await loadProjectFile(projectFile), recipe);
  const unavailableStorage = new Proxy({}, { get() { throw new Error('Offline recipe has no storage engine'); } }) as IStorageEngine;
  const serialized = new ProjectSerializer(unavailableStorage).exportToJson(result);
  const output = await open(outputFile, 'wx');
  try { await output.writeFile(serialized); } finally { await output.close(); }
  console.log(`Saved isolated candidate: ${outputFile}`);
}
void main().catch(error => { console.error(error instanceof Error ? error.message : String(error)); process.exitCode = 1; });
