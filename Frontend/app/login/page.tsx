"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { ErrorMessage, Field, Message } from "../components/ui";
import SsoButtons from "../components/SsoButtons";

export default function LoginPage() {
  const router = useRouter();
  const { setSession } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);
  const [resent, setResent] = useState(false);

  const canResend = error?.code === "email_unverified";

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setResent(false);
    try {
      const res = await api.login(email, password);
      setSession(res.access_token, res.refresh_token, res.user);
      router.push("/dashboard");
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    try {
      await api.resendVerification(email);
      setResent(true);
    } catch {
      setResent(true); // generic response either way
    }
  }

  return (
    <div className="container">
      <div className="card">
        <h1>Welcome back</h1>
        <p className="subtitle">Log in to resume your learning progress.</p>

        <ErrorMessage error={error} />
        {canResend && (
          <Message kind="warn">
            Your email isn&apos;t verified yet.{" "}
            <a onClick={resend} style={{ cursor: "pointer" }}>
              Resend verification email
            </a>
            {resent && " — sent!"}
          </Message>
        )}

        <form onSubmit={submit}>
          <Field
            label="Email"
            type="email"
            value={email}
            required
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
          />
          <Field
            label="Password"
            type="password"
            value={password}
            required
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
          />
          <div style={{ textAlign: "right", marginBottom: 16 }}>
            <Link href="/forgot-password" style={{ fontSize: 13 }}>
              Forgot password?
            </Link>
          </div>
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? "Logging in…" : "Log in"}
          </button>
        </form>

        <div className="divider">or</div>
        <SsoButtons
          onSuccess={(res) => {
            setSession(res.access_token, res.refresh_token, res.user);
            router.push("/dashboard");
          }}
        />

        <p className="helper">
          New here? <Link href="/register">Create an account</Link>
        </p>
      </div>
    </div>
  );
}
