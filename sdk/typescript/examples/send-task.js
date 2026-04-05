/**
 * Example: Send a task to an A2A agent (CommonJS / Node.js)
 * 
 * Usage: node examples/send-task.js
 */

const axios = require('axios');

class OpenClawA2AClient {
  constructor(url) {
    this.baseUrl = url.replace(/\/$/, '');
    this.client = axios.create({
      baseURL: this.baseUrl,
      timeout: 30000,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  async sendMessage(params) {
    const request = {
      jsonrpc: '2.0',
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
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

    const response = await this.client.post('/message:send', request);
    if (response.data.error) {
      throw new Error(`${response.data.error.code}: ${response.data.error.message}`);
    }
    return response.data.result;
  }

  async getAgentCard() {
    const response = await this.client.get('/agentCard');
    return response.data;
  }

  close() {}
}

async function main() {
  const client = new OpenClawA2AClient('http://192.168.0.59:8080/a2a');
  console.log('Connected to Dexter A2A server');

  const card = await client.getAgentCard();
  console.log(`Agent: ${card.name} v${card.version}`);

  const result = await client.sendMessage({
    message: {
      message_id: 'example-1',
      role: 'user',
      parts: [{ kind: 'text', text: 'Hello from the JS example' }],
    },
  });

  console.log(`Task: ${result.task.id} | Status: ${result.task.status.state}`);
  if (result.task.artifacts?.[0]?.parts?.[0]?.text) {
    console.log(`Response: ${result.task.artifacts[0].parts[0].text}`);
  }

  client.close();
}

main().catch(console.error);
