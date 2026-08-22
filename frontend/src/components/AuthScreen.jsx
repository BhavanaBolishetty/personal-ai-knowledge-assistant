import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import "./AuthScreen.css";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MIN_PASSWORD_LENGTH = 8;
const PASSWORD_HINT = `At least ${MIN_PASSWORD_LENGTH} characters, with an uppercase letter, a lowercase letter, a number, and a symbol.`;

// Mirrors the backend's own rule (SignupRequest.validate_password_strength
// in app/api/schemas.py) — this is just the fast client-side check; the
// backend enforces the same rule regardless, since anything could call the
// API directly without going through this form at all.
function getPasswordIssues(password) {
  const issues = [];
  if (password.length < MIN_PASSWORD_LENGTH) issues.push(`at least ${MIN_PASSWORD_LENGTH} characters`);
  if (!/[A-Z]/.test(password)) issues.push("an uppercase letter");
  if (!/[a-z]/.test(password)) issues.push("a lowercase letter");
  if (!/\d/.test(password)) issues.push("a number");
  if (!/[^A-Za-z0-9]/.test(password)) issues.push("a symbol");
  return issues;
}

function validate(mode, { email, password, confirmPassword }) {
  const fieldErrors = {};

  if (!EMAIL_PATTERN.test(email.trim())) {
    fieldErrors.email = "Enter a valid email address.";
  }

  if (mode === "signup") {
    const issues = getPasswordIssues(password);
    if (issues.length > 0) {
      fieldErrors.password = `Password needs ${issues.join(", ")}.`;
    }
  } else if (!password) {
    fieldErrors.password = "Enter your password.";
  }

  if (mode === "signup" && password !== confirmPassword) {
    fieldErrors.confirmPassword = "Passwords don't match.";
  }

  return fieldErrors;
}

function AuthScreen() {
  const { login, signup } = useAuth();
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setFormError("");

    const errors = validate(mode, { email, password, confirmPassword });
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) {
      return;
    }

    setIsSubmitting(true);
    try {
      if (mode === "login") {
        await login(email.trim(), password);
      } else {
        await signup(email.trim(), password);
      }
    } catch (err) {
      // Server-side failures (wrong password, duplicate email on signup,
      // etc.) — client-side validation above already ruled out malformed
      // input, so anything reaching here is a real response from the API.
      setFormError(err.message || "Something went wrong. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  function switchMode() {
    setMode((current) => (current === "login" ? "signup" : "login"));
    setFormError("");
    setFieldErrors({});
    setPassword("");
    setConfirmPassword("");
  }

  const isLogin = mode === "login";

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <h1 className="auth-title">Personal AI Knowledge Assistant</h1>
        <p className="auth-heading">{isLogin ? "Welcome back" : "Create your account"}</p>
        <p className="auth-subtitle">
          {isLogin
            ? "Log in to see your documents and conversations."
            : "Your documents and conversations will be private to this account."}
        </p>

        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          <label className="auth-field">
            <span>Email</span>
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className={fieldErrors.email ? "auth-input-invalid" : ""}
              autoComplete="email"
              autoFocus
            />
            {fieldErrors.email && <p className="auth-field-error">{fieldErrors.email}</p>}
          </label>

          <label className="auth-field">
            <span>Password</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className={fieldErrors.password ? "auth-input-invalid" : ""}
              autoComplete={isLogin ? "current-password" : "new-password"}
            />
            {fieldErrors.password && <p className="auth-field-error">{fieldErrors.password}</p>}
            {!isLogin && !fieldErrors.password && <p className="field-hint">{PASSWORD_HINT}</p>}
          </label>

          {!isLogin && (
            <label className="auth-field">
              <span>Confirm Password</span>
              <input
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                className={fieldErrors.confirmPassword ? "auth-input-invalid" : ""}
                autoComplete="new-password"
              />
              {fieldErrors.confirmPassword && <p className="auth-field-error">{fieldErrors.confirmPassword}</p>}
            </label>
          )}

          {formError && <p className="status status-error">{formError}</p>}

          <button type="submit" className="auth-submit" disabled={isSubmitting}>
            {isSubmitting ? "Please wait…" : isLogin ? "Log In" : "Create Account"}
          </button>
        </form>

        <button type="button" className="auth-switch" onClick={switchMode}>
          {isLogin ? "Don't have an account? Sign up" : "Already have an account? Log in"}
        </button>
      </div>
    </div>
  );
}

export default AuthScreen;
