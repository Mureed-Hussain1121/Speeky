"use client";

import { ReactNode } from "react";
import { ApiError } from "../lib/api";

export function Message({ kind, children }: { kind: "error" | "success" | "info" | "warn"; children: ReactNode }) {
  if (!children) return null;
  return <div className={`msg ${kind}`}>{children}</div>;
}

export function ErrorMessage({ error }: { error: ApiError | null }) {
  if (!error) return null;
  // Weak-password errors carry a `requirements` array.
  const reqs: string[] | undefined = error.detail?.requirements;
  return (
    <div className="msg error">
      {error.message}
      {reqs && reqs.length > 0 && (
        <ul>
          {reqs.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function Field({
  label,
  ...props
}: { label: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div className="field">
      <label>{label}</label>
      <input {...props} />
    </div>
  );
}

export function Spinner({ text = "Loading…" }: { text?: string }) {
  return <div className="spinner">{text}</div>;
}
