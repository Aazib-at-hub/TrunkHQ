"use client";

import React, { useEffect, useState } from "react";
import { Modal } from "../ui/modal";
import { Input } from "../ui/input";
import { Button } from "../ui/button";
import { useAuthStore } from "../../lib/store/auth";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  defaultMode?: "login" | "register";
}

export function AuthModal({
  isOpen,
  onClose,
  defaultMode = "login",
}: AuthModalProps) {
  const [mode, setMode] = useState<"login" | "register">(defaultMode);
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [loading, setLoading] = useState(false);

  const { login, register } = useAuthStore();

  useEffect(() => {
    if (!isOpen) return;
    const timer = setTimeout(() => {
      setMode(defaultMode);
      setErrorMsg("");
    }, 0);
    return () => clearTimeout(timer);
  }, [isOpen, defaultMode]);

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
      onClose();
      setEmail("");
      setUsername("");
      setPassword("");
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMsg(err.message);
      } else {
        setErrorMsg("Authentication failed. Please check credentials.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={mode === "login" ? "Sign In to TrunkHQ" : "Create Account"}
      description={
        mode === "login"
          ? "Access your indexed repositories and intelligence conversations"
          : "Start indexing repositories and querying codebases with RAG"
      }
      maxWidth="sm"
    >
      <div className="mt-1 mb-4 grid grid-cols-2 gap-1 rounded-lg border border-border-default bg-bg-primary p-1">
        <button
          type="button"
          onClick={() => {
            setMode("login");
            setErrorMsg("");
          }}
          className={`cursor-pointer rounded-md py-1.5 text-xs font-medium transition ${
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
          className={`cursor-pointer rounded-md py-1.5 text-xs font-medium transition ${
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
          <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-2.5 text-xs text-rose-300">
            {errorMsg}
          </div>
        )}

        <Input
          label="Email Address"
          type="email"
          required
          placeholder="developer@example.com"
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

        <Button type="submit" variant="primary" className="w-full" isLoading={loading}>
          {mode === "login" ? "Sign In" : "Create Account"}
        </Button>
      </form>
    </Modal>
  );
}
