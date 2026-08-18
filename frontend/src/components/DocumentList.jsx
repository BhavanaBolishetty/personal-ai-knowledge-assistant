import { useEffect, useMemo, useState } from "react";
import { deleteDocument, fetchDocuments } from "../api/documents";
import { getDocumentOpenUrl, getOpenActionLabel } from "../utils/documentLinks";

const STATUS_BADGE = {
  completed: { symbol: "✓", className: "document-badge-completed" },
  failed: { symbol: "✗", className: "document-badge-failed" },
  processing: { symbol: "···", className: "document-badge-pending" },
  uploaded: { symbol: "···", className: "document-badge-pending" },
};

function formatUploadDate(isoString) {
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function DocumentList({ refreshKey, onDeleted }) {
  const [documents, setDocuments] = useState([]);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    fetchDocuments()
      .then(setDocuments)
      .catch((err) => setError(err.message));
  }, [refreshKey]);

  const filteredDocuments = useMemo(() => {
    const query = filter.trim().toLowerCase();
    if (!query) return documents;
    return documents.filter((doc) => doc.original_filename.toLowerCase().includes(query));
  }, [documents, filter]);

  async function handleDelete(id, event) {
    event.preventDefault();
    event.stopPropagation();
    if (!window.confirm("Delete this document? This removes it and its knowledge permanently.")) {
      return;
    }
    try {
      await deleteDocument(id);
      onDeleted();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="knowledge-documents">
      {error && <p className="status status-error">Could not load documents: {error}</p>}

      {!error && documents.length === 0 && <p className="status">No documents yet.</p>}

      {documents.length > 5 && (
        <input
          type="search"
          className="document-filter"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          placeholder="Filter documents..."
        />
      )}

      {documents.length > 0 && (
        <ul className="document-list">
          {filteredDocuments.map((doc) => {
            const badge = STATUS_BADGE[doc.status] || STATUS_BADGE.uploaded;
            const href = doc.source_url || getDocumentOpenUrl(doc.id, doc.original_filename);
            return (
              <li key={doc.id} className="document-item" title={doc.error_message || undefined}>
                <span className="document-type-icon" aria-hidden="true">
                  {doc.source_url ? "🔗" : "📄"}
                </span>
                <div className="document-info">
                  <a
                    className="document-name"
                    href={href}
                    target="_blank"
                    rel="noreferrer"
                    title={doc.source_url ? href : `${getOpenActionLabel(doc.original_filename)} ${doc.original_filename}`}
                  >
                    {doc.original_filename}
                  </a>
                  <span className="document-meta">Uploaded {formatUploadDate(doc.uploaded_at)}</span>
                </div>
                <span className={`document-badge ${badge.className}`}>{badge.symbol}</span>
                <button
                  type="button"
                  className="document-delete"
                  aria-label={`Delete ${doc.original_filename}`}
                  onClick={(event) => handleDelete(doc.id, event)}
                >
                  ×
                </button>
              </li>
            );
          })}
          {filteredDocuments.length === 0 && (
            <p className="status">No documents match "{filter}".</p>
          )}
        </ul>
      )}
    </div>
  );
}

export default DocumentList;
