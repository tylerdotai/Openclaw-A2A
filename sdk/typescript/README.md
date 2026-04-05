# OpenClaw A2A TypeScript SDK

TypeScript/JavaScript SDK for OpenClaw A2A agent communication.

## Installation

```bash
npm install @flume-a2a/sdk
```

## Usage

```typescript
import { OpenClawA2AClient } from '@flume-a2a/sdk';

const client = new OpenClawA2AClient('http://192.168.0.59:8080/a2a');

// Send a task
const result = await client.sendMessage({
  role: 'user',
  parts: [{ kind: 'text', text: 'Build a REST API' }]
});

// Stream responses
for await (const event of client.sendMessageStreaming({ ... })) {
  console.log(event);
}
```

## API

See full docs at [OpenClaw-A2A](https://github.com/tylerdotai/Openclaw-A2A)
