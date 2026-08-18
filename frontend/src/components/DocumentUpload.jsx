import { useRef, useState } from "react";
import { addUrl, uploadDocument } from "../api/documents";

function InfoTooltip({ text }) {
  return (
    <span className="info-tooltip" tabIndex={0} role="img" aria-label="More information" title={text}>
      ⓘ
    </span>
  );
}

function DocumentUpload({ onUploaded }) {
  const [status, setStatus] = useState("idle"); // idle | busy | success | error
  const [message, setMessage] = useState("");
  const [url, setUrl] = useState("");
  const fileInputRef = useRef(null);

  async function handleFileChange(event) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    setStatus("busy");
    setMessage("");

    try {
      const document = await uploadDocument(file);
      if (document.status === "failed") {
        setStatus("error");
        setMessage(document.error_message || "Processing failed.");
      } else {
        setStatus("success");
        setMessage(`"${document.original_filename}" uploaded.`);
      }
      onUploaded();
    } catch (err) {
      setStatus("error");
      setMessage(err.message);
    } finally {
      event.target.value = "";
    }
  }

  async function handleUrlSubmit(event) {
    event.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) {
      return;
    }

    setStatus("busy");
    setMessage("");

    try {
      const document = await addUrl(trimmed);
      if (document.status === "failed") {
        setStatus("error");
        setMessage(document.error_message || "Could not process that page.");
      } else {
        setStatus("success");
        setMessage(`"${document.original_filename}" added.`);
      }
      onUploaded();
      setUrl("");
    } catch (err) {
      setStatus("error");
      setMessage(err.message);
    }
  }

  return (
    <div className="knowledge-actions">
      <input
        ref={fileInputRef}
        type="file"
        className="visually-hidden-file-input"
        accept=".pdf,.txt,.md,.markdown,.docx,.png,.jpg,.jpeg,.webp"
        onChange={handleFileChange}
        disabled={status === "busy"}
      />
      <div className="knowledge-action-row">
        <button
          type="button"
          className="knowledge-action-button"
          onClick={() => fileInputRef.current?.click()}
          disabled={status === "busy"}
        >
          Upload File
        </button>
        <InfoTooltip text="Supports PDF, Word (.docx), text, Markdown, and images (PNG/JPG/WEBP)." />
      </div>

      <form className="url-form" onSubmit={handleUrlSubmit}>
        <input
          type="url"
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          placeholder="Paste a URL..."
          disabled={status === "busy"}
        />
        <button type="submit" className="knowledge-action-button" disabled={status === "busy" || !url.trim()}>
          Add URL
        </button>
      </form>
      <p className="field-hint">Public pages only.</p>

      {status !== "idle" && status !== "busy" && (
        <p className={`status ${status === "error" ? "status-error" : "status-ok"}`}>{message}</p>
      )}
    </div>
  );
}

export default DocumentUpload;
