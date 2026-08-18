import { useEffect, useState } from "react";
import ChatMain from "./components/ChatMain";
import Sidebar from "./components/Sidebar";
import { deleteConversation, listConversations } from "./api/conversations";
import "./App.css";

const ACTIVE_CONVERSATION_KEY = "paika:activeConversationId";

function HamburgerIcon({ open }) {
  if (open) {
    return (
      <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
        <line x1="5" y1="5" x2="19" y2="19" />
        <line x1="19" y1="5" x2="5" y2="19" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <line x1="3" y1="6" x2="21" y2="6" />
      <line x1="3" y1="12" x2="21" y2="12" />
      <line x1="3" y1="18" x2="21" y2="18" />
    </svg>
  );
}

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(
    () => localStorage.getItem(ACTIVE_CONVERSATION_KEY) || null
  );
  const [documentsRefreshKey, setDocumentsRefreshKey] = useState(0);

  async function refreshConversationList() {
    try {
      const list = await listConversations();
      setConversations(list);
      return list;
    } catch {
      return [];
    }
  }

  // Load the conversation list once, and restore whichever conversation
  // was open before a refresh (if it still exists).
  useEffect(() => {
    refreshConversationList().then((list) => {
      if (activeConversationId && !list.some((c) => c.id === activeConversationId)) {
        setActiveConversationId(null);
        localStorage.removeItem(ACTIVE_CONVERSATION_KEY);
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function selectConversation(id) {
    setActiveConversationId(id);
    localStorage.setItem(ACTIVE_CONVERSATION_KEY, id);
    setSidebarOpen(false);
  }

  function handleNewChat() {
    setActiveConversationId(null);
    localStorage.removeItem(ACTIVE_CONVERSATION_KEY);
    setSidebarOpen(false);
  }

  async function handleDeleteConversation(id, event) {
    event.stopPropagation();
    if (!window.confirm("Delete this conversation? This cannot be undone.")) {
      return;
    }
    try {
      await deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (id === activeConversationId) {
        setActiveConversationId(null);
        localStorage.removeItem(ACTIVE_CONVERSATION_KEY);
      }
    } catch {
      // The conversation list will simply retain the (now stale) entry;
      // the user can retry the delete from the sidebar.
    }
  }

  function handleConversationCreated(conversation) {
    setConversations((prev) => [conversation, ...prev]);
    selectConversation(conversation.id);
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <button
          type="button"
          className="icon-button hamburger-button"
          onClick={() => setSidebarOpen((open) => !open)}
          aria-label={sidebarOpen ? "Close menu" : "Open menu"}
          title={sidebarOpen ? "Close menu" : "Open menu"}
        >
          <HamburgerIcon open={sidebarOpen} />
        </button>
        <h1>Personal AI Knowledge Assistant</h1>
      </header>

      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelectConversation={selectConversation}
        onNewChat={handleNewChat}
        onDeleteConversation={handleDeleteConversation}
        documentsRefreshKey={documentsRefreshKey}
        onDocumentsChanged={() => setDocumentsRefreshKey((key) => key + 1)}
      />

      <ChatMain
        conversationId={activeConversationId}
        onConversationCreated={handleConversationCreated}
        onConversationChanged={refreshConversationList}
      />
    </div>
  );
}

export default App;
