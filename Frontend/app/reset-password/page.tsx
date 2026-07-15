"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api, ApiError } from "../lib/api";
import { ErrorMessage, Field, Message, Spinner } from "../components/ui";

function ResetInner() {
  const params = useSearchParams();
  const token = params.get("token") || "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [done, setDone] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password !== confirm) {
      setError({ status: 0, message: "Passwords do not match." });
      return;
    }
    setBusy(true);
    try {
      await api.resetPassword(token, password);
      setDone(true);
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setBusy(false);
    }
  }

  if (!token) {
    return <Message kind="error">This reset link is missing its token.</Message>;
  }

  if (done) {
    return (
      <>
        <Message kind="success">
          Your password has been updated and all other sessions were signed out. Please log in with your new password.
        </Message>
        <Link href="/login">
          <button className="btn-primary">Go to login</button>
        </Link>
      </>
    );
  }

  return (
    <form onSubmit={submit}>
      <ErrorMessage error={error} />
      <Field
        label="New password"
        type="password"
        value={password}
        required
        onChange={(e) => setPassword(e.target.value)}
        placeholder="At least 8 chars, upper, lower, number"
      />
      <Field
        label="Confirm new password"
        type="password"
        value={confirm}
        required
        onChange={(e) => setConfirm(e.target.value)}
      />
      <button type="submit" className="btn-primary" disabled={busy}>
        {busy ? "Updating…" : "Update password"}
      </button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="container">
      <div className="card">
        <h1>Set a new password</h1>
        <p className="subtitle">Choose a strong password you haven&apos;t used recently.</p>
        <Suspense fallback={<Spinner />}>
          <ResetInner />
        </Suspense>
      </div>
    </div>
  );
}
