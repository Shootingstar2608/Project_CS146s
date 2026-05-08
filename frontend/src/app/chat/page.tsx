"use client";

import React, { ChangeEvent, KeyboardEvent, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  ChevronRight,
  Maximize2,
  MessageSquare,
  Paperclip,
  Plus,
  Search,
  Send,
  Share2,
  Trash2,
  Upload,
} from "lucide-react";
import { NewPaperInput, useResearchStore } from "@/lib/research-store";
import { cn } from "@/lib/utils";

async function fileToPaperInput(file: File): Promise<NewPaperInput> {
  const canRead = /text|json|csv|markdown/.test(file.type) || /\.(txt|md|csv|json)$/i.test(file.name);
  return {
    fileName: file.name,
    fileType: file.type,
    fileSize: file.size,
    abstract: canRead ? (await file.text()).replace(/\s+/g, " ").trim().slice(0, 900) : undefined,
  };
}

export default function ChatPage() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const papers = useResearchStore((state) => state.papers);
  const sessions = useResearchStore((state) => state.sessions);
  const activeSessionId = useResearchStore((state) => state.activeSessionId);
  const createSession = useResearchStore((state) => state.createSession);
  const setActiveSession = useResearchStore((state) => state.setActiveSession);
  const deleteSession = useResearchStore((state) => state.deleteSession);
  const sendMessage = useResearchStore((state) => state.sendMessage);
  const addPapers = useResearchStore((state) => state.addPapers);
  const [draft, setDraft] = useState("");
  const [sessionQuery, setSessionQuery] = useState("");
  const [detailTab, setDetailTab] = useState<"sources" | "trace">("sources");

  const activeSession = sessions.find((session) => session.id === activeSessionId) ?? sessions[0];
  const filteredSessions = useMemo(() => {
    const normalized = sessionQuery.trim().toLowerCase();
    if (!normalized) return sessions;
    return sessions.filter((session) => session.title.toLowerCase().includes(normalized));
  }, [sessionQuery, sessions]);

  const latestAssistantMessage = [...(activeSession?.messages ?? [])].reverse().find((message) => message.role === "assistant");
  const sourcePapers = papers.filter((paper) => latestAssistantMessage?.sourcePaperIds.includes(paper.id));

  const handleSend = () => {
    const message = draft.trim();
    if (!message) return;
    sendMessage(message);
    setDraft("");
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  const handleAttach = async (event: ChangeEvent<HTMLInputElement>) => {
    if (!event.target.files || event.target.files.length === 0) return;
    const inputs = await Promise.all(Array.from(event.target.files).map(fileToPaperInput));
    const created = addPapers(inputs);
    setDraft((current) => {
      const titles = created.map((paper) => paper.title).join(", ");
      return current ? `${current}\nAttached: ${titles}` : `Attached: ${titles}`;
    });
    event.target.value = "";
  };

  return (
    <div className="grid min-h-[calc(100vh-140px)] gap-6 xl:grid-cols-[280px_minmax(0,1fr)_340px]">
      <aside className="flex min-h-[420px] flex-col overflow-hidden rounded-[28px] border border-aubergine/5 bg-surface/50">
        <div className="border-b border-aubergine/5 p-6">
          <h3 className="mb-4 text-xs font-bold uppercase tracking-wider text-aubergine/40">Conversations</h3>
          <button
            type="button"
            onClick={() => createSession()}
            className="flex w-full cursor-pointer items-center justify-center gap-2 rounded-xl border-2 border-dashed border-aubergine/10 py-3 text-sm font-bold text-aubergine/60 transition-colors hover:border-terracotta/40 hover:text-terracotta"
          >
            <Plus className="h-4 w-4" />
            <span>New chat</span>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {filteredSessions.length === 0 ? (
            <div className="rounded-2xl bg-cream-dark/20 p-4 text-sm leading-6 text-aubergine/45">
              {sessionQuery.trim() ? "No conversations match your search." : "No conversations yet. Start with New chat or send a question."}
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {filteredSessions.map((session) => {
                const isActive = activeSession?.id === session.id;
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
                      onClick={() => setActiveSession(session.id)}
                      className={cn(
                        "flex min-w-0 flex-1 items-center gap-3 rounded-lg p-2 text-left",
                        isActive && "border-l-4 border-terracotta"
                      )}
                    >
                      <MessageSquare className={cn("h-4 w-4 flex-shrink-0", isActive ? "text-terracotta" : "text-aubergine/40")} />
                      <span className={cn("line-clamp-1 text-sm font-medium", isActive ? "text-aubergine" : "text-aubergine/60")}>
                        {session.title}
                      </span>
                    </button>
                    <button
                      type="button"
                      aria-label={`Delete ${session.title}`}
                      onClick={() => deleteSession(session.id)}
                      className="rounded-lg p-2 text-aubergine/25 opacity-100 transition-colors hover:bg-surface hover:text-terracotta sm:opacity-0 sm:group-hover:opacity-100"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="border-t border-aubergine/5 p-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-aubergine/30" />
            <input
              type="text"
              value={sessionQuery}
              onChange={(event) => setSessionQuery(event.target.value)}
              placeholder="Search conversations..."
              className="w-full rounded-lg bg-cream-dark/20 py-2 pl-9 pr-3 text-xs font-mono focus:outline-none"
            />
          </div>
        </div>
      </aside>

      <section className="flex min-h-[620px] min-w-0 flex-col overflow-hidden rounded-[28px] bg-surface shadow-soft">
        <div className="flex flex-col gap-4 border-b border-aubergine/5 p-6">
          <h1 className="text-xl font-bold text-aubergine">{activeSession?.title ?? "Research chat"}</h1>
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-2 rounded-full bg-cream-dark/30 px-3 py-1 text-[10px] font-mono text-aubergine/60">
              <div className="h-1.5 w-1.5 rounded-full bg-sage" />
              <span>{papers.length} local papers</span>
            </div>
            <div className="flex items-center gap-2 rounded-full bg-cream-dark/30 px-3 py-1 text-[10px] font-mono text-aubergine/60">
              <div className="h-1.5 w-1.5 rounded-full bg-lilac" />
              <span>local index</span>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-5 sm:p-6">
          {!activeSession || activeSession.messages.length === 0 ? (
            <div className="flex h-full min-h-[360px] flex-col items-center justify-center text-center">
              <div className="mb-5 flex h-20 w-20 items-center justify-center rounded-2xl bg-cream-dark/30 text-terracotta">
                <MessageSquare className="h-10 w-10" />
              </div>
              <h2 className="text-2xl font-extrabold text-aubergine">Ask the local library</h2>
              <p className="mt-2 max-w-md text-sm leading-6 text-aubergine/50">
                Questions search your uploaded paper metadata and readable snippets. Upload files first for better answers.
              </p>
              {papers.length === 0 && (
                <Link href="/upload" className="mt-6 flex items-center gap-2 rounded-lg bg-terracotta px-5 py-3 font-bold text-surface shadow-soft">
                  <Upload className="h-5 w-5" />
                  Upload papers
                </Link>
              )}
            </div>
          ) : (
            <div className="flex flex-col gap-8">
              {activeSession.messages.map((message) => (
                <div key={message.id} className={cn("flex", message.role === "user" ? "justify-end" : "justify-start")}>
                  <div
                    className={cn(
                      "max-w-[90%] whitespace-pre-line rounded-[20px] p-4 text-sm leading-relaxed sm:max-w-[76%]",
                      message.role === "user"
                        ? "bg-terracotta text-surface shadow-soft"
                        : "border border-aubergine/5 bg-cream-dark/10 text-aubergine"
                    )}
                  >
                    {message.role === "assistant" && (
                      <div className="mb-4 flex items-center gap-2 border-b border-aubergine/5 pb-2 text-[10px] font-mono text-aubergine/40">
                        <ChevronRight className="h-3 w-3" />
                        <span>Local retrieval complete</span>
                      </div>
                    )}
                    {message.content}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="p-5 sm:p-6">
          <div className="relative flex items-end gap-3 rounded-2xl border border-aubergine/10 bg-surface p-3 shadow-soft focus-within:ring-2 focus-within:ring-terracotta/10">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.txt,.md,.csv,.json,application/pdf,text/plain,text/markdown,text/csv,application/json"
              onChange={handleAttach}
              className="hidden"
            />
            <button
              type="button"
              aria-label="Attach papers"
              onClick={() => fileInputRef.current?.click()}
              className="mb-1 cursor-pointer p-2 text-aubergine/30 transition-colors hover:text-aubergine"
            >
              <Paperclip className="h-5 w-5" />
            </button>
            <textarea
              rows={1}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask a research question..."
              className="max-h-32 min-h-10 flex-1 resize-none py-2 text-sm focus:outline-none"
            />
            <button
              type="button"
              aria-label="Send message"
              onClick={handleSend}
              disabled={draft.trim().length === 0}
              className="cursor-pointer rounded-xl bg-terracotta p-2 text-surface shadow-soft transition-transform hover:scale-105 active:scale-95 disabled:cursor-not-allowed disabled:opacity-45 disabled:hover:scale-100"
            >
              <Send className="h-5 w-5" />
            </button>
          </div>
        </div>
      </section>

      <aside className="relative flex min-h-[420px] flex-col overflow-hidden rounded-[28px] border border-aubergine/5 bg-surface/50">
        <div className="flex items-center justify-between border-b border-aubergine/5 p-6">
          <h3 className="text-xs font-bold uppercase tracking-wider text-aubergine/40">Reasoning Graph</h3>
          <Share2 className="h-4 w-4 text-aubergine/30" />
        </div>

        <div className="flex gap-2 border-b border-aubergine/5 p-4">
          <button
            type="button"
            onClick={() => setDetailTab("sources")}
            className={cn("flex-1 rounded-xl px-3 py-2 text-xs font-bold uppercase tracking-wider", detailTab === "sources" ? "bg-surface text-terracotta shadow-soft" : "text-aubergine/35")}
          >
            Sources
          </button>
          <button
            type="button"
            onClick={() => setDetailTab("trace")}
            className={cn("flex-1 rounded-xl px-3 py-2 text-xs font-bold uppercase tracking-wider", detailTab === "trace" ? "bg-surface text-terracotta shadow-soft" : "text-aubergine/35")}
          >
            Trace
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {detailTab === "sources" ? (
            sourcePapers.length > 0 ? (
              <div className="flex flex-col gap-3">
                {sourcePapers.map((paper) => (
                  <div key={paper.id} className="rounded-2xl bg-surface p-4 shadow-soft">
                    <div className="line-clamp-2 text-sm font-extrabold text-aubergine">{paper.title}</div>
                    <div className="mt-2 text-[10px] font-bold uppercase tracking-wider text-aubergine/35">
                      {paper.category}{paper.year ? ` | ${paper.year}` : ""}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex min-h-[260px] flex-col items-center justify-center text-center">
                <div className="mb-4 flex h-28 w-28 items-center justify-center rounded-full border-2 border-dashed border-aubergine/10">
                  <Share2 className="h-10 w-10 text-aubergine/10" />
                </div>
                <p className="max-w-[190px] text-xs leading-5 text-aubergine/30">Ask a question to see retrieved local sources.</p>
              </div>
            )
          ) : (
            <ol className="flex flex-col gap-3 text-sm text-aubergine/60">
              <li className="rounded-2xl bg-surface p-4 shadow-soft">1. Normalize the user question.</li>
              <li className="rounded-2xl bg-surface p-4 shadow-soft">2. Score uploaded papers by title, category, author, year, and readable snippets.</li>
              <li className="rounded-2xl bg-surface p-4 shadow-soft">3. Return the strongest local sources for the answer.</li>
            </ol>
          )}
        </div>

        <div className="absolute bottom-6 right-6">
          <Link
            href="/graph"
            aria-label="Open full graph"
            className="flex h-10 w-10 items-center justify-center rounded-xl bg-surface text-aubergine/60 shadow-soft hover:text-aubergine"
          >
            <Maximize2 className="h-5 w-5" />
          </Link>
        </div>
      </aside>
    </div>
  );
}
