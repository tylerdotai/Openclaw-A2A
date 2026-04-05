/**
 * Tests for OpenClaw A2A TypeScript SDK
 */

import { describe, it, expect, vi } from 'vitest';
import { OpenClawA2AClient, A2AError } from '../src/client';

// Mock axios
vi.mock('axios', () => ({
  default: {
    create: () => ({
      post: vi.fn(),
      get: vi.fn(),
    }),
  },
}));

describe('OpenClawA2AClient', () => {
  it('creates a client with base URL', () => {
    const client = new OpenClawA2AClient('http://localhost:8080/a2a');
    expect(client).toBeDefined();
  });

  it('strips trailing slashes from URL', () => {
    const client = new OpenClawA2AClient('http://localhost:8080/a2a/');
    expect(client).toBeDefined();
  });

  it('creates valid JSON-RPC request for sendMessage', async () => {
    const mockPost = vi.fn().mockResolvedValue({
      data: {
        jsonrpc: '2.0',
        id: '1',
        result: {
          task: {
            id: 'task-123',
            status: { state: 'completed' },
          },
        },
      },
    });

    const { default: axios } = require('axios');
    axios.create = () => ({
      post: mockPost,
      get: vi.fn(),
    });

    const client = new OpenClawA2AClient('http://localhost:8080/a2a');
    const result = await client.sendMessage({
      message: {
        message_id: 'msg-1',
        role: 'user',
        parts: [{ kind: 'text', text: 'Hello' }],
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
    const mockPost = vi.fn().mockResolvedValue({
      data: {
        jsonrpc: '2.0',
        id: '1',
        error: {
          code: -32601,
          message: 'Method not found',
        },
      },
    });

    const { default: axios } = require('axios');
    axios.create = () => ({
      post: mockPost,
      get: vi.fn(),
    });

    const client = new OpenClawA2AClient('http://localhost:8080/a2a');

    await expect(
      client.sendMessage({
        message: {
          message_id: 'msg-1',
          role: 'user',
          parts: [{ kind: 'text', text: 'Hello' }],
        },
      })
    ).rejects.toThrow('Method not found');
  });

  it('extracts text from task artifacts', async () => {
    const mockPost = vi.fn().mockResolvedValue({
      data: {
        jsonrpc: '2.0',
        id: '1',
        result: {
          task: {
            id: 'task-456',
            status: { state: 'completed' },
            artifacts: [
              {
                name: 'response',
                parts: [{ kind: 'text', text: 'Hello from agent' }],
              },
            ],
          },
        },
      },
    });

    const { default: axios } = require('axios');
    axios.create = () => ({
      post: mockPost,
      get: vi.fn(),
    });

    const client = new OpenClawA2AClient('http://localhost:8080/a2a');
    const result = await client.sendMessage({
      message: {
        message_id: 'msg-1',
        role: 'user',
        parts: [{ kind: 'text', text: 'Hello' }],
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
