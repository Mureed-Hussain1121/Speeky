"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../lib/auth";
import { Spinner } from "./ui";

/** Wraps pages that require an authenticated session. */
export default function Protected({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, user, router]);

  if (loading) return <Spinner />;
  if (!user) return <Spinner text="Redirecting to login…" />;
  return <>{children}</>;
}
