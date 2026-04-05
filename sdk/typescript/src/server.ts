/**
 * OpenClaw A2A Server — TypeScript Implementation
 *
 * HTTP/JSON-RPC 2.0 server for A2A agents.
 * Handles: message.send, tasks.get, tasks.list, tasks.cancel, streaming, subscriptions.
 */

import {
  AgentCard,
  Task,
  TaskStatus,
  TaskState,
  Message,
  Part,
  SendMessageResponse,
  StreamEvent,
  JSONRPCRequest,
  JSONRPCResponse,
  JSONRPCError,
} from './models.js';

// ── Error codes (must match Python SDK) ────────────────────────────────────────

export const A2A_ERROR_CODES = {
  PARSE_ERROR: -32700,
  INVALID_REQUEST: -32600,
  METHOD_NOT_FOUND: -32601,
  INVALID_PARAMS: -32602,
  INTERNAL_ERROR: -32603,
  AUTH_REQUIRED: -32001,
  INPUT_REQUIRED: -32002,
  TASK_NOT_FOUND: -32003,
  RATE_LIMITED: -32004,
  UNSUPPORTED_OPERATION: -32005,
} as const;

export type A2AErrorCode = typeof A2A_ERROR_CODES[keyof typeof A2A_ERROR_CODES];

// ── Message handler ───────────────────────────────────────────────────────────

export type MessageHandler = (
  message: Message,
  context: Record<string, unknown>
) => Promise<Message>;

// ── Task store ────────────────────────────────────────────────────────────────

export class InMemoryTaskStore {
  private tasks = new Map<string, Task>();
  private byContext = new Map<string, string[]>();

  async save(task: Task): Promise<void> {
    this.tasks.set(task.id, task);
    if (task.context_id) {
      const existing = this.byContext.get(task.context_id) ?? [];
      if (!existing.includes(task.id)) {
        existing.push(task.id);
        this.byContext.set(task.context_id, existing);
      }
    }
  }

  async get(taskId: string): Promise<Task | null> {
    return this.tasks.get(taskId) ?? null;
  }

  async list(contextId?: string, limit = 20): Promise<Task[]> {
    let ids: string[];
    if (contextId) {
      ids = this.byContext.get(contextId) ?? [];
    } else {
      ids = [...this.tasks.keys()];
    }
    return ids
      .slice(-limit)
      .map(id => this.tasks.get(id)!)
      .filter(Boolean);
  }

  async delete(taskId: string): Promise<void> {
    this.tasks.delete(taskId);
  }
}

// ── SSE streaming ─────────────────────────────────────────────────────────────

export type StreamSubscriber = (event: StreamEvent) => void;

export class StreamManager {
  private subscribers = new Map<string, Set<StreamSubscriber>>();

  subscribe(taskId: string, subscriber: StreamSubscriber): () => void {
    const subs = this.subscribers.get(taskId) ?? new Set();
    subs.add(subscriber);
    this.subscribers.set(taskId, subs);
    return () => subs.delete(subscriber);
  }

  async emit(taskId: string, event: StreamEvent): Promise<void> {
    const subs = this.subscribers.get(taskId);
    if (!subs) return;
    await Promise.all([...subs].map(fn => fn(event)));
  }

  async emitTaskUpdate(taskId: string, state: TaskState): Promise<void> {
    await this.emit(taskId, { type: 'status_update', status_update: { state } });
  }
}

// ── A2A Server ────────────────────────────────────────────────────────────────

export interface A2AServerOptions {
  agentCard: AgentCard;
  messageHandler?: MessageHandler;
  taskStore?: InMemoryTaskStore;
  streamManager?: StreamManager;
}

export class A2AServer {
  private _agentCard: AgentCard;
  private messageHandler?: MessageHandler;
  private taskStore: InMemoryTaskStore;
  private streamManager: StreamManager;

  constructor(options: A2AServerOptions) {
    this._agentCard = options.agentCard;
    this.messageHandler = options.messageHandler;
    this.taskStore = options.taskStore ?? new InMemoryTaskStore();
    this.streamManager = options.streamManager ?? new StreamManager();
  }

  // ── Route handlers ─────────────────────────────────────────────────────────

  /**
   * Handle GET /agent-card
   */
  async handleGetAgentCard(): Promise<{ status: number; body: AgentCard }> {
    return { status: 200, body: this._agentCard };
  }

