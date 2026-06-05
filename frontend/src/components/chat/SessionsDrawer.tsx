"use client";

import { useEffect, useState } from "react";
import { MessageSquare, Plus, Search, Trash2, X } from "lucide-react";
import { ChatSession } from "@/lib/research-store";
import { cn } from "@/lib/utils";

type Props = {
  open: boolean;
  onClose: () => void;
  sessions: ChatSession[];
  activeSessionId?: string;
  onCreate: () => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
};

/** Left slide-in drawer holding the conversation history (hidden by default). */
export default function SessionsDrawer({
  open,
  onClose,
  sessions,
  activeSessionId,
  onCreate,
  onSelect,
  onDelete,
}: Props) {
  const [query, setQuery] = useState("");

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const normalized = query.trim().toLowerCase();
  const filtered = normalized
    ? sessions.filter((session) => session.title.toLowerCase().includes(normalized))
    : sessions;

  return (
    <>
      <div
        className={cn(
          "absolute inset-0 z-20 bg-aubergine/20 transition-opacity",
          open ? "opacity-100" : "pointer-events-none opacity-0"
        )}
        onClick={onClose}
        aria-hidden
      />
      <aside
        aria-label="Conversations"
        aria-hidden={!open}
        className={cn(
          "absolute inset-y-0 left-0 z-30 flex w-[300px] max-w-[85%] flex-col border-r border-aubergine/10 bg-surface shadow-deep transition-transform duration-200",
          open ? "translate-x-0" : "pointer-events-none -translate-x-[110%]"
        )}
      >
        <div className="flex items-center justify-between border-b border-aubergine/5 px-5 py-4">
          <h3 className="text-xs font-bold uppercase tracking-wider text-aubergine/40">Conversations</h3>
          <button
            type="button"
            aria-label="Close conversations"
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-aubergine/40 transition-colors hover:bg-cream-dark/30 hover:text-aubergine"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="px-4 pt-4">
          <button
            type="button"
            onClick={onCreate}
            className="flex w-full items-center justify-center gap-2 rounded-xl border-2 border-dashed border-aubergine/10 py-3 text-sm font-bold text-aubergine/60 transition-colors hover:border-terracotta/40 hover:text-terracotta"
          >
            <Plus className="h-4 w-4" />
            <span>New chat</span>
          </button>
        </div>

        <div className="px-4 pt-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-aubergine/30" />
            <input
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search conversations…"
              aria-label="Search conversations"
              className="w-full rounded-lg bg-cream-dark/20 py-2 pl-9 pr-3 text-xs focus:outline-none focus:ring-2 focus:ring-terracotta/20"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {filtered.length === 0 ? (
            <div className="rounded-2xl bg-cream-dark/20 p-4 text-sm leading-6 text-aubergine/45">
              {normalized
                ? "No conversations match your search."
                : "No conversations yet. Start with New chat or send a question."}
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {filtered.map((session) => {
                const isActive = session.id === activeSessionId;
                return (
                  <div
                    key={session.id}
                    className={cn(
                      "group flex items-center gap-2 rounded-xl p-2 transition-colors",
                      isActive ? "bg-cream-dark/30" : "hover:bg-cream-dark/20"
                    )}
                  >
                    <button
                      type="button"
                      onClick={() => onSelect(session.id)}
                      className={cn(
                        "flex min-w-0 flex-1 items-center gap-3 rounded-lg p-2 text-left",
                        isActive && "border-l-4 border-terracotta"
                      )}
                    >
                      <MessageSquare
                        className={cn(
                          "h-4 w-4 flex-shrink-0",
                          isActive ? "text-terracotta" : "text-aubergine/40"
                        )}
                      />
                      <span
                        className={cn(
                          "line-clamp-1 text-sm font-medium",
                          isActive ? "text-aubergine" : "text-aubergine/60"
                        )}
                      >
                        {session.title}
                      </span>
                    </button>
                    <button
                      type="button"
                      aria-label={`Delete ${session.title}`}
                      onClick={() => onDelete(session.id)}
                      className="rounded-lg p-2 text-aubergine/25 transition-colors hover:bg-surface hover:text-terracotta sm:opacity-0 sm:group-hover:opacity-100"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
