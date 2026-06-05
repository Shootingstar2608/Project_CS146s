"use client";

import { ChangeEvent, KeyboardEvent, RefObject, useEffect, useRef } from "react";
import { ArrowUp, Paperclip } from "lucide-react";
import { cn } from "@/lib/utils";

type Props = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onAttach: (event: ChangeEvent<HTMLInputElement>) => void;
  isSending: boolean;
  isUploading: boolean;
  variant?: "hero" | "docked";
  autoFocus?: boolean;
  placeholder?: string;
  inputRef?: RefObject<HTMLTextAreaElement | null>;
};

/**
 * The chat input pill — a rounded composer with a `+` attach button, an
 * auto-growing textarea, and a circular send button. Reused for the centered
 * empty-state ("hero") and the docked bottom bar ("docked").
 */
export default function ChatComposer({
  value,
  onChange,
  onSubmit,
  onAttach,
  isSending,
  isUploading,
  variant = "docked",
  autoFocus = false,
  placeholder = "Ask a research question…",
  inputRef,
}: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const localRef = useRef<HTMLTextAreaElement>(null);
  const textareaRef = inputRef ?? localRef;

  // Auto-grow the textarea up to a max height as the user types.
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    const resize = () => {
      el.style.height = "auto";
      el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
    };
    resize();
    // The first mount (and web-font load) can mis-measure scrollHeight, leaving
    // an empty field stuck at its max height — recompute once after paint.
    const raf = requestAnimationFrame(resize);
    return () => cancelAnimationFrame(raf);
  }, [value, textareaRef]);

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSubmit();
    }
  };

  const canSend = value.trim().length > 0 && !isSending;

  return (
    <div
      className={cn(
        "flex items-end gap-2 rounded-[26px] border border-aubergine/10 bg-surface shadow-soft transition focus-within:border-terracotta/30 focus-within:ring-4 focus-within:ring-terracotta/10",
        variant === "hero" ? "px-3 py-2.5" : "px-3 py-2"
      )}
    >
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".pdf,application/pdf"
        onChange={onAttach}
        className="hidden"
      />
      <button
        type="button"
        aria-label="Attach papers"
        title="Attach PDF papers"
        onClick={() => fileInputRef.current?.click()}
        disabled={isUploading}
        className="mb-0.5 flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full text-aubergine/40 transition-colors hover:bg-cream-dark/30 hover:text-aubergine disabled:cursor-not-allowed disabled:opacity-40"
      >
        <Paperclip className="h-5 w-5" />
      </button>
      <textarea
        ref={textareaRef}
        rows={1}
        value={value}
        autoFocus={autoFocus}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        aria-label="Message"
        className="max-h-[200px] min-h-[40px] flex-1 resize-none bg-transparent py-2 text-sm leading-6 text-aubergine placeholder:text-aubergine/35 focus:outline-none"
      />
      <button
        type="button"
        aria-label="Send message"
        onClick={onSubmit}
        disabled={!canSend}
        className="mb-0.5 flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-terracotta text-surface shadow-soft transition hover:scale-105 active:scale-95 disabled:cursor-not-allowed disabled:bg-aubergine/15 disabled:text-aubergine/40 disabled:hover:scale-100 motion-reduce:transition-none motion-reduce:hover:scale-100"
      >
        <ArrowUp className="h-5 w-5" />
      </button>
    </div>
  );
}
