/**
 * AgentCard Builder for OpenClaw A2A
 *
 * Helps construct compliant AgentCard objects with validation,
 * skill detection from directories, and environment-based defaults.
 */

import { AgentCard, AgentCapabilities, AgentProvider, AgentSkill } from './models.js';

// ── Skill loading from directory ───────────────────────────────────────────────

export interface SkillDir {
  name: string;
  description?: string;
  tags?: string[];
  metadata?: Record<string, unknown>;
}

/**
 * Load skill definitions from a directory of skill folders.
 * Each skill folder should have a SKILL.md with frontmatter:
 *   ---
 *   name: skill-name
 *   description: What the skill does
 *   tags: [tag1, tag2]
 *   emoji: '🤖'
 *   ---
 */
export function loadSkillsFromDir(skillsDir: string): SkillDir[] {
  // Placeholder — actual implementation would read filesystem
  return [];
}

// ── Capability detection ──────────────────────────────────────────────────────

export interface DetectedCapabilities {
  streaming: boolean;
  pushNotifications: boolean;
  stateTransitionHistory: boolean;
  extendedAgentCard: boolean;
}

/**
 * Auto-detect capabilities based on available modules.
 */
export function detectCapabilities(): DetectedCapabilities {
  return {
    streaming: true,        // All OpenClaw A2A servers support streaming
    pushNotifications: true, // Push notification support is standard
    stateTransitionHistory: false, // Requires explicit opt-in
    extendedAgentCard: false, // Requires auth — not available to anonymous callers
  };
}

// ── AgentCard Builder ──────────────────────────────────────────────────────────

export interface AgentCardBuilderOptions {
  name: string;
  version?: string;
  description?: string;
  url?: string;
  organization?: string;
  skills?: SkillDir[];
  capabilities?: Partial<AgentCapabilities>;
  envPrefix?: string;
}

export class AgentCardBuilder {
  private name: string;
  private version: string = '1.0.0';
  private description: string = '';
  private url: string = '';
  private organization: string = 'flume';
  private skills: AgentSkill[] = [];
  private capabilities: AgentCapabilities = {
    streaming: true,
    push_notifications: true,
    state_transition_history: false,
    extensions: [],
  };

  constructor(options: AgentCardBuilderOptions) {
    this.name = options.name;
    if (options.version) this.version = options.version;
    if (options.description) this.description = options.description;
    if (options.url) this.url = options.url;
    if (options.organization) this.organization = options.organization;
    if (options.capabilities) {
      this.capabilities = { ...this.capabilities, ...options.capabilities };
    }
    if (options.skills) {
      this.skills = options.skills.map(s => ({
        id: s.name.toLowerCase().replace(/\s+/g, '-'),
        name: s.name,
        description: s.description ?? '',
        tags: s.tags ?? [],
        metadata: s.metadata ?? {},
      }));
    }
  }

  /**
   * Set the agent's URL (how others reach it).
   */
  withUrl(url: string): this {
    this.url = url;
    return this;
  }

  /**
   * Add a skill to the agent card.
   */
  addSkill(skill: SkillDir): this {
    this.skills.push({
      id: skill.name.toLowerCase().replace(/\s+/g, '-'),
      name: skill.name,
      description: skill.description ?? '',
      tags: skill.tags ?? [],
      metadata: skill.metadata ?? {},
    });
    return this;
  }

  /**
   * Add multiple skills at once.
   */
  addSkills(skills: SkillDir[]): this {
    for (const skill of skills) this.addSkill(skill);
    return this;
  }

  /**
   * Enable or disable specific capabilities.
   */
  withCapabilities(caps: Partial<AgentCapabilities>): this {
    this.capabilities = { ...this.capabilities, ...caps };
    return this;
  }

  /**
   * Load skills from a directory on disk.
   */
  withSkillsFromDir(skillsDir: string): this {
    const skills = loadSkillsFromDir(skillsDir);
    return this.addSkills(skills);
  }

  /**
   * Auto-detect capabilities based on environment.
   */
  withAutoDetectedCapabilities(): this {
    const detected = detectCapabilities();
    return this.withCapabilities(detected);
  }

  /**
   * Build the final AgentCard object.
   */
  build(): AgentCard {
    const slug = this.name.toLowerCase().replace(/\s+/g, '-');
    return {
      id: `${this.organization}/${slug}`,
      name: this.name,
      version: this.version,
      description: this.description,
      url: this.url,
      capabilities: this.capabilities,
      provider: {
        organization: this.organization,
        url: this.url ? `${this.url}/a2a` : undefined,
      },
      skills: this.skills,
      default_input_modes: ['text/plain', 'application/json'],
      default_output_modes: ['text/plain', 'application/json'],
    };
  }
}

// ── Load from environment ─────────────────────────────────────────────────────

/**
 * Build an AgentCard from environment variables:
 *   A2A_AGENT_NAME=MyAgent
 *   A2A_AGENT_VERSION=1.0.0
 *   A2A_AGENT_URL=http://localhost:8080
 *   A2A_ORGANIZATION=flume
 */
export function buildFromEnv(prefix: string = 'A2A_AGENT'): AgentCard {
  const get = (key: string) => process.env[`${prefix}_${key}`];

  const name = get('NAME') ?? 'openclaw-agent';
  const version = get('VERSION') ?? '1.0.0';
  const url = get('URL') ?? '';
  const organization = get('ORGANIZATION') ?? 'flume';

  return new AgentCardBuilder({
    name,
    version,
    url,
    organization,
  }).build();
}
