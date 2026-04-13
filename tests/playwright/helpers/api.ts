import { type APIRequestContext } from '@playwright/test';

/**
 * Login via API and return the JWT token.
 */
export async function apiLogin(
  request: APIRequestContext,
  baseUrl: string,
  email: string,
  password: string,
): Promise<string> {
  const response = await request.post(`${baseUrl}/api/v1/auths/signin`, {
    data: { email, password },
  });
  if (!response.ok()) {
    throw new Error(`Login failed (${response.status()}): ${await response.text()}`);
  }
  const body = await response.json();
  return body.token;
}

/**
 * Fetch the list of models visible to the authenticated user.
 */
export async function getModels(
  request: APIRequestContext,
  baseUrl: string,
  token: string,
): Promise<Array<{ id: string; name: string }>> {
  const response = await request.get(`${baseUrl}/api/models`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok()) {
    throw new Error(`Failed to fetch models: ${response.status()}`);
  }
  const body = await response.json();
  return body.data || body;
}

/**
 * Fetch the list of knowledge bases.
 */
export async function getKnowledgeBases(
  request: APIRequestContext,
  baseUrl: string,
  token: string,
): Promise<Array<{ id: string; name: string; description: string }>> {
  const response = await request.get(`${baseUrl}/api/v1/knowledge/`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok()) {
    throw new Error(`Failed to fetch KBs: ${response.status()}`);
  }
  const body = await response.json();
  return body.items || body;
}

/**
 * Fetch the list of users (admin only).
 */
export async function getUsers(
  request: APIRequestContext,
  baseUrl: string,
  token: string,
): Promise<Array<{ id: string; name: string; email: string; role: string }>> {
  const response = await request.get(`${baseUrl}/api/v1/users`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok()) {
    throw new Error(`Failed to fetch users: ${response.status()}`);
  }
  const body = await response.json();
  return body.users || body;
}

/**
 * Fetch full model details (including params, system prompt, function_calling config).
 * Uses GET /api/v1/models/model?id=X which returns the complete model object.
 */
export async function getModelDetail(
  request: APIRequestContext,
  baseUrl: string,
  token: string,
  modelId: string,
): Promise<{
  id: string;
  name: string;
  base_model_id: string | null;
  params: Record<string, unknown>;
  meta: Record<string, unknown>;
  [key: string]: unknown;
}> {
  const response = await request.get(`${baseUrl}/api/v1/models/model?id=${encodeURIComponent(modelId)}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok()) {
    throw new Error(`Failed to fetch model detail for "${modelId}": ${response.status()}`);
  }
  return await response.json();
}

/**
 * Fetch functions/tools list.
 */
export async function getFunctions(
  request: APIRequestContext,
  baseUrl: string,
  token: string,
): Promise<Array<{ id: string; name: string; type: string }>> {
  const response = await request.get(`${baseUrl}/api/v1/functions/`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok()) {
    throw new Error(`Failed to fetch functions: ${response.status()}`);
  }
  return await response.json();
}

/**
 * Send a chat completion request (non-streaming).
 * Returns the assistant message content, or null on failure.
 */
export async function chatCompletion(
  request: APIRequestContext,
  baseUrl: string,
  token: string,
  model: string,
  userMessage: string,
  options?: { files?: Array<{ type: string; id: string }>; timeout?: number },
): Promise<string | null> {
  const body: Record<string, unknown> = {
    model,
    messages: [{ role: 'user', content: userMessage }],
    stream: false,
  };
  if (options?.files) {
    body.files = options.files;
  }
  const response = await request.post(`${baseUrl}/api/chat/completions`, {
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    data: body,
    timeout: options?.timeout ?? 60_000,
  });
  if (!response.ok()) return null;
  const json = await response.json();
  if (!json?.choices?.[0]?.message?.content) return null;
  return json.choices[0].message.content;
}

/**
 * Generate TTS audio. Returns the response size in bytes, or -1 on failure.
 */
export async function generateTTS(
  request: APIRequestContext,
  baseUrl: string,
  token: string,
  text: string,
): Promise<number> {
  const response = await request.post(`${baseUrl}/api/v1/audio/speech`, {
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    data: { input: text },
    timeout: 30_000,
  });
  if (!response.ok()) return -1;
  const buf = await response.body();
  return buf.length;
}

/**
 * Transcribe audio via STT. Returns transcript text, or null on failure.
 */
export async function transcribeAudio(
  request: APIRequestContext,
  baseUrl: string,
  token: string,
  filePath: string,
): Promise<string | null> {
  const fs = await import('fs');
  const path = await import('path');
  const fileBuffer = fs.readFileSync(filePath);
  const fileName = path.basename(filePath);

  const response = await request.post(`${baseUrl}/api/v1/audio/transcriptions`, {
    headers: { Authorization: `Bearer ${token}` },
    multipart: {
      file: { name: fileName, mimeType: 'audio/mpeg', buffer: fileBuffer },
    },
    timeout: 120_000,
  });
  if (!response.ok()) return null;
  const json = await response.json();
  return json.text ?? null;
}

/**
 * Fetch OpenAI connector config (admin only).
 */
export async function getOpenAIConfig(
  request: APIRequestContext,
  baseUrl: string,
  token: string,
): Promise<{ urls: string[]; keys: string[]; configs: Record<string, unknown> }> {
  const response = await request.get(`${baseUrl}/openai/config`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok()) {
    throw new Error(`Failed to fetch OpenAI config: ${response.status()}`);
  }
  const body = await response.json();
  return {
    urls: body.OPENAI_API_BASE_URLS || [],
    keys: body.OPENAI_API_KEYS || [],
    configs: body.OPENAI_API_CONFIGS || {},
  };
}

/**
 * Fetch embedding config.
 */
export async function getEmbeddingConfig(
  request: APIRequestContext,
  baseUrl: string,
  token: string,
): Promise<Record<string, unknown>> {
  const response = await request.get(`${baseUrl}/api/v1/retrieval/embedding`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok()) {
    throw new Error(`Failed to fetch embedding config: ${response.status()}`);
  }
  return await response.json();
}

/**
 * Fetch audio config.
 */
export async function getAudioConfig(
  request: APIRequestContext,
  baseUrl: string,
  token: string,
): Promise<{ tts: Record<string, unknown>; stt: Record<string, unknown> }> {
  const response = await request.get(`${baseUrl}/api/v1/audio/config`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok()) {
    throw new Error(`Failed to fetch audio config: ${response.status()}`);
  }
  return await response.json();
}

/**
 * Fetch image generation config.
 */
export async function getImageConfig(
  request: APIRequestContext,
  baseUrl: string,
  token: string,
): Promise<Record<string, unknown>> {
  const response = await request.get(`${baseUrl}/api/v1/images/config`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok()) {
    throw new Error(`Failed to fetch image config: ${response.status()}`);
  }
  return await response.json();
}

/**
 * Fetch tool server connections.
 */
export async function getToolServers(
  request: APIRequestContext,
  baseUrl: string,
  token: string,
): Promise<Array<Record<string, unknown>>> {
  const response = await request.get(`${baseUrl}/api/v1/configs/tool_servers`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok()) return [];
  const body = await response.json();
  return body.TOOL_SERVER_CONNECTIONS || [];
}

/**
 * Fetch channels list.
 */
export async function getChannels(
  request: APIRequestContext,
  baseUrl: string,
  token: string,
): Promise<Array<{ id: string; name: string }>> {
  const response = await request.get(`${baseUrl}/api/v1/channels/`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok()) return [];
  return await response.json();
}
