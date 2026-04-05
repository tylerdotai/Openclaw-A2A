#!/usr/bin/env node
/**
 * A2A Task Router - Node.js version for systems without Python 3.10+
 * 
 * Usage: node a2a-server.js --agent brad --port 8082
 */

const http = require('http');
const url = require('url');
const { randomUUID } = require('crypto');

const PORT = parseInt(process.argv.find(a => a.startsWith('--port='))?.split('=')[1] || '8080');
const AGENT_ID = process.argv.find(a => a.startsWith('--agent='))?.split('=')[1] || 'unknown';

const AGENT_CARD = {
  id: AGENT_ID,
  name: `${AGENT_ID.charAt(0).toUpperCase() + AGENT_ID.slice(1)} (Node.js A2A)`,
  version: '1.0.0',
  description: `A2A Task Router (Node.js) for ${AGENT_ID}`,
  url: `http://localhost:${PORT}/a2a`,
  capabilities: { streaming: true },
  skills: [
    { id: 'coding', name: 'Coding', description: 'Build and implement' },
    { id: 'research', name: 'Research', description: 'Find and analyze' },
    { id: 'writing', name: 'Writing', description: 'Write content' },
  ],
};

function log(operation, data = {}) {
  const entry = {
    timestamp: new Date().toISOString(),
    service: 'a2a-router-node',
    agent_id: AGENT_ID,
    operation,
    ...data,
  };
  console.log(JSON.stringify(entry));
}

function sendJSONRPC(res, data) {
  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(data));
}

function sendError(res, code, message) {
  res.writeHead(200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify({
    jsonrpc: '2.0',
    id: null,
    error: { code, message }
  }));
}

function routeTask(content) {
  const lower = content.toLowerCase();
  if (lower.includes('build') || lower.includes('code') || lower.includes('implement') || lower.includes('sdk')) {
    return `coding`;
  }
  if (lower.includes('research') || lower.includes('find') || lower.includes('analyze')) {
    return `research`;
  }
  if (lower.includes('write') || lower.includes('content') || lower.includes('blog')) {
    return `writing`;
  }
  if (lower.includes('deploy') || lower.includes('docker') || lower.includes('server')) {
    return `devops`;
  }
  return `generic`;
}

function handleMessage(params) {
  const message = params.message || params;
  const content = message.parts?.[0]?.text || message.parts?.[0] || '';
  const traceId = randomUUID().slice(0, 8);
  const taskId = randomUUID().slice(0, 8);

  log('task_received', { content: String(content).slice(0, 100), trace_id: traceId, task_id: taskId });

  const skill = routeTask(String(content));
  const response = `A2A Node.js Router [${AGENT_ID.toUpperCase()}] Task ${taskId} received.

Skill routed: ${skill}
Trace ID: ${traceId}
Content: ${String(content).slice(0, 200)}

This is a Node.js A2A server running on Python 3.9 system.
Full Python SDK requires Python 3.10+.

Task acknowledged and logged.`;

  log('task_completed', { task_id: taskId, trace_id: traceId, skill });

  return {
    task: {
      id: taskId,
      status: {
        state: 'completed',
        message: {
          message_id: randomUUID(),
          role: 'agent',
          parts: [{ kind: 'text', text: response }],
        },
      },
    },
  };
}

const server = http.createServer((req, res) => {
  const parsedUrl = url.parse(req.url, true);
  const path = parsedUrl.pathname.replace(/\/a2a/, '') || '/';

  // CORS preflight
  if (req.method === 'OPTIONS') {
    res.writeHead(200, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    });
    res.end();
    return;
  }

  let body = '';
  req.on('data', chunk => { body += chunk; });
  req.on('end', () => {
    try {
      // Agent Card endpoint
      if (path === '/agentCard' && req.method === 'GET') {
        return sendJSONRPC(res, AGENT_CARD);
      }

      // Message send endpoint
      if (path === '/message:send' && req.method === 'POST') {
        const rpc = JSON.parse(body);
        if (rpc.method === 'message.send') {
          const result = handleMessage(rpc.params || {});
          return sendJSONRPC(res, {
            jsonrpc: '2.0',
            id: rpc.id,
            result,
          });
        }
      }

      // 404 for everything else
      res.writeHead(404, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'Not found', path }));

    } catch (err) {
      console.error('Error:', err.message);
      sendError(res, -32603, `Internal error: ${err.message}`);
    }
  });
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`A2A Node.js Router [${AGENT_ID}] listening on port ${PORT}`);
  log('server_started', { agent_id: AGENT_ID, port: PORT });
});

process.on('SIGTERM', () => {
  log('server_stopped', { agent_id: AGENT_ID });
  process.exit(0);
});
