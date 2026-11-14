import { projectionDefinition } from './live-state.js';
import { installLocalAdapter } from './local-adapter.js';
import { defaults } from './p0.js';
export const inject = ['sessionProjections', 'llm'];
export async function apply(ctx) {
  await ctx.sessionProjections.register(projectionDefinition);
  installLocalAdapter(ctx, defaults);
}
