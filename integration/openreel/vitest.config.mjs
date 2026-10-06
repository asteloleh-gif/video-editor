import path from 'node:path';
const root = path.resolve(import.meta.dirname, '../..');
export default {
  test: { globals: true, environment: 'node', include: ['integration/openreel/**/*.test.ts'] },
  resolve: { alias: { '@openreel/core': path.join(root, 'vendor/openreel/packages/core/src'), '@openreel/agent': path.join(root, 'vendor/openreel/packages/agent/src') } },
};
