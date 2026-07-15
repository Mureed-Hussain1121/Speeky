"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "../lib/auth";

export default function Nav() {
  const { user, logout, loading } = useAuth();
  const router = useRouter();

  async function handleLogout() {
    await logout();
    router.push("/login");
  }

  return (
    <nav className="nav">
      <Link href={user ? "/dashboard" : "/login"} className="brand" style={{ color: "var(--text)" }}>
        🎤 Speeky
      </Link>
      <span className="spacer" />
      {!loading && user && (
        <>
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/profile">Profile</Link>
          <Link href="/security">Security</Link>
          <Link href="/privacy">Privacy</Link>
          <a onClick={handleLogout} style={{ cursor: "pointer" }}>
            Log out
          </a>
        </>
      )}
      {!loading && !user && (
        <>
          <Link href="/login">Log in</Link>
          <Link href="/register">Sign up</Link>
        </>
      )}
    </nav>
  );
}
