"use client";

import { useState } from "react";
import { Check, Copy, FileText, ListTree, Sparkles } from "lucide-react";
import Markdown from "@/components/ui/Markdown";
import { ChatMessage as ChatMessageType } from "@/lib/research-store";

type Props = {
  message: ChatMessageType;
  sourceCount: number;
  onOpenSources: () => void;
  onOpenTrace: () => void;
};

const chipClass =
  "flex items-center gap-1.5 rounded-full border border-aubergine/10 px-3 py-1 text-xs font-semibold text-aubergine/55 transition-colors hover:border-terracotta/30 hover:text-terracotta";

/** A single chat turn: a neutral right-aligned bubble for the user, a full-width
 *  markdown answer with copy + source/trace actions for the assistant. */
export default function ChatMessage({ message, sourceCount, onOpenSources, onOpenTrace }: Props) {
  const [copied, setCopied] = useState(false);

  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-line rounded-[20px] rounded-br-md bg-cream-dark/50 px-4 py-3 text-sm leading-relaxed text-aubergine">
          {message.content}
        </div>
      </div>
    );
  }

  const hasTrace = (message.reasoningSteps?.length ?? 0) > 0;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard may be unavailable (insecure context) — fail silently.
    }
  };

  return (
    <div className="flex gap-3">
      <div className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-terracotta/10 text-terracotta">
        <Sparkles className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-aubergine">
          {message.content ? (
            <Markdown>{message.content}</Markdown>
          ) : (
            <div className="flex items-center gap-2 text-sm text-aubergine/45">
              <span className="h-2 w-2 animate-pulse rounded-full bg-terracotta" />
              Preparing the answer...
            </div>
          )}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <button type="button" onClick={copy} aria-label="Copy answer" className={chipClass}>
            {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
            {copied ? "Copied" : "Copy"}
          </button>
          {sourceCount > 0 && (
            <button type="button" onClick={onOpenSources} className={chipClass}>
              <FileText className="h-3.5 w-3.5" />
              Sources ({sourceCount})
            </button>
          )}
          {hasTrace && (
            <button type="button" onClick={onOpenTrace} className={chipClass}>
              <ListTree className="h-3.5 w-3.5" />
              Trace
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
