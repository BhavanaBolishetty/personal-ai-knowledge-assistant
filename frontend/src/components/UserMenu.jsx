import { useEffect, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";
import "./UserMenu.css";

function LogoutIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  );
}

// A small avatar button that reveals the account email + logout in a
// dropdown on click — nothing shown by default, no separate account page.
// Standard pattern (Gmail/Slack-style), matches the app's existing plain
// CSS/no-router conventions rather than introducing a real route for it.
function UserMenu() {
  const { currentUser, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const containerRef = useRef(null);

  useEffect(() => {
    if (!open) return;

    function handleClickOutside(event) {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setOpen(false);
      }
    }

    function handleEscape(event) {
      if (event.key === "Escape") setOpen(false);
    }

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [open]);

  const initial = currentUser.email.trim().charAt(0).toUpperCase();

  return (
    <div className="user-menu" ref={containerRef}>
      <button
        type="button"
        className="user-menu-avatar"
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="true"
        aria-expanded={open}
        aria-label="Account menu"
        title={currentUser.email}
      >
        {initial}
      </button>

      {open && (
        <div className="user-menu-dropdown" role="menu">
          <p className="user-menu-email">{currentUser.email}</p>
          <button
            type="button"
            className="user-menu-logout"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              logout();
            }}
          >
            <LogoutIcon />
            <span>Log out</span>
          </button>
        </div>
      )}
    </div>
  );
}

export default UserMenu;
