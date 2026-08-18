import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { askInConversation, createConversation, getConversation } from "../api/conversations";
import { getDocumentOpenUrl, getOpenActionLabel } from "../utils/documentLinks";
import { cleanMathNotation } from "../utils/cleanMarkdown";

const SpeechRecognitionClass =
  typeof window !== "undefined" ? window.SpeechRecognition || window.webkitSpeechRecognition : null;

function SendIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  );
}

function MicIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8" y1="23" x2="16" y2="23" />
    </svg>
  );
}

function StopIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true">
      <rect x="6" y="6" width="12" height="12" rx="2" />
    </svg>
  );
}

function formatPageRange(source) {
  if (source.page_start === null || source.page_start === undefined) {
    return "";
  }
  if (source.page_start === source.page_end) {
    return ` — Page ${source.page_start}`;
  }
  return ` — Pages ${source.page_start}–${source.page_end}`;
}

// Every source is clickable: a URL source opens the original page;
// everything else opens (or, for a DOCX, downloads) the original
// uploaded file via the shared document-link helper.
function getSourceHref(source) {
  return source.source_url || getDocumentOpenUrl(source.document_id, source.filename, source.page_start);
}

// Only http(s) links are ever rendered as clickable — anything else
// (e.g. a javascript: URL smuggled in via retrieved document content)
// renders as plain text instead.
function MarkdownLink({ href, children }) {
  if (typeof href !== "string" || !/^https?:\/\//i.test(href)) {
    return <>{children}</>;
  }
  return (
    <a href={href} target="_blank" rel="noreferrer">
      {children}
    </a>
  );
}

const MARKDOWN_COMPONENTS = { a: MarkdownLink };

function messagesFromConversation(detail) {
  return detail.messages.map((message) => ({
    role: message.role,
    content: message.content,
    sources: message.sources,
    id: message.id,
  }));
}

function ChatMain({ conversationId, onConversationCreated, onConversationChanged }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [voiceError, setVoiceError] = useState("");
  const messagesEndRef = useRef(null);
  const recognitionRef = useRef(null);

  useEffect(() => {
    if (!conversationId) {
      setMessages([]);
      return;
    }
    getConversation(conversationId)
      .then((detail) => setMessages(messagesFromConversation(detail)))
      .catch((err) => setError(err.message));
  }, [conversationId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // Stop any in-progress recognition if the component unmounts mid-listen.
  useEffect(() => {
    return () => recognitionRef.current?.stop();
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isLoading) {
      return;
    }

    setError("");
    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setInput("");
    setIsLoading(true);

    try {
      let activeId = conversationId;
      if (!activeId) {
        const conversation = await createConversation();
        activeId = conversation.id;
        onConversationCreated(conversation);
      }

      const data = await askInConversation(activeId, trimmed);
      setMessages((prev) => [...prev, { role: "assistant", content: data.answer, sources: data.sources }]);
      onConversationChanged(); // picks up the auto-generated title / reordering
    } catch (err) {
      setMessages((prev) => [...prev, { role: "assistant", content: err.message, isError: true }]);
    } finally {
      setIsLoading(false);
    }
  }

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSubmit(event);
    }
  }

  function handleToggleListening() {
    if (!SpeechRecognitionClass) {
      setVoiceError("Voice input isn't supported in this browser — try Chrome or Edge.");
      return;
    }

    if (isListening) {
      recognitionRef.current?.stop();
      return;
    }

    setVoiceError("");
    const recognition = new SpeechRecognitionClass();
    recognition.lang = "en-US";
    recognition.interimResults = true;
    recognition.continuous = false;

    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((result) => result[0].transcript)
        .join("");
      setInput(transcript);
    };

    recognition.onerror = (event) => {
      setVoiceError(
        event.error === "not-allowed"
          ? "Microphone access was denied."
          : "Voice input failed — you can still type your question."
      );
      setIsListening(false);
    };

    recognition.onend = () => setIsListening(false);

    recognitionRef.current = recognition;
    recognition.start();
    setIsListening(true);
  }

  return (
    <main className="chat-main">
      {error && <p className="status status-error">{error}</p>}

      <div className="chat-messages">
        {messages.length === 0 && !isLoading && (
          <p className="status">Ask a question about your uploaded documents to get started.</p>
        )}

        {messages.map((message, index) => (
          <div
            key={message.id || index}
            className={`chat-message chat-message-${message.role}${message.isError ? " chat-message-error" : ""}`}
          >
            <span className="chat-message-role">{message.role === "user" ? "You" : "Assistant"}</span>
            {message.role === "assistant" && !message.isError ? (
              <div className="chat-message-content">
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={MARKDOWN_COMPONENTS}>
                  {cleanMathNotation(message.content)}
                </ReactMarkdown>
              </div>
            ) : (
              <p className="chat-message-content">{message.content}</p>
            )}

            {message.sources && message.sources.length > 0 && (
              <div className="chat-sources">
                <h3>Sources</h3>
                <ul>
                  {message.sources.map((source) => (
                    <li key={source.id}>
                      <span className="ask-source-id">[{source.id}]</span>{" "}
                      <a
                        href={getSourceHref(source)}
                        target="_blank"
                        rel="noreferrer"
                        title={`${getOpenActionLabel(source.filename)} ${source.filename}`}
                      >
                        {source.filename}
                      </a>
                      {formatPageRange(source)}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div className="chat-message chat-message-assistant chat-message-loading">
            <span className="chat-message-role">Assistant</span>
            <p className="chat-message-content">Thinking...</p>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <form className="chat-composer" onSubmit={handleSubmit}>
        {isListening && <p className="chat-voice-status">Listening...</p>}
        {voiceError && <p className="chat-voice-status chat-voice-status-error">{voiceError}</p>}
        <div className="chat-input-row">
          <textarea
            className="chat-input"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask your knowledge base... (Enter to send, Shift+Enter for a new line)"
            rows={1}
          />
          <button
            type="button"
            className={`icon-button chat-mic-button${isListening ? " chat-mic-button-active" : ""}`}
            onClick={handleToggleListening}
            disabled={!SpeechRecognitionClass}
            title={
              SpeechRecognitionClass
                ? isListening
                  ? "Stop listening"
                  : "Ask by voice"
                : "Voice input not supported in this browser"
            }
            aria-label={isListening ? "Stop voice input" : "Start voice input"}
          >
            {isListening ? <StopIcon /> : <MicIcon />}
          </button>
          <button
            type="submit"
            className="icon-button chat-send-button"
            disabled={isLoading || !input.trim()}
            aria-label="Send"
            title="Send"
          >
            <SendIcon />
          </button>
        </div>
      </form>
    </main>
  );
}

export default ChatMain;
