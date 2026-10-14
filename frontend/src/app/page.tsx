"use client";

import React, { useState, useEffect } from "react";
import { CheckCircle2, AlertCircle, Database, Server, Terminal, RefreshCw, Layers } from "lucide-react";

interface HealthData {
  status: string;
  app: string;
  environment: string;
  database: string;
  timestamp: string;
}

export default function Home() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchHealth = async () => {
    setLoading(true);
    setError(null);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${apiUrl}/healthz`, { cache: "no-store" });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }
      const data: HealthData = await res.json();
      setHealth(data);
    } catch (err: any) {
      setError(err.message || "Failed to connect to backend");
      setHealth(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  return (
    <main className="min-h-screen p-8 lg:p-16 max-w-6xl mx-auto flex flex-col gap-10">
      {/* Header */}
      <header className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-border/60 pb-8">
        <div>
          <div className="flex items-center gap-3">
            <span className="flex h-3 w-3 rounded-full bg-emerald-500 animate-pulse" />
            <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
              PromptCheck
            </h1>
            <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20">
              Phase 0 Foundation
            </span>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            Continuous prompt regression testing and quality evaluation platform
          </p>
        </div>

        <button
          onClick={fetchHealth}
          disabled={loading}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium transition-all rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 active:scale-95 disabled:opacity-50 shadow-sm"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Check Backend Health
        </button>
      </header>

      {/* Grid of Component Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Backend Status Card */}
        <div className="rounded-xl border border-border/60 bg-card/60 backdrop-blur-sm p-6 flex flex-col justify-between shadow-sm">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="p-2.5 rounded-lg bg-blue-500/10 text-blue-400">
                <Server className="h-5 w-5" />
              </div>
              <span
                className={`text-xs font-medium px-2.5 py-0.5 rounded-full border ${
                  health?.status === "healthy"
                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                    : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                }`}
              >
                {health?.status || (loading ? "Checking..." : "Offline")}
              </span>
            </div>
            <h2 className="text-base font-semibold text-foreground">FastAPI Backend</h2>
            <p className="text-xs text-muted-foreground mt-1">
              Python 3.12, FastAPI, SQLAlchemy 2, Alembic
            </p>
          </div>
          <div className="mt-6 pt-4 border-t border-border/40 text-xs text-muted-foreground">
            Port: <code className="text-foreground">8000</code> &middot; Route:{" "}
            <code className="text-foreground">/healthz</code>
          </div>
        </div>

        {/* Database Status Card */}
        <div className="rounded-xl border border-border/60 bg-card/60 backdrop-blur-sm p-6 flex flex-col justify-between shadow-sm">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="p-2.5 rounded-lg bg-indigo-500/10 text-indigo-400">
                <Database className="h-5 w-5" />
              </div>
              <span
                className={`text-xs font-medium px-2.5 py-0.5 rounded-full border ${
                  health?.database === "ok"
                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                    : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                }`}
              >
                {health?.database === "ok" ? "Connected" : "Standby / Error"}
              </span>
            </div>
            <h2 className="text-base font-semibold text-foreground">PostgreSQL Database</h2>
            <p className="text-xs text-muted-foreground mt-1">
              PostgreSQL 16 &middot; Connection verified via SELECT 1
            </p>
          </div>
          <div className="mt-6 pt-4 border-t border-border/40 text-xs text-muted-foreground">
            Port: <code className="text-foreground">5432</code> &middot; DB:{" "}
            <code className="text-foreground">promptcheck</code>
          </div>
        </div>

        {/* CLI & Workflows Card */}
        <div className="rounded-xl border border-border/60 bg-card/60 backdrop-blur-sm p-6 flex flex-col justify-between shadow-sm">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="p-2.5 rounded-lg bg-purple-500/10 text-purple-400">
                <Terminal className="h-5 w-5" />
              </div>
              <span className="text-xs font-medium px-2.5 py-0.5 rounded-full border bg-purple-500/10 text-purple-400 border-purple-500/20">
                Configured
              </span>
            </div>
            <h2 className="text-base font-semibold text-foreground">Typer CLI & CI Action</h2>
            <p className="text-xs text-muted-foreground mt-1">
              Python CLI with Typer &middot; GitHub Action composite package
            </p>
          </div>
          <div className="mt-6 pt-4 border-t border-border/40 text-xs text-muted-foreground">
            Command: <code className="text-foreground">promptcheck ping</code>
          </div>
        </div>
      </div>

      {/* Live Health Check Response Section */}
      <section className="rounded-xl border border-border/60 bg-card/40 p-6 flex flex-col gap-4 shadow-sm">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Layers className="h-5 w-5 text-primary" />
            <h3 className="text-sm font-semibold">GET /healthz Realtime Connectivity</h3>
          </div>
          {health?.status === "healthy" ? (
            <div className="flex items-center gap-1.5 text-xs text-emerald-400">
              <CheckCircle2 className="h-4 w-4" />
              <span>Backend & Database Verified</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 text-xs text-amber-400">
              <AlertCircle className="h-4 w-4" />
              <span>{error || "Waiting for backend response"}</span>
            </div>
          )}
        </div>

        <div className="rounded-lg bg-black/60 p-4 border border-border/40 font-mono text-xs overflow-x-auto text-slate-300">
          {loading ? (
            <span className="text-muted-foreground">Querying http://localhost:8000/healthz...</span>
          ) : health ? (
            <pre>{JSON.stringify(health, null, 2)}</pre>
          ) : (
            <span className="text-rose-400">Backend offline or unreachable. Status: {error}</span>
          )}
        </div>
      </section>

      {/* Monorepo Architecture Overview */}
      <section className="rounded-xl border border-border/60 bg-card/30 p-6">
        <h3 className="text-sm font-semibold mb-4 text-foreground">Monorepo Structure (Phase 0)</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 text-xs">
          <div className="p-3 rounded-lg border border-border/40 bg-background/50">
            <span className="font-semibold text-foreground block">/backend</span>
            <span className="text-muted-foreground">FastAPI app, SQLAlchemy 2, Alembic migrations</span>
          </div>
          <div className="p-3 rounded-lg border border-border/40 bg-background/50">
            <span className="font-semibold text-foreground block">/frontend</span>
            <span className="text-muted-foreground">Next.js 14, TypeScript, Tailwind, shadcn/ui</span>
          </div>
          <div className="p-3 rounded-lg border border-border/40 bg-background/50">
            <span className="font-semibold text-foreground block">/cli</span>
            <span className="text-muted-foreground">Typer CLI tool, Rich console outputs</span>
          </div>
          <div className="p-3 rounded-lg border border-border/40 bg-background/50">
            <span className="font-semibold text-foreground block">/action</span>
            <span className="text-muted-foreground">Reusable GitHub Action package</span>
          </div>
          <div className="p-3 rounded-lg border border-border/40 bg-background/50">
            <span className="font-semibold text-foreground block">/examples/qa-bot</span>
            <span className="text-muted-foreground">Sample prompt tests and test bot</span>
          </div>
          <div className="p-3 rounded-lg border border-border/40 bg-background/50">
            <span className="font-semibold text-foreground block">docker-compose.yml</span>
            <span className="text-muted-foreground">Full stack orchestration (db, backend, frontend)</span>
          </div>
        </div>
      </section>
    </main>
  );
}
