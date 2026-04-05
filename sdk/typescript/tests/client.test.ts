/**
 * Tests for OpenClaw A2A TypeScript SDK
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { OpenClawA2AClient, A2AError } from '../src/client';

const { mockPost, mockGet, mockCreate } = vi.hoisted(() => {
  const post = vi.fn();
  const get = vi.fn();
  const create = vi.fn(() => ({ post, get }));
  return { mockPost: post, mockGet: get, mockCreate: create };
});

vi.mock('axios', async (importOriginal) => {
  const actual = await importOriginal<typeof import('axios')>();
  return {
    __esModule: true,
    default: {
      ...actual.default,
      create: mockCreate,
    },
    AxiosError: actual.AxiosError,
  };
});

describe('OpenClawA2AClient', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('creates a client with base URL', () => {
    const client = new OpenClawA2AClient('http://localhost:8080/a2a');
    expect(client).toBeDefined();
    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({ baseURL: 'http://localhost:8080/a2a' })
    );
  });

  it('strips trailing slashes from URL', () => {
    const client = new OpenClawA2AClient('http://localhost:8080/a2a/');
    expect(client).toBeDefined();
    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({ baseURL: 'http://localhost:8080/a2a' })
    );
  });

  it('sends a message and returns task result', async () => {
    const mockTask = {
      id: 'task-123',
      status: { state: 'completed' as const },
    };

    mockPost.mockResolvedValueOnce({
      data: {
        jsonrpc: '2.0',
        id: '1',
        result: { task: mockTask },
      },
    });

    const client = new OpenClawA2AClient('http://localhost:8080/a2a');
    const result = await client.sendMessage({
      message: {
        message_id: 'msg-1',
        role: 'user' as const,
        parts: [{ kind: 'text' as const, text: 'Hello' }],
      },
    });

    expect(result.task.id).toBe('task-123');
    expect(mockPost).toHaveBeenCalledWith(
      '/message:send',
      expect.objectContaining({
        jsonrpc: '2.0',
        method: 'message.send',
      })
    );
  });

  it('throws A2AError on JSON-RPC error response', async () => {
    mockPost.mockResolvedValueOnce({
      data: {
        jsonrpc: '2.0',
        id: '1',
        error: {
          code: -32601,
          message: 'Method not found',
        },
      },
    });

    const client = new OpenClawA2AClient('http://localhost:8080/a2a');

    await expect(
      client.sendMessage({
        message: {
          message_id: 'msg-1',
          role: 'user' as const,
          parts: [{ kind: 'text' as const, text: 'Hello' }],
        },
      })
    ).rejects.toThrow('Method not found');
  });

  it('extracts text from task artifacts', async () => {
    mockPost.mockResolvedValueOnce({
      data: {
        jsonrpc: '2.0',
        id: '1',
        result: {
          task: {
            id: 'task-456',
            status: { state: 'completed' as const },
            artifacts: [
              {
                name: 'response',
                parts: [{ kind: 'text' as const, text: 'Hello from agent' }],
              },
            ],
          },
        },
      },
    });

    const client = new OpenClawA2AClient('http://localhost:8080/a2a');
    const result = await client.sendMessage({
      message: {
        message_id: 'msg-1',
        role: 'user' as const,
        parts: [{ kind: 'text' as const, text: 'Hello' }],
      },
    });

    expect(result.task.artifacts?.[0]?.parts?.[0]?.text).toBe('Hello from agent');
  });
});

describe('A2AError', () => {
  it('creates error with code and message', () => {
    const error = new A2AError('Not found', 404);
    expect(error.message).toBe('Not found');
    expect(error.code).toBe(404);
    expect(error.name).toBe('A2AError');
  });

  it('includes optional data', () => {
    const error = new A2AError('Error', 500, { details: 'extra info' });
    expect(error.data).toEqual({ details: 'extra info' });
  });
});
