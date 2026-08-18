import { getDocumentFileUrl } from "../api/documents";

// Kept in sync with the backend's own inline/attachment split
// (backend/app/api/documents.py) purely for the UI label — the actual
// open-vs-download behavior is decided server-side via the
// Content-Disposition header, not by anything here.
const DOWNLOAD_ONLY_EXTENSIONS = new Set([".docx"]);

function getExtension(filename) {
  const match = /\.[a-z0-9]+$/i.exec(filename || "");
  return match ? match[0].toLowerCase() : "";
}

export function isDownloadOnly(filename) {
  return DOWNLOAD_ONLY_EXTENSIONS.has(getExtension(filename));
}

export function getOpenActionLabel(filename) {
  return isDownloadOnly(filename) ? "Download" : "Open";
}

// Every source is clickable: a URL source opens the original page; a PDF
// opens the uploaded file at the cited page (if known) via the browser's
// built-in viewer, which honors the #page= fragment; anything else opens
// (or downloads, per the backend's Content-Disposition) the original
// uploaded file. Never exposes internal storage paths — just a
// document-ID-keyed route.
export function getDocumentOpenUrl(documentId, filename, pageStart) {
  const fileUrl = getDocumentFileUrl(documentId);
  if (getExtension(filename) === ".pdf" && pageStart) {
    return `${fileUrl}#page=${pageStart}`;
  }
  return fileUrl;
}
