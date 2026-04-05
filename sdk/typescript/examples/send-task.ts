/**
 * Example: Send a task to an A2A agent
 * 
 * Usage: npx ts-node examples/send-task.ts
 */

import { OpenClawA2AClient } from '../src/client';

async function main() {
  // Connect to Dexter
  const client = new OpenClawA2AClient('http://192.168.0.59:8080/a2a');

  console.log('Connected to Dexter A2A server');

  // Get agent info
  const card = await client.getAgentCard();
  console.log(`Agent: ${card.name} v${card.version}`);
  console.log(`Skills: ${card.skills?.map(s => s.name).join(', ')}`);

  // Send a task
  console.log('\nSending task...');
  const result = await client.sendMessage({
    message: {
      message_id: 'example-1',
      role: 'user',
      parts: [{ kind: 'text', text: 'Hello, this is a test message' }],
    },
    configuration: {
      accepted_output_modes: ['text/plain'],
      return_immediately: false,
    },
  });

  console.log(`Task ID: ${result.task.id}`);
  console.log(`Status: ${result.task.status.state}`);

  if (result.task.artifacts) {
    for (const artifact of result.task.artifacts) {
      for (const part of artifact.parts) {
        if (part.text) {
          console.log(`\nResponse: ${part.text}`);
        }
      }
    }
  }

  client.close();
}

main().catch(console.error);
