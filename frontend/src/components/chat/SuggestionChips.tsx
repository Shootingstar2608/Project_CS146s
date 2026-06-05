"use client";

import { BarChart3, Database, FileText, GitCompare } from "lucide-react";

const SUGGESTIONS = [
  {
    icon: FileText,
    label: "Summarize a paper",
    prompt: "Summarize the key contributions of one of my completed papers.",
  },
  {
    icon: GitCompare,
    label: "Compare two methods",
    prompt: "Compare two methods used across my papers and explain how they differ.",
  },
  {
    icon: Database,
    label: "Which datasets are used?",
    prompt: "Which datasets are used across my completed papers?",
  },
  {
    icon: BarChart3,
    label: "List key results",
    prompt: "List the key results and metrics reported across my papers.",
  },
];

/** Empty-state quick actions that prefill the composer (the user can edit before sending). */
export default function SuggestionChips({ onPick }: { onPick: (prompt: string) => void }) {
  return (
    <div className="flex flex-wrap items-center justify-center gap-2">
      {SUGGESTIONS.map(({ icon: Icon, label, prompt }) => (
        <button
          key={label}
          type="button"
          onClick={() => onPick(prompt)}
          className="flex items-center gap-2 rounded-full border border-aubergine/10 bg-surface px-4 py-2 text-sm font-medium text-aubergine/70 shadow-soft transition-colors hover:border-terracotta/30 hover:text-aubergine"
        >
          <Icon className="h-4 w-4 text-terracotta" />
          {label}
        </button>
      ))}
    </div>
  );
}
