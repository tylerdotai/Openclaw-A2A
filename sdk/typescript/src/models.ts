// A2A Protocol Types

export type TaskState = 
  | 'submitted' 
  | 'working' 
  | 'completed' 
  | 'failed' 
  | 'canceled';

export type Role = 'user' | 'agent';

export type PartKind = 'text' | 'data' | 'file' | 'audio' | 'video';

export interface Part {
  kind: PartKind;
  text?: string;
  data?: unknown;
  url?: string;
}

export interface Message {
  message_id: string;
  role: Role;
  parts: Part[];
  context_id?: string;
}

export interface TaskStatus {
  state: TaskState;
  message?: Message;
  timestamp?: string;
}

export interface Task {
  id: string;
  context_id?: string;
  status: TaskStatus;
  artifacts?: Artifact[];
  history?: Message[];
}

export interface Artifact {
  artifact_id: string;
  name: string;
  parts: Part[];
}

export interface SendMessageParams {
  message: Message;
  configuration?: {
    accepted_output_modes?: string[];
    return_immediately?: boolean;
  };
  context_id?: string;
}

export interface SendMessageResponse {
  task: Task;
}

export interface JSONRPCError {
  code: number;
  message: string;
  data?: unknown;
}

export interface JSONRPCRequest {
  jsonrpc: '2.0';
  id: string | number;
  method: string;
  params?: Record<string, unknown>;
}

export interface JSONRPCResponse {
  jsonrpc: '2.0';
  id: string | number;
  result?: SendMessageResponse;
  error?: JSONRPCError;
}

// Streaming events
export type StreamEventType = 
  | 'task'
  | 'status_update'
  | 'artifact_update'
  | 'message';

export interface StreamEvent {
  type: StreamEventType;
  task?: Task;
  status_update?: { state: TaskState };
  artifact?: Artifact;
  message?: Message;
}

// Agent Card
export interface AgentCapabilities {
  streaming?: boolean;
  push_notifications?: boolean;
  extended_agent_card?: boolean;
}

export interface AgentProvider {
  organization: string;
  url?: string;
}

export interface AgentSkill {
  id: string;
  name: string;
  description?: string;
  tags?: string[];
}

export interface AgentCard {
  id: string;
  name: string;
  version: string;
  description?: string;
  url?: string;
  capabilities?: AgentCapabilities;
  provider?: AgentProvider;
  skills?: AgentSkill[];
  default_input_modes?: string[];
  default_output_modes?: string[];
}

// Client options
export interface A2AClientOptions {
  baseUrl: string;
  timeout?: number;
  headers?: Record<string, string>;
}
