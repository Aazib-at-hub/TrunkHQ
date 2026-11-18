"use client";

import React, { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { Input } from "../../components/ui/input";
import { Button } from "../../components/ui/button";
import { useAuthStore } from "../../lib/store/auth";
import { useThemeStore } from "../../lib/store/theme";

function AuthPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialMode = searchParams.get("mode") === "register" ? "register" : "login";

  const { user, login, register, initialize } = useAuthStore();
  const { initTheme } = useThemeStore();

  const [mode, setMode] = useState<"login" | "register">(initialMode);
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    initialize();
    initTheme();
  }, [initialize, initTheme]);

  useEffect(() => {
    if (user) {
      router.replace("/");
    }
  }, [user, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg("");
    setLoading(true);
    try {
      if (mode === "login") {
        await login(email.trim(), password);
      } else {
        await register(email.trim(), username.trim(), password);
      }
      router.push("/");
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Authentication failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col justify-between bg-bg-primary text-text-primary px-4 py-8">
      <div className="mx-auto w-full max-w-md">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-xs text-text-secondary hover:text-text-primary transition"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to TrunkHQ
        </Link>
      </div>

      <div className="mx-auto w-full max-w-md rounded-2xl border border-border-default bg-bg-secondary p-7 shadow-xl space-y-6 my-8">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-border-default bg-white p-1.5">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/trunkhq-icon.png" alt="TrunkHQ" className="h-full w-full object-contain" />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-text-primary">
              {mode === "login" ? "Sign In to TrunkHQ" : "Create Your TrunkHQ Account"}
            </h1>
            <p className="text-xs text-text-secondary">
              Engineering Intelligence Platform
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-1 rounded-lg border border-border-default bg-bg-primary p-1">
          <button
            type="button"
            onClick={() => {
              setMode("login");
              setErrorMsg("");
            }}
            className={`cursor-pointer rounded-md py-2 text-xs font-medium transition ${
              mode === "login"
                ? "bg-emerald-600 text-white"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => {
              setMode("register");
              setErrorMsg("");
            }}
            className={`cursor-pointer rounded-md py-2 text-xs font-medium transition ${
              mode === "register"
                ? "bg-emerald-600 text-white"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            Sign Up
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {errorMsg && (
            <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300">
              {errorMsg}
            </div>
          )}

          <Input
            label="Email Address"
            type="email"
            required
            placeholder="developer@company.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />

          {mode === "register" && (
            <Input
              label="Username"
              type="text"
              required
              minLength={3}
              maxLength={50}
              pattern="^[a-zA-Z0-9_-]+$"
              helperText="3–50 characters: letters, numbers, _ or -"
              placeholder="octocat"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          )}

          <Input
            label="Password"
            type="password"
            required
            minLength={mode === "register" ? 8 : 1}
            helperText={mode === "register" ? "Minimum 8 characters" : undefined}
            placeholder="••••••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          <Button type="submit" variant="primary" size="lg" className="w-full" isLoading={loading}>
            {mode === "login" ? "Sign In" : "Create Account"}
          </Button>
        </form>
      </div>

      <p className="text-center text-xs text-text-tertiary">
        TrunkHQ · Engineering Intelligence Platform
      </p>
    </div>
  );
}

export default function AuthPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-bg-primary" />}>
      <AuthPageContent />
    </Suspense>
  );
}
