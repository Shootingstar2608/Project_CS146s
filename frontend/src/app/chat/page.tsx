"use client";

import { ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useQueryClient } from "@tanstack/react-query";
import { PanelLeft, PanelRight, Plus, Sparkles } from "lucide-react";
import { getErrorMessage, sendMessage as sendBackendMessage, uploadDocument } from "@/lib/api";
import { queryKeys, useDocuments } from "@/lib/queries";
import { useResearchStore } from "@/lib/research-store";
import ChatComposer from "@/components/chat/ChatComposer";
import ChatMessage from "@/components/chat/ChatMessage";
import InspectorDrawer from "@/components/chat/InspectorDrawer";
import SessionsDrawer from "@/components/chat/SessionsDrawer";
import SuggestionChips from "@/components/chat/SuggestionChips";

type InspectorTab = "sources" | "trace";

export default function ChatPage() {
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();

  const sessions = useResearchStore((state) => state.sessions);
  const activeSessionId = useResearchStore((state) => state.activeSessionId);
  const createSession = useResearchStore((state) => state.createSession);
  const setActiveSession = useResearchStore((state) => state.setActiveSession);
  const deleteSession = useResearchStore((state) => state.deleteSession);
  const appendUserMessage = useResearchStore((state) => state.appendUserMessage);
  const appendAssistantMessage = useResearchStore((state) => state.appendAssistantMessage);

  const { data: papers = [] } = useDocuments();

  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showSessions, setShowSessions] = useState(false);
  const [showInspector, setShowInspector] = useState(false);
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>("sources");
  const [selectedMessageId, setSelectedMessageId] = useState<string>();

  const activeSession = sessions.find((session) => session.id === activeSessionId) ?? sessions[0];
  const messages = useMemo(() => activeSession?.messages ?? [], [activeSession]);
  const isEmpty = messages.length === 0;

  // Keep the latest message (and the typing indicator) in view.
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, isSending]);

  // The answer whose sources/trace the inspector shows (defaults to the latest answer).
  const latestAssistant = useMemo(
    () => [...messages].reverse().find((message) => message.role === "assistant"),
    [messages]
  );
  const selectedMessage = messages.find((message) => message.id === selectedMessageId) ?? latestAssistant;
  const inspectorSourcePapers = papers.filter((paper) => selectedMessage?.sourcePaperIds.includes(paper.id));
  const inspectorReasoning = selectedMessage?.reasoningSteps ?? [];

  const sourceCountFor = (sourcePaperIds: string[]) =>
    papers.filter((paper) => sourcePaperIds.includes(paper.id)).length;

  const handleSend = async () => {
    const message = draft.trim();
    if (!message || isSending) return;
    setDraft("");
    setError(null);
    setIsSending(true);
    // Show the user's message immediately (optimistic), then await the answer.
    appendUserMessage(message);
    try {
      const response = await sendBackendMessage(message, activeSessionId);
      appendAssistantMessage({
        content: response.answer || "No answer returned.",
        sourcePaperIds: response.sources || [],
        reasoningSteps: response.reasoning_steps || [],
      });
    } catch (err: unknown) {
      const detail = getErrorMessage(err, "Backend chat request failed.");
      appendAssistantMessage({
        content: `Chat backend error: ${detail}`,
        sourcePaperIds: [],
        reasoningSteps: ["Backend chat request failed"],
      });
      setError(detail);
    } finally {
      setIsSending(false);
    }
  };

  const handleAttach = async (event: ChangeEvent<HTMLInputElement>) => {
    if (!event.target.files || event.target.files.length === 0) return;
    setIsUploading(true);
    setError(null);
    try {
      for (const file of Array.from(event.target.files)) {
        await uploadDocument(file);
      }
      queryClient.invalidateQueries({ queryKey: queryKeys.documents });
      queryClient.invalidateQueries({ queryKey: ["graph"] });
      setDraft((current) => current || "Summarize the newly uploaded paper.");
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Upload failed."));
    } finally {
      setIsUploading(false);
      event.target.value = "";
    }
  };

  const pickSuggestion = (prompt: string) => {
    setDraft(prompt);
    requestAnimationFrame(() => composerRef.current?.focus());
  };

  const handleNewChat = () => {
    createSession();
    setSelectedMessageId(undefined);
    setShowSessions(false);
  };

  const handleSelectSession = (id: string) => {
    setActiveSession(id);
    setSelectedMessageId(undefined);
    setShowSessions(false);
  };

  const openInspector = (messageId: string, tab: InspectorTab) => {
    setSelectedMessageId(messageId);
    setInspectorTab(tab);
    setShowInspector(true);
  };

  const composerProps = {
    value: draft,
    onChange: setDraft,
    onSubmit: handleSend,
    onAttach: handleAttach,
    isSending,
    isUploading,
    inputRef: composerRef,
  };

  return (
    <div className="relative flex h-[calc(100vh-140px)] min-h-[520px] flex-col overflow-hidden rounded-[28px] bg-surface shadow-soft">
      {/* Header */}
      <header className="flex items-center justify-between gap-3 border-b border-aubergine/5 px-3 py-2.5 sm:px-4">
        <div className="flex items-center gap-1">
          <button
            type="button"
            aria-label="Open conversations"
            aria-expanded={showSessions}
            title="Conversations"
            onClick={() => setShowSessions(true)}
            className="flex h-9 w-9 items-center justify-center rounded-lg text-aubergine/50 transition-colors hover:bg-cream-dark/30 hover:text-aubergine"
          >
            <PanelLeft className="h-5 w-5" />
          </button>
          <button
            type="button"
            aria-label="New chat"
            title="New chat"
            onClick={handleNewChat}
            className="flex h-9 w-9 items-center justify-center rounded-lg text-aubergine/50 transition-colors hover:bg-cream-dark/30 hover:text-aubergine"
          >
            <Plus className="h-5 w-5" />
          </button>
        </div>
        <h1 className="min-w-0 flex-1 truncate text-center text-sm font-bold text-aubergine">
          {activeSession?.title ?? "New chat"}
        </h1>
        <div className="flex items-center gap-2">
          <span className="hidden items-center gap-1.5 rounded-full bg-cream-dark/30 px-3 py-1 text-[10px] font-mono text-aubergine/60 sm:flex">
            <span className="h-1.5 w-1.5 rounded-full bg-sage" />
            {papers.length} papers
          </span>
          <button
            type="button"
            aria-label="Open answer details"
            aria-expanded={showInspector}
            title="Sources & trace"
            onClick={() => setShowInspector(true)}
            className="flex h-9 w-9 items-center justify-center rounded-lg text-aubergine/50 transition-colors hover:bg-cream-dark/30 hover:text-aubergine"
          >
            <PanelRight className="h-5 w-5" />
          </button>
        </div>
      </header>

      {/* Messages / empty state */}
      <div className="flex-1 overflow-y-auto">
        {isEmpty ? (
          <div className="mx-auto flex h-full w-full max-w-3xl flex-col items-center justify-center px-4 text-center">
            <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-terracotta/10 text-terracotta">
              <Sparkles className="h-7 w-7" />
            </div>
            <h2 className="text-3xl font-extrabold tracking-tight text-aubergine sm:text-4xl">
              What do you want to research?
            </h2>
            <p className="mt-3 max-w-md text-sm leading-6 text-aubergine/55">
              Questions run through the GraphRAG agent and cite your indexed papers when the graph has matching context.
            </p>
            <div className="mt-7 w-full">
              <ChatComposer variant="hero" autoFocus placeholder="Ask anything about your papers…" {...composerProps} />
            </div>
            <div className="mt-5">
              <SuggestionChips onPick={pickSuggestion} />
            </div>
            {papers.length === 0 && (
              <p className="mt-6 text-xs text-aubergine/45">
                No papers yet —{" "}
                <Link href="/upload" className="font-semibold text-terracotta hover:underline">
                  upload to ground answers
                </Link>
                .
              </p>
            )}
            {error && <p className="mt-4 text-xs font-medium text-terracotta">{error}</p>}
          </div>
        ) : (
          <div className="mx-auto w-full max-w-3xl px-4 py-6">
            <div className="flex flex-col gap-7">
              {messages.map((message) => (
                <ChatMessage
                  key={message.id}
                  message={message}
                  sourceCount={sourceCountFor(message.sourcePaperIds)}
                  onOpenSources={() => openInspector(message.id, "sources")}
                  onOpenTrace={() => openInspector(message.id, "trace")}
                />
              ))}
              {isSending && (
                <div className="flex gap-3">
                  <div className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-terracotta/10 text-terracotta">
                    <Sparkles className="h-4 w-4" />
                  </div>
                  <div className="flex items-center gap-3 rounded-[20px] bg-cream-dark/15 px-4 py-3 text-sm text-aubergine/60">
                    <span className="flex gap-1" aria-hidden>
                      <span className="h-2 w-2 animate-bounce rounded-full bg-terracotta/60 [animation-delay:-0.2s] motion-reduce:animate-none" />
                      <span className="h-2 w-2 animate-bounce rounded-full bg-terracotta/60 [animation-delay:-0.1s] motion-reduce:animate-none" />
                      <span className="h-2 w-2 animate-bounce rounded-full bg-terracotta/60 motion-reduce:animate-none" />
                    </span>
                    <span>Searching the knowledge graph…</span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>
        )}
      </div>

      {/* Docked composer (active conversation) */}
      {!isEmpty && (
        <div className="border-t border-aubergine/5 bg-surface/80 px-4 py-3 backdrop-blur">
          <div className="mx-auto w-full max-w-3xl">
            <ChatComposer variant="docked" autoFocus {...composerProps} />
            {error && <p className="mt-2 text-xs font-medium text-terracotta">{error}</p>}
            <p className="mt-2 text-center text-[11px] text-aubergine/35">
              GraphRAG can be inaccurate — verify cited sources.
            </p>
          </div>
        </div>
      )}

      <SessionsDrawer
        open={showSessions}
        onClose={() => setShowSessions(false)}
        sessions={sessions}
        activeSessionId={activeSession?.id}
        onCreate={handleNewChat}
        onSelect={handleSelectSession}
        onDelete={deleteSession}
      />
      <InspectorDrawer
        open={showInspector}
        onClose={() => setShowInspector(false)}
        tab={inspectorTab}
        onTabChange={setInspectorTab}
        sourcePapers={inspectorSourcePapers}
        reasoningSteps={inspectorReasoning}
      />
    </div>
  );
}
