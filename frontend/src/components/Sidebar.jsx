import DocumentList from "./DocumentList";
import DocumentUpload from "./DocumentUpload";

function Sidebar({
  open,
  onClose,
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewChat,
  onDeleteConversation,
  documentsRefreshKey,
  onDocumentsChanged,
}) {
  return (
    <>
      {open && <div className="sidebar-backdrop" onClick={onClose} />}
      <aside className={`sidebar${open ? " sidebar-open" : ""}`} aria-hidden={!open}>
        <div className="sidebar-section">
          <button type="button" className="chat-new-button chat-new-button-full" onClick={onNewChat}>
            + New Chat
          </button>

          <h2 className="sidebar-heading">Chats</h2>
          <ul className="conversation-list">
            {conversations.map((conversation) => (
              <li
                key={conversation.id}
                className={`conversation-item${conversation.id === activeConversationId ? " conversation-item-active" : ""}`}
                onClick={() => onSelectConversation(conversation.id)}
              >
                <span className="conversation-title">{conversation.title}</span>
                <button
                  type="button"
                  className="conversation-delete"
                  aria-label="Delete conversation"
                  onClick={(event) => onDeleteConversation(conversation.id, event)}
                >
                  ×
                </button>
              </li>
            ))}
            {conversations.length === 0 && <p className="status">No conversations yet.</p>}
          </ul>
        </div>

        <div className="sidebar-divider" />

        <div className="sidebar-section">
          <h2 className="sidebar-heading">Knowledge</h2>
          <DocumentUpload onUploaded={onDocumentsChanged} />

          <h3 className="sidebar-subheading">Documents</h3>
          <DocumentList refreshKey={documentsRefreshKey} onDeleted={onDocumentsChanged} />
        </div>
      </aside>
    </>
  );
}

export default Sidebar;
