"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { ErrorMessage, Field, Message } from "../components/ui";
import SsoButtons from "../components/SsoButtons";

export default function RegisterPage() {
  const router = useRouter();
  const { setSession } = useAuth();
  const [goals, setGoals] = useState<{ key: string; label: string }[]>([]);
  const [selectedGoal, setSelectedGoal] = useState<string>("");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    api.goals().then((r) => setGoals(r.goals)).catch(() => {});
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    // ONB-US-08: at least one learning purpose is required before proceeding.
    if (!selectedGoal) {
      setError({ status: 0, message: "Please select a learning goal to continue." });
      return;
    }
    setBusy(true);
    try {
      await api.register({
        email,
        password,
        username: username || undefined,
        learning_goal: selectedGoal,
      });
      setDone(true);
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <div className="container">
        <div className="card">
          <h1>Check your inbox</h1>
          <Message kind="success">
            We&apos;ve sent a verification link to <b>{email}</b>. Click it to activate your account, then log in.
          </Message>
          <p className="muted">
            (Email is mocked in this build — open <code>/dev/outbox</code> on the API, or the verification page will
            accept the token from the link.)
          </p>
          <Link href="/login">
            <button className="btn-primary" style={{ marginTop: 10 }}>
              Go to login
            </button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="container">
      <div className="card">
        <h1>Create your account</h1>
        <p className="subtitle">Set a goal so we can personalize your practice.</p>

        <ErrorMessage error={error} />

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
            label="Username (optional)"
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="speeky_learner"
          />
          <Field
            label="Password"
            type="password"
            value={password}
            required
            onChange={(e) => setPassword(e.target.value)}
            placeholder="At least 8 chars, upper, lower, number"
          />

          <label>Primary learning goal</label>
          <div className="goal-grid" style={{ marginBottom: 18 }}>
            {goals.map((g) => (
              <button
                type="button"
                key={g.key}
                className={`goal-option ${selectedGoal === g.key ? "selected" : ""}`}
                onClick={() => setSelectedGoal(g.key)}
              >
                {g.label}
              </button>
            ))}
          </div>

          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? "Creating account…" : "Create account"}
          </button>
        </form>

        <div className="divider">or sign up with</div>
        <SsoButtons
          learningGoal={selectedGoal || undefined}
          onSuccess={(res) => {
            setSession(res.access_token, res.refresh_token, res.user);
            router.push("/dashboard");
          }}
        />

        <p className="helper">
          Already have an account? <Link href="/login">Log in</Link>
        </p>
      </div>
    </div>
  );
}
