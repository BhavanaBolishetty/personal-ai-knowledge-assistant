const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/documents`, {
    method: "POST",
    body: formData,
  });

  const body = await response.json().catch(() => null);

  if (!response.ok) {
    const message = body && body.detail ? body.detail : `Upload failed with status ${response.status}`;
    throw new Error(message);
  }

  return body;
}

export async function addUrl(url) {
  const response = await fetch(`${API_BASE_URL}/documents/url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });

  const body = await response.json().catch(() => null);

  if (!response.ok) {
    const message = body && body.detail ? body.detail : `Could not add URL (status ${response.status})`;
    throw new Error(message);
  }

  return body;
}

export async function fetchDocuments() {
  const response = await fetch(`${API_BASE_URL}/documents`);
  if (!response.ok) {
    throw new Error(`Failed to load documents (status ${response.status})`);
  }
  return response.json();
}

export async function deleteDocument(id) {
  const response = await fetch(`${API_BASE_URL}/documents/${id}`, { method: "DELETE" });
  if (!response.ok) {
    throw new Error(`Could not delete document (status ${response.status})`);
  }
}

export function getDocumentFileUrl(documentId) {
  return `${API_BASE_URL}/documents/${documentId}/file`;
}
