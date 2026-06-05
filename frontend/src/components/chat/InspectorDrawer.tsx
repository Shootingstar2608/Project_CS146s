"use client";

import { useEffect } from "react";
import Link from "next/link";
import { Maximize2, Share2, X } from "lucide-react";
import { BackendPaper } from "@/lib/api";
import { cn } from "@/lib/utils";

type InspectorTab = "sources" | "trace";

type Props = {
  open: boolean;
  onClose: () => void;
  tab: InspectorTab;
  onTabChange: (tab: InspectorTab) => void;
  sourcePapers: BackendPaper[];
  reasoningSteps: string[];
};

/** Right slide-in drawer with the Sources / Trace inspector for an answer. */
export default function InspectorDrawer({
  open,
  onClose,
  tab,
  onTabChange,
  sourcePapers,
  reasoningSteps,
}: Props) {
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

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
        aria-label="Answer details"
        aria-hidden={!open}
        className={cn(
          "absolute inset-y-0 right-0 z-30 flex w-[360px] max-w-[88%] flex-col border-l border-aubergine/10 bg-surface shadow-deep transition-transform duration-200",
          open ? "translate-x-0" : "pointer-events-none translate-x-[110%]"
        )}
      >
        <div className="flex items-center justify-between border-b border-aubergine/5 px-5 py-4">
          <h3 className="text-xs font-bold uppercase tracking-wider text-aubergine/40">Answer details</h3>
          <div className="flex items-center gap-1">
            <Link
              href="/graph"
              aria-label="Open full graph"
              title="Open full graph"
              className="flex h-8 w-8 items-center justify-center rounded-lg text-aubergine/50 transition-colors hover:bg-cream-dark/30 hover:text-aubergine"
            >
              <Maximize2 className="h-4 w-4" />
            </Link>
            <button
              type="button"
              aria-label="Close details"
              onClick={onClose}
              className="flex h-8 w-8 items-center justify-center rounded-lg text-aubergine/40 transition-colors hover:bg-cream-dark/30 hover:text-aubergine"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="flex gap-2 border-b border-aubergine/5 p-4">
          {(["sources", "trace"] as InspectorTab[]).map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => onTabChange(item)}
              className={cn(
                "flex-1 rounded-xl px-3 py-2 text-xs font-bold uppercase tracking-wider transition-colors",
                tab === item ? "bg-cream-dark/30 text-terracotta" : "text-aubergine/35 hover:text-aubergine/60"
              )}
            >
              {item}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          {tab === "sources" ? (
            sourcePapers.length > 0 ? (
              <div className="flex flex-col gap-3">
                {sourcePapers.map((paper) => (
                  <Link
                    key={paper.id}
                    href={`/papers/${paper.id}`}
                    className="block rounded-2xl bg-cream-dark/20 p-4 transition-colors hover:bg-cream-dark/35"
                  >
                    <div className="line-clamp-2 text-sm font-extrabold text-aubergine">{paper.title}</div>
                    <div className="mt-2 text-[10px] font-bold uppercase tracking-wider text-aubergine/40">
                      {paper.categories?.join(", ")}
                      {paper.year ? ` | ${paper.year}` : ""}
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <div className="flex min-h-[220px] flex-col items-center justify-center text-center">
                <div className="mb-4 flex h-24 w-24 items-center justify-center rounded-full border-2 border-dashed border-aubergine/10">
                  <Share2 className="h-9 w-9 text-aubergine/15" />
                </div>
                <p className="max-w-[200px] text-xs leading-5 text-aubergine/45">
                  No cited sources for this answer yet.
                </p>
              </div>
            )
          ) : (
            <ol className="flex flex-col gap-3 text-sm text-aubergine/60">
              {(reasoningSteps.length
                ? reasoningSteps
                : ["No retrieval trace for this answer yet."]
              ).map((step, index) => (
                <li key={`${step}-${index}`} className="rounded-2xl bg-cream-dark/20 p-4">
                  <span className="font-bold text-aubergine/40">{index + 1}.</span> {step}
                </li>
              ))}
            </ol>
          )}
        </div>
      </aside>
    </>
  );
}