  /**
   * Handle POST /message:send
   */
  async handleSendMessage(body: JSONRPCRequest): Promise<{ status: number; body: JSONRPCResponse }> {
    try {
      if (!body.params || typeof body.params !== 'object') {
        return this.errorResponse(body.id, A2A_ERROR_CODES.INVALID_REQUEST, 'Invalid params');
      }

      const params = body.params as Record<string, unknown>;
      const message = params.message as Message;
      if (!message) {
        return this.errorResponse(body.id, A2A_ERROR_CODES.INVALID_PARAMS, 'message required');
      }

      const context_id = params.context_id as string | undefined;
      const task_id = (params.task_id as string | undefined) ?? `task-${Date.now()}`;
      const stream = (params.stream as boolean) ?? false;

      let task = await this.taskStore.get(task_id);
      if (!task) {
        task = {
          id: task_id,
          context_id: context_id ?? `ctx-${Date.now()}`,
          status: { state: 'submitted' as TaskState, timestamp: new Date().toISOString() },
        };
        await this.taskStore.save(task);
      }

      // Update to WORKING
      task.status = { state: 'working' as TaskState, timestamp: new Date().toISOString() };
      await this.taskStore.save(task);

      // Emit working state if streaming
      if (stream) {
        await this.streamManager.emitTaskUpdate(task_id, 'working');
      }

      // Handle message
      let responseMsg: Message;
      if (this.messageHandler) {
        responseMsg = await this.messageHandler(message, { task_id, context_id });
      } else {
        // Default: echo back
        responseMsg = message;
      }

      // Mark completed
      task.status = { state: 'completed' as TaskState, timestamp: new Date().toISOString(), message: responseMsg };
      await this.taskStore.save(task);

      if (stream) {
        await this.streamManager.emitTaskUpdate(task_id, 'completed');
      }

      const result: SendMessageResponse = { task };
      return {
        status: 200,
        body: { jsonrpc: '2.0', id: body.id, result },
      };
    } catch (err) {
      return this.errorResponse(
        body.id,
        A2A_ERROR_CODES.INTERNAL_ERROR,
        err instanceof Error ? err.message : 'Internal error'
      );
    }
  }

  /**
   * Handle GET /tasks/{taskId}
   */
  async handleGetTask(taskId: string): Promise<{ status: number; body: JSONRPCResponse }> {
    const task = await this.taskStore.get(taskId);
    if (!task) {
      return {
        status: 404,
        body: {
          jsonrpc: '2.0',
          id: null,
          error: {
            code: A2A_ERROR_CODES.TASK_NOT_FOUND,
            message: `Task not found: ${taskId}`,
          },
        },
      };
    }
    return {
      status: 200,
      body: {
        jsonrpc: '2.0',
        id: null,
        result: { task },
      },
    };
  }

  /**
   * Handle GET /tasks?context_id=...
   */
  async handleListTasks(query: Record<string, string>): Promise<{ status: number; body: JSONRPCResponse }> {
    const context_id = query.context_id;
    const limit = parseInt(query.limit ?? '20', 10);
    const tasks = await this.taskStore.list(context_id, limit);
    return {
      status: 200,
      body: {
        jsonrpc: '2.0',
        id: null,
        result: { tasks } as unknown as SendMessageResponse,
      },
    };
  }

  /**
   * Handle POST /tasks/{taskId}:cancel
   */
  async handleCancelTask(
    taskId: string
  ): Promise<{ status: number; body: JSONRPCResponse }> {
    const task = await this.taskStore.get(taskId);
    if (!task) {
      return {
        status: 404,
        body: {
          jsonrpc: '2.0',
          id: null,
          error: {
            code: A2A_ERROR_CODES.TASK_NOT_FOUND,
            message: `Task not found: ${taskId}`,
          },
        },
      };
    }
    task.status = { state: 'canceled' as TaskState, timestamp: new Date().toISOString() };
    await this.taskStore.save(task);
    await this.streamManager.emitTaskUpdate(taskId, 'canceled');
    return {
      status: 200,
      body: { jsonrpc: '2.0', id: null, result: { task } },
    };
  }

  // ── Central router ─────────────────────────────────────────────────────────

  async handleRequest(
    method: string,
    path: string,
    body: JSONRPCRequest | null,
    query: Record<string, string> = {}
  ): Promise<{ status: number; body: unknown }> {
    // GET /agent-card
    if (method === 'GET' && path === '/agent-card') {
      return this.handleGetAgentCard();
    }

    // GET /tasks (list)
    if (method === 'GET' && path === '/tasks') {
      return this.handleListTasks(query);
    }

    // GET /tasks/{id}:subscribe (SSE subscription)
    if (method === 'GET' && path.match(/^\/tasks\/([^:]+):subscribe$/)) {
      const taskId = path.match(/^\/tasks\/([^:]+):subscribe$/)![1];
      return { status: 200, body: { type: 'subscribe', task_id: taskId } };
    }

    // GET /tasks/{id}
    if (method === 'GET' && path.match(/^\/tasks\/([^/]+)$/)) {
      const taskId = path.match(/^\/tasks\/([^/]+)$/)![1];
      return this.handleGetTask(taskId);
    }

    // POST /tasks/{id}:cancel
    if (method === 'POST' && path.match(/^\/tasks\/([^:]+):cancel$/)) {
      const taskId = path.match(/^\/tasks\/([^:]+):cancel$/)![1];
      return this.handleCancelTask(taskId);
    }

    // POST /message:send
    if (method === 'POST' && path === '/message:send') {
      return this.handleSendMessage(body!);
    }

    return {
      status: 404,
      body: { error: 'Not found', path },
    };
  }

  // ── Helpers ────────────────────────────────────────────────────────────────

  private errorResponse(
    id: string | number | null,
    code: A2AErrorCode,
    message: string
  ): { status: number; body: JSONRPCResponse } {
    return {
      status: code < -32000 ? 400 : 500,
      body: {
        jsonrpc: '2.0',
        id: id ?? null,
        error: { code, message },
      },
    };
  }

  get agentCard(): AgentCard {
    return this._agentCard;
  }
}
