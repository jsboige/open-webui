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
  const response = await request.get(`${baseUrl}/api/v1/knowledge`, {
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
  const response = await request.get(`${baseUrl}/api/v1/functions`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok()) {
    throw new Error(`Failed to fetch functions: ${response.status()}`);
  }
  return await response.json();
}
