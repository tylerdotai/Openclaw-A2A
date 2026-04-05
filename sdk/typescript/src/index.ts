/**
 * OpenClaw A2A TypeScript SDK
 *
 * @example
 * import { OpenClawA2AClient, AgentCardBuilder } from '@flume-a2a/sdk';
 */

// Client
export { OpenClawA2AClient, A2AError, A2A_ERROR_CODES } from './client.js';
export type { A2AClientOptions } from './models.js';

// Server
export { A2AServer, InMemoryTaskStore, StreamManager } from './server.js';
export type { A2AServerOptions, MessageHandler } from './server.js';

// Models
export * from './models.js';

// Agent Card
export { AgentCardBuilder, buildFromEnv } from './agent_card.js';
export type { AgentCardBuilderOptions, DetectedCapabilities, SkillDir } from './agent_card.js';
