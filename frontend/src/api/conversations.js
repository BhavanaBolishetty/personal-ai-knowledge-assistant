const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function parseErrorOrReturn(response) {
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const message = body && body.detail ? body.detail : `Request failed with status ${response.status}`;
    throw new Error(message);
  }
  return body;
}

export async function createConversation() {
  const response = await fetch(`${API_BASE_URL}/conversations`, { method: "POST" });
  return parseErrorOrReturn(response);
}

export async function listConversations() {
  const response = await fetch(`${API_BASE_URL}/conversations`);
  return parseErrorOrReturn(response);
}

export async function getConversation(id) {
  const response = await fetch(`${API_BASE_URL}/conversations/${id}`);
  return parseErrorOrReturn(response);
}

export async function deleteConversation(id) {
  const response = await fetch(`${API_BASE_URL}/conversations/${id}`, { method: "DELETE" });
  if (!response.ok) {
    throw new Error(`Could not delete conversation (status ${response.status})`);
  }
}

export async function askInConversation(conversationId, query, topK) {
  const response = await fetch(`${API_BASE_URL}/conversations/${conversationId}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(topK ? { query, top_k: topK } : { query }),
  });
  return parseErrorOrReturn(response);
}
