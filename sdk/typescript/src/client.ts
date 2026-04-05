import axios, { AxiosInstance, AxiosError } from 'axios';
import {
  A2AClientOptions,
  Message,
  SendMessageParams,
  SendMessageResponse,
  Task,
  StreamEvent,
  AgentCard,
  JSONRPCRequest,
  JSONRPCResponse,
} from './models';

export class OpenClawA2AClient {
  private client: AxiosInstance;
  private baseUrl: string;

  constructor(url: string, options: Partial<A2AClientOptions> = {}) {
    this.baseUrl = url.replace(/\/$/, '');
    this.client = axios.create({
      baseURL: this.baseUrl,
      timeout: options.timeout ?? 30000,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });
  }

  /**
   * Send a message and wait for completion.
   */
  async sendMessage(params: SendMessageParams): Promise<SendMessageResponse> {
    const request: JSONRPCRequest = {
      jsonrpc: '2.0',
      id: this.generateId(),
      method: 'message.send',
      params: {
        message: params.message,
        configuration: params.configuration ?? {
          accepted_output_modes: ['text/plain', 'application/json'],
          return_immediately: false,
        },
        context_id: params.context_id,
      },
    };

    try {
      const response = await this.client.post<JSONRPCResponse>('/message:send', request);
      
      if (response.data.error) {
        throw new A2AError(
          response.data.error.message,
          response.data.error.code,
          response.data.error.data
        );
      }

      return response.data.result as SendMessageResponse;
    } catch (error) {
      if (error instanceof A2AError) throw error;
      throw this.wrapError(error as Error);
    }
  }

  /**
   * Send a message and stream responses (SSE).
   */
  async *sendMessageStreaming(params: SendMessageParams): AsyncGenerator<StreamEvent> {
    const request: JSONRPCRequest = {
      jsonrpc: '2.0',
      id: this.generateId(),
      method: 'message.send',
      params: {
        message: params.message,
        configuration: {
          ...params.configuration,
          stream: true,
        },
        context_id: params.context_id,
      },
    };

    try {
      const response = await this.client.post('/message:stream', request, {
        responseType: 'stream',
      });

      const stream = response.data as AsyncIterable<string>;

      for await (const chunk of stream) {
        const lines = chunk.toString().split('\n');
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') return;
            try {
              const event = JSON.parse(data) as StreamEvent;
              yield event;
            } catch {
              // Skip malformed JSON
            }
          }
        }
      }
    } catch (error) {
      throw this.wrapError(error as Error);
    }
  }

  /**
   * Get a task by ID.
   */
  async getTask(taskId: string): Promise<Task> {
    const request: JSONRPCRequest = {
      jsonrpc: '2.0',
      id: this.generateId(),
      method: 'tasks.get',
      params: { task_id: taskId },
    };

    try {
      const response = await this.client.post<JSONRPCResponse>('/tasks/' + taskId, request);
      
      if (response.data.error) {
        throw new A2AError(
          response.data.error.message,
          response.data.error.code,
          response.data.error.data
        );
      }

      return (response.data.result as SendMessageResponse).task;
    } catch (error) {
      throw this.wrapError(error as Error);
    }
  }

  /**
   * List tasks with optional filtering.
   */
  async listTasks(options: {
    context_id?: string;
    status?: string;
    limit?: number;
  } = {}): Promise<Task[]> {
    const request: JSONRPCRequest = {
      jsonrpc: '2.0',
      id: this.generateId(),
      method: 'tasks.list',
      params: options,
    };

    try {
      const response = await this.client.post<JSONRPCResponse>('/tasks', request);
      
      if (response.data.error) {
        throw new A2AError(
          response.data.error.message,
          response.data.error.code,
          response.data.error.data
        );
      }

      return (response.data.result as unknown as { tasks: Task[] }).tasks;
    } catch (error) {
      throw this.wrapError(error as Error);
    }
  }

  /**
   * Cancel a task.
   */
  async cancelTask(taskId: string): Promise<Task> {
    const request: JSONRPCRequest = {
      jsonrpc: '2.0',
      id: this.generateId(),
      method: 'tasks.cancel',
      params: { task_id: taskId },
    };

    try {
      const response = await this.client.post<JSONRPCResponse>(`/tasks/${taskId}:cancel`, request);
      
      if (response.data.error) {
        throw new A2AError(
          response.data.error.message,
          response.data.error.code,
          response.data.error.data
        );
      }

      return (response.data.result as SendMessageResponse).task;
    } catch (error) {
      throw this.wrapError(error as Error);
    }
  }

  /**
   * Get the agent card for this server.
   */
  async getAgentCard(): Promise<AgentCard> {
    try {
      const response = await this.client.get<AgentCard>('/agentCard');
      return response.data;
    } catch (error) {
      throw this.wrapError(error as Error);
    }
  }

  /**
   * Close the client (cleanup).
   */
  close(): void {
    // axios doesn't require explicit close
  }

  private generateId(): string {
    return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
  }

  private wrapError(error: Error): A2AError {
    if (error instanceof A2AError) return error;
    
    if (error instanceof AxiosError) {
      if (error.response?.data?.error) {
        return new A2AError(
          error.response.data.error.message,
          error.response.data.error.code,
          error.response.data.error.data
        );
      }
      if (error.code === 'ECONNREFUSED') {
        return new A2AError(`Connection refused: ${this.baseUrl}`, -32000);
      }
      if (error.code === 'ETIMEDOUT') {
        return new A2AError(`Timeout connecting to: ${this.baseUrl}`, -32001);
      }
    }
    
    return new A2AError(error.message, -32003, error);
  }
}

export class A2AError extends Error {
  constructor(
    message: string,
    public code: number,
    public data?: unknown
  ) {
    super(message);
    this.name = 'A2AError';
  }
}

// Default error codes
export const A2A_ERROR_CODES = {
  PARSE_ERROR: -32700,
  INVALID_REQUEST: -32600,
  METHOD_NOT_FOUND: -32601,
  INVALID_PARAMS: -32602,
  INTERNAL_ERROR: -32603,
  SERVER_ERROR: -32000,
  CONNECTION_REFUSED: -32000,
  TIMEOUT: -32001,
  TASK_NOT_FOUND: -32004,
  AGENT_NOT_FOUND: -32005,
} as const;
