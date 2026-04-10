import { useState, FormEvent } from "react";
import { login } from "../api/client";

export default function Login() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(password);
      window.location.href = "/";
    } catch {
      setError("Invalid password");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        maxWidth: 400,
        margin: "120px auto",
        padding: 32,
        border: "1px solid #e0e0e0",
        borderRadius: 8,
      }}
    >
      <h2
        style={{
          margin: "0 0 8px",
          fontSize: 20,
          fontWeight: 700,
          color: "#2e7d32",
        }}
      >
        Plant Tracker
      </h2>
      <p style={{ margin: "0 0 24px", fontSize: 13, color: "#888" }}>
        Enter password to continue
      </p>

      <form onSubmit={handleSubmit}>
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoFocus
          style={{
            width: "100%",
            padding: "10px 12px",
            fontSize: 14,
            border: "1px solid #ccc",
            borderRadius: 4,
            boxSizing: "border-box",
            marginBottom: 12,
          }}
        />
        {error && (
          <p style={{ color: "#d32f2f", fontSize: 13, margin: "0 0 12px" }}>
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={loading || !password}
          style={{
            width: "100%",
            padding: "10px 0",
            fontSize: 14,
            fontWeight: 600,
            color: "#fff",
            backgroundColor: "#2e7d32",
            border: "none",
            borderRadius: 4,
            cursor: loading ? "wait" : "pointer",
            opacity: loading || !password ? 0.6 : 1,
          }}
        >
          {loading ? "Signing in…" : "Sign In"}
        </button>
      </form>
    </div>
  );
}
