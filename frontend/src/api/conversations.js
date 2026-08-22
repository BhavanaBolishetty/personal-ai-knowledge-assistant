import { apiFetch, apiFetchNoContent } from "./client";

export async function createConversation() {
  return apiFetch("/conversations", { method: "POST" });
}

export async function listConversations() {
  return apiFetch("/conversations");
}

export async function getConversation(id) {
  return apiFetch(`/conversations/${id}`);
}

export async function deleteConversation(id) {
  return apiFetchNoContent(`/conversations/${id}`, { method: "DELETE" });
}

export async function askInConversation(conversationId, query, topK) {
  return apiFetch(`/conversations/${conversationId}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(topK ? { query, top_k: topK } : { query }),
  });
}
