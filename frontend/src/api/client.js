const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const TOKEN_KEY = "paika:authToken";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function parseErrorOrReturn(response) {
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const message = body && body.detail ? body.detail : `Request failed with status ${response.status}`;
    throw new Error(message);
  }
  return body;
}

// Shared fetch wrapper: attaches the auth token (if any) to every request,
// so callers in api/documents.js, api/conversations.js, etc. don't each
// need to repeat that logic. Not used for the raw <a>/<img> style URLs
// (e.g. getDocumentFileUrl) that the browser navigates to directly, since
// those can't carry an Authorization header anyway.
export async function apiFetch(path, options = {}) {
  const token = getToken();
  const headers = { ...(options.headers || {}) };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  return parseErrorOrReturn(response);
}

// For DELETE-style calls that return no body — apiFetch's JSON parsing
// would fail on an empty 204 response.
export async function apiFetchNoContent(path, options = {}) {
  const token = getToken();
  const headers = { ...(options.headers || {}) };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const message = body && body.detail ? body.detail : `Request failed with status ${response.status}`;
    throw new Error(message);
  }
}

export { API_BASE_URL };
