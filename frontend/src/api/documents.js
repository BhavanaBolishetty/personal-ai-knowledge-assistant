import { API_BASE_URL, apiFetch, apiFetchNoContent, getToken } from "./client";

export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append("file", file);

  return apiFetch("/documents", {
    method: "POST",
    body: formData,
  });
}

export async function addUrl(url) {
  return apiFetch("/documents/url", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
}

export async function fetchDocuments() {
  return apiFetch("/documents");
}

export async function deleteDocument(id) {
  return apiFetchNoContent(`/documents/${id}`, { method: "DELETE" });
}

export function getDocumentFileUrl(documentId) {
  // Opened directly by the browser (new tab / download), which can't send
  // an Authorization header — the token travels as a query param instead,
  // read by the backend as a fallback when no header is present (see
  // app/api/deps.py). Still requires being logged in; nothing is public.
  const token = getToken();
  const tokenParam = token ? `?token=${encodeURIComponent(token)}` : "";
  return `${API_BASE_URL}/documents/${documentId}/file${tokenParam}`;
}
