"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Protected from "../components/Protected";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { ErrorMessage, Field, Message } from "../components/ui";

function ProfileInner() {
  const { user, refresh } = useAuth();
  const [goals, setGoals] = useState<{ key: string; label: string }[]>([]);

  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [photoUrl, setPhotoUrl] = useState("");
  const [language, setLanguage] = useState("en-GB");
  const [goal, setGoal] = useState("");

  const [error, setError] = useState<ApiError | null>(null);
  const [saved, setSaved] = useState("");
  const [busy, setBusy] = useState(false);
  const [goalBusy, setGoalBusy] = useState(false);

  useEffect(() => {
    api.goals().then((r) => setGoals(r.goals)).catch(() => {});
  }, []);

  useEffect(() => {
    if (user) {
      setUsername(user.username || "");
      setDisplayName(user.display_name || "");
      setPhotoUrl(user.photo_url || "");
      setLanguage(user.preferred_language || "en-GB");
      setGoal(user.learning_goal);
    }
  }, [user]);

  if (!user) return null;

  async function saveProfile(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved("");
    setBusy(true);
    // Only send changed fields (backend rejects a no-op update).
    const body: any = {};
    if (username !== (user!.username || "")) body.username = username || undefined;
    if (displayName !== (user!.display_name || "")) body.display_name = displayName;
    if (photoUrl !== (user!.photo_url || "")) body.photo_url = photoUrl;
    if (language !== user!.preferred_language) body.preferred_language = language;
    if (Object.keys(body).length === 0) {
      setBusy(false);
      setSaved("No changes to save.");
      return;
    }
    try {
      await api.updateProfile(body);
      await refresh();
      setSaved("Profile updated.");
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setBusy(false);
    }
  }

  async function saveGoal(newGoal: string) {
    setGoal(newGoal);
    setGoalBusy(true);
    setError(null);
    try {
      await api.updateGoal(newGoal);
      await refresh();
      setSaved("Goal updated — your dashboard has been recalibrated.");
    } catch (err) {
      setError(err as ApiError);
      setGoal(user!.learning_goal); // revert on failure (E-01)
    } finally {
      setGoalBusy(false);
    }
  }

  const isSso = user.auth_provider !== "email";

  return (
    <div className="container wide">
      <div className="card">
        <h1>Your profile</h1>
        <p className="subtitle">
          Signed in via <span className="badge">{user.auth_provider}</span>
          {user.uses_private_relay && <span className="badge" style={{ marginLeft: 6 }}>Apple private relay</span>}
        </p>

        <ErrorMessage error={error} />
        {saved && <Message kind="success">{saved}</Message>}

        <form onSubmit={saveProfile}>
          <Field label="Email" type="email" value={user.email} disabled readOnly />
          <Field
            label="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="speeky_learner"
          />
          <Field
            label="Display name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="Your name"
          />
          <Field
            label="Profile photo URL (.png .jpg .jpeg .webp .gif)"
            value={photoUrl}
            onChange={(e) => setPhotoUrl(e.target.value)}
            placeholder="https://…/avatar.png"
          />
          <div className="field">
            <label>Preferred language</label>
            <select value={language} onChange={(e) => setLanguage(e.target.value)}>
              <option value="en-GB">English (British)</option>
              <option value="en-US">English (American)</option>
              <option value="ur">Urdu</option>
              <option value="hi">Hindi</option>
            </select>
          </div>
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? "Saving…" : "Save changes"}
          </button>
        </form>
      </div>

      {/* ONB-US-10 — Dynamic goal recalibration */}
      <div className="card">
        <h2>Learning goal</h2>
        <p className="muted" style={{ marginTop: 0 }}>
          Changing your goal instantly reorders your dashboard. Your score and streaks are preserved.
        </p>
        <div className="goal-grid">
          {goals.map((g) => (
            <button
              key={g.key}
              className={`goal-option ${goal === g.key ? "selected" : ""}`}
              onClick={() => saveGoal(g.key)}
              disabled={goalBusy}
            >
              {g.label}
            </button>
          ))}
        </div>
      </div>

      {/* MOCK read-only fields */}
      <div className="card">
        <h2>Progress (mock)</h2>
        <div className="stat-grid">
          <div className="stat">
            <div className="value">{user.score}</div>
            <p className="label">Confidence Score</p>
          </div>
          <div className="stat">
            <div className="value">{user.skill_level}</div>
            <p className="label">Skill Level</p>
          </div>
          <div className="stat">
            <div className="value">{new Date(user.created_at).toLocaleDateString()}</div>
            <p className="label">Member since</p>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="row">
          <div>
            <h2 style={{ marginBottom: 4 }}>Danger zone</h2>
            <p className="muted">Permanently delete your account and data.</p>
          </div>
          <Link href="/delete-account">
            <button className="btn-danger">Delete account</button>
          </Link>
        </div>
        {isSso && <p className="muted" style={{ marginTop: 10 }}>SSO account — deletion is confirmed without a password.</p>}
      </div>
    </div>
  );
}

export default function ProfilePage() {
  return (
    <Protected>
      <ProfileInner />
    </Protected>
  );
}
