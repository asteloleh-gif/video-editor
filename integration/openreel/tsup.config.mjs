export default {
  entry: { 'astel-recipe': 'integration/openreel/cli.ts' },
  outDir: 'integration/openreel/build',
  tsconfig: 'integration/openreel/tsconfig.json',
  outExtension: () => ({ js: '.cjs' }),
  format: ['cjs'], platform: 'node', target: 'node20',
  noExternal: ['@openreel/agent', '@openreel/core', '@openreel/creation-schema'],
  clean: true,
};
