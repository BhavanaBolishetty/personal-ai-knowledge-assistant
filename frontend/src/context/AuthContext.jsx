import { createContext, useContext, useEffect, useState } from "react";
import { getCurrentUser, login as apiLogin, signup as apiSignup } from "../api/auth";
import { clearToken, getToken, setToken } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [currentUser, setCurrentUser] = useState(null);
  // Starts true whenever a token is already stored, so App.jsx doesn't
  // flash the login screen for a split second before the /auth/me check
  // (below) confirms an existing session is still valid.
  const [loading, setLoading] = useState(() => Boolean(getToken()));

  useEffect(() => {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    getCurrentUser()
      .then(setCurrentUser)
      .catch(() => {
        // Stored token is expired/invalid — clear it rather than get stuck
        // showing a broken app state on every subsequent load.
        clearToken();
        setCurrentUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  async function login(email, password) {
    const body = await apiLogin(email, password);
    setToken(body.token);
    setCurrentUser(body.user);
  }

  async function signup(email, password) {
    const body = await apiSignup(email, password);
    setToken(body.token);
    setCurrentUser(body.user);
  }

  function logout() {
    clearToken();
    setCurrentUser(null);
  }

  return (
    <AuthContext.Provider value={{ currentUser, loading, login, signup, logout }}>{children}</AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
