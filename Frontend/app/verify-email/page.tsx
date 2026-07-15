"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api, ApiError } from "../lib/api";
import { Message, Spinner } from "../components/ui";

function VerifyInner() {
  const params = useSearchParams();
  const token = params.get("token");
  const [state, setState] = useState<"working" | "ok" | "error">("working");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!token) {
      setState("error");
      setMessage("No verification token found in the link.");
      return;
    }
    api
      .verifyEmail(token)
      .then((r: any) => {
        setState("ok");
        setMessage(r.message || "Email verified.");
      })
      .catch((e: ApiError) => {
        setState("error");
        setMessage(e.message);
      });
  }, [token]);

  return (
    <div className="container">
      <div className="card">
        <h1>Email verification</h1>
        {state === "working" && <Spinner text="Verifying your email…" />}
        {state === "ok" && (
          <>
            <Message kind="success">{message}</Message>
            <Link href="/login">
              <button className="btn-primary">Continue to login</button>
            </Link>
          </>
        )}
        {state === "error" && (
          <>
            <Message kind="error">{message}</Message>
            <p className="muted">
              If your link expired, log in and use the &quot;Resend verification email&quot; option.
            </p>
            <Link href="/login">
              <button className="btn-secondary">Back to login</button>
            </Link>
          </>
        )}
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<Spinner />}>
      <VerifyInner />
    </Suspense>
  );
}
