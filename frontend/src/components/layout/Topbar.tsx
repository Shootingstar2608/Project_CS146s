"use client";

import React, { useState } from "react";
import { Bell, Database, Search, Settings, User } from "lucide-react";
import Link from "next/link";
import { useResearchStore } from "@/lib/research-store";

const Topbar = () => {
  const [showStatus, setShowStatus] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const papers = useResearchStore((state) => state.papers);
  const sessions = useResearchStore((state) => state.sessions);
  const clearWorkspace = useResearchStore((state) => state.clearWorkspace);

  const handleClear = () => {
    if (window.confirm("Clear local papers and chat history?")) {
      clearWorkspace();
      setShowSettings(false);
    }
  };

  return (
    <header className="fixed left-20 right-0 top-0 z-40 flex h-[60px] items-center justify-between bg-surface px-4 shadow-soft sm:px-8">
      <div className="flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-terracotta text-surface font-bold">
          M
        </div>
        <span className="text-base font-bold tracking-tight text-aubergine sm:text-lg">MLIoT Lab</span>
      </div>

      <div className="relative flex items-center gap-3 sm:gap-6">
        <div className="flex items-center gap-3 text-aubergine/60 sm:gap-4">
          <Link
            href="/papers"
            aria-label="Search papers"
            title="Search papers"
            className="transition-colors hover:text-aubergine"
          >
            <Search className="h-5 w-5" />
          </Link>
          <button
            type="button"
            aria-label="Workspace status"
            title="Workspace status"
            onClick={() => {
              setShowStatus((value) => !value);
              setShowSettings(false);
            }}
            className="cursor-pointer transition-colors hover:text-aubergine"
          >
            <Bell className="h-5 w-5" />
          </button>
          <button
            type="button"
            aria-label="Local workspace settings"
            title="Local workspace settings"
            onClick={() => {
              setShowSettings((value) => !value);
              setShowStatus(false);
            }}
            className="cursor-pointer transition-colors hover:text-aubergine"
          >
            <Settings className="h-5 w-5" />
          </button>
        </div>
        
        <div className="hidden items-center gap-3 border-l border-aubergine/10 pl-6 sm:flex">
          <div className="flex flex-col items-end">
            <span className="text-sm font-semibold text-aubergine leading-none">Local Workspace</span>
            <span className="text-[10px] font-bold uppercase tracking-wider text-terracotta/80 mt-1">
              Local MVP
            </span>
          </div>
          <div className="h-10 w-10 overflow-hidden rounded-full bg-cream-dark shadow-soft border-2 border-surface">
            <User className="h-full w-full p-2 text-aubergine/40" />
          </div>
        </div>

        {showStatus && (
          <div className="absolute right-0 top-12 w-72 rounded-2xl border border-aubergine/10 bg-surface p-4 shadow-deep">
            <div className="mb-3 flex items-center gap-2 text-sm font-bold text-aubergine">
              <Database className="h-4 w-4 text-terracotta" />
              Workspace status
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-xl bg-cream-dark/30 p-3">
                <div className="text-2xl font-extrabold text-aubergine">{papers.length}</div>
                <div className="text-xs font-medium text-aubergine/50">Papers</div>
              </div>
              <div className="rounded-xl bg-cream-dark/30 p-3">
                <div className="text-2xl font-extrabold text-aubergine">{sessions.length}</div>
                <div className="text-xs font-medium text-aubergine/50">Chats</div>
              </div>
            </div>
          </div>
        )}

        {showSettings && (
          <div className="absolute right-0 top-12 w-72 rounded-2xl border border-aubergine/10 bg-surface p-4 shadow-deep">
            <div className="mb-3 text-sm font-bold text-aubergine">Local workspace</div>
            <p className="mb-4 text-xs leading-5 text-aubergine/50">
              Data is stored in this browser until the backend ingestion API is ready.
            </p>
            <button
              type="button"
              onClick={handleClear}
              className="w-full rounded-xl bg-aubergine px-4 py-3 text-sm font-bold text-surface transition-colors hover:bg-aubergine/90"
            >
              Clear local data
            </button>
          </div>
        )}
      </div>
    </header>
  );
};

export default Topbar;
