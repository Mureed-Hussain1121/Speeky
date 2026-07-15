"use client";

import Link from "next/link";
import Protected from "../components/Protected";
import { useAuth } from "../lib/auth";

const GOAL_LABELS: Record<string, string> = {
  improve_english: "Improve English",
  job_interviews: "Job Interviews",
  workplace_communication: "Workplace Communication",
  public_speaking: "Public Speaking",
};

// Module catalogue; the module matching the user's goal is surfaced first
// (ONB-US-10: dashboard reorders instantly when the goal changes).
const MODULES: Record<string, string[]> = {
  improve_english: ["Everyday Conversation", "Vocabulary Builder", "Pronunciation Drills"],
  job_interviews: ["Interview Coach", "STAR Answer Practice", "Confidence Warmups"],
  workplace_communication: ["Meeting Simulator", "Email & Small Talk", "Presentation Practice"],
  public_speaking: ["Speech Builder", "Pacing & Pauses", "Audience Q&A"],
};

function DashboardInner() {
  const { user } = useAuth();
  if (!user) return null;

  const goalKey = user.learning_goal;
  const primary = MODULES[goalKey] || [];
  const others = Object.entries(MODULES)
    .filter(([k]) => k !== goalKey)
    .flatMap(([, v]) => v);

  return (
    <div className="container wide">
      {user.is_pending_deletion && (
        <div className="msg warn">
          Your account is scheduled for deletion.{" "}
          <Link href="/delete-account">Review or cancel</Link>.
        </div>
      )}

      <div className="card">
        <h1>Hi{user.display_name ? `, ${user.display_name}` : ""} 👋</h1>
        <p className="subtitle">
          Your focus: <b>{GOAL_LABELS[goalKey] || goalKey}</b> ·{" "}
          <Link href="/profile">change goal</Link>
        </p>

        {/* MOCK stats — score (Gameification) & skill level (Baseline Assessment). */}
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
            <div className="value">{user.is_verified ? "✓" : "—"}</div>
            <p className="label">Email Verified</p>
          </div>
        </div>
        <p className="muted" style={{ marginTop: 10 }}>
          Score and skill level are placeholders until the Gameification and Baseline Assessment features ship.
        </p>
      </div>

      <div className="card">
        <h2>Recommended for your goal</h2>
        {primary.map((m) => (
          <div className="list-item row" key={m}>
            <span>{m}</span>
            <span className="badge blue">Featured</span>
          </div>
        ))}
      </div>

      <div className="card">
        <h2>Explore more</h2>
        {others.map((m) => (
          <div className="list-item" key={m}>
            {m}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <Protected>
      <DashboardInner />
    </Protected>
  );
}
