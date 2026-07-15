import "./globals.css";
import type { Metadata } from "next";
import { AuthProvider } from "./lib/auth";
import Nav from "./components/Nav";

export const metadata: Metadata = {
  title: "Speeky — Account",
  description: "Speeky Onboarding & Account Management",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          <Nav />
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
