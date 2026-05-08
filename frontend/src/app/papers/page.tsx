"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import {
  FileText,
  LayoutGrid,
  List,
  MessageSquare,
  Plus,
  Search,
  Trash2,
} from "lucide-react";
import {
  formatFileSize,
  paperCategories,
  PaperCategory,
  PaperStatus,
  useResearchStore,
  ViewMode,
} from "@/lib/research-store";
import { cn } from "@/lib/utils";

const statusLabels: Record<PaperStatus, string> = {
  indexed: "Indexed",
  needs_review: "Needs review",
};

const categoryColors: Record<PaperCategory, string> = {
  "ML/AI": "bg-sage",
  "IoT/Hardware": "bg-rose",
  Networks: "bg-peach",
  Theory: "bg-lilac",
  Surveys: "bg-sky",
  Uncategorized: "bg-cream-dark",
};

export default function PapersPage() {
  const papers = useResearchStore((state) => state.papers);
  const removePaper = useResearchStore((state) => state.removePaper);
  const [query, setQuery] = useState("");
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [category, setCategory] = useState<PaperCategory | "all">("all");
  const [status, setStatus] = useState<PaperStatus | "all">("all");

  const filteredPapers = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return papers.filter((paper) => {
      const searchable = `${paper.title} ${paper.fileName} ${paper.category} ${paper.year ?? ""} ${paper.authors.join(" ")} ${paper.abstract ?? ""}`.toLowerCase();
      const matchesQuery = normalized.length === 0 || searchable.includes(normalized);
      const matchesCategory = category === "all" || paper.category === category;
      const matchesStatus = status === "all" || paper.status === status;
      return matchesQuery && matchesCategory && matchesStatus;
    });
  }, [category, papers, query, status]);

  const categoryCounts = useMemo(
    () =>
      paperCategories.reduce<Record<PaperCategory, number>>((counts, item) => {
        counts[item] = papers.filter((paper) => paper.category === item).length;
        return counts;
      }, {} as Record<PaperCategory, number>),
    [papers]
  );

  const clearFilters = () => {
    setQuery("");
    setCategory("all");
    setStatus("all");
  };

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
        <div className="flex flex-col gap-1">
          <span className="text-sm font-medium text-aubergine/40">Library</span>
          <h1 className="text-4xl font-extrabold tracking-tight text-aubergine">Papers</h1>
        </div>

        <div className="flex flex-col gap-3 md:flex-row md:items-center">
          <div className="relative min-w-0 md:w-[420px]">
            <Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-aubergine/40" />
            <input
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search by title, author, category..."
              className="h-12 w-full rounded-lg bg-surface pl-12 pr-4 text-sm shadow-soft focus:outline-none focus:ring-2 focus:ring-terracotta/20"
            />
          </div>

          <div className="flex h-12 w-max items-center rounded-lg bg-cream-dark/30 p-1">
            <button
              type="button"
              aria-label="Grid view"
              onClick={() => setViewMode("grid")}
              className={cn(
                "flex h-10 w-10 items-center justify-center rounded-md transition-colors",
                viewMode === "grid" ? "bg-surface text-aubergine shadow-soft" : "text-aubergine/40 hover:text-aubergine"
              )}
            >
              <LayoutGrid className="h-5 w-5" />
            </button>
            <button
              type="button"
              aria-label="List view"
              onClick={() => setViewMode("list")}
              className={cn(
                "flex h-10 w-10 items-center justify-center rounded-md transition-colors",
                viewMode === "list" ? "bg-surface text-aubergine shadow-soft" : "text-aubergine/40 hover:text-aubergine"
              )}
            >
              <List className="h-5 w-5" />
            </button>
          </div>

          <Link
            href="/upload"
            className="flex h-12 items-center justify-center gap-2 rounded-lg bg-terracotta px-6 font-bold text-surface shadow-soft transition-transform hover:-translate-y-0.5 active:translate-y-0"
          >
            <Plus className="h-5 w-5" />
            <span>Upload Papers</span>
          </Link>
        </div>
      </div>

      <div className="flex flex-col gap-8 lg:flex-row">
        <aside className="flex-shrink-0 lg:w-[260px]">
          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-1">
            <section className="flex flex-col gap-4">
              <h3 className="text-xs font-bold uppercase tracking-wider text-aubergine/40">Categories</h3>
              <div className="flex flex-col gap-2">
                {paperCategories.map((item) => (
                  <button
                    key={item}
                    type="button"
                    onClick={() => setCategory(item)}
                    className={cn(
                      "flex items-center justify-between rounded-lg px-2 py-2 text-left transition-colors",
                      category === item ? "bg-surface shadow-soft" : "hover:bg-surface/50"
                    )}
                  >
                    <span className="flex items-center gap-3">
                      <span className={cn("h-2 w-2 rounded-full", categoryColors[item])} />
                      <span className="text-sm font-medium text-aubergine/80">{item}</span>
                    </span>
                    <span className="text-xs font-bold text-aubergine/30">{categoryCounts[item]}</span>
                  </button>
                ))}
              </div>
            </section>

            <section className="flex flex-col gap-4">
              <h3 className="text-xs font-bold uppercase tracking-wider text-aubergine/40">Status</h3>
              <div className="flex flex-col gap-2">
                {(Object.keys(statusLabels) as PaperStatus[]).map((item) => (
                  <button
                    key={item}
                    type="button"
                    onClick={() => setStatus(item)}
                    className={cn(
                      "flex items-center gap-3 rounded-lg px-2 py-2 text-left transition-colors",
                      status === item ? "bg-surface shadow-soft" : "hover:bg-surface/50"
                    )}
                  >
                    <span className={cn("h-2 w-2 rounded-full", item === "indexed" ? "bg-[#5E9A6B]" : "bg-[#D9A547]")} />
                    <span className="text-sm font-medium text-aubergine/80">{statusLabels[item]}</span>
                  </button>
                ))}
              </div>
              <button type="button" onClick={clearFilters} className="text-left text-sm font-bold text-terracotta hover:underline">
                Clear filters
              </button>
            </section>
          </div>
        </aside>

        <div className="min-w-0 flex-1">
          {papers.length === 0 ? (
            <div className="flex min-h-[480px] flex-col items-center justify-center rounded-[28px] border border-dashed border-aubergine/15 bg-surface/50 p-8 text-center">
              <div className="mb-5 flex h-20 w-20 items-center justify-center rounded-2xl bg-cream-dark/40 text-terracotta">
                <FileText className="h-10 w-10" />
              </div>
              <h2 className="text-2xl font-extrabold text-aubergine">No papers indexed yet</h2>
              <p className="mt-2 max-w-md text-sm leading-6 text-aubergine/50">
                Upload PDFs or text notes to create a local research library. The graph and chat views will use the same data immediately.
              </p>
              <Link href="/upload" className="mt-6 rounded-lg bg-terracotta px-6 py-3 font-bold text-surface shadow-soft">
                Upload first paper
              </Link>
            </div>
          ) : filteredPapers.length === 0 ? (
            <div className="flex min-h-[360px] flex-col items-center justify-center rounded-[28px] bg-surface/50 p-8 text-center">
              <h2 className="text-xl font-extrabold text-aubergine">No matching papers</h2>
              <p className="mt-2 text-sm text-aubergine/50">Adjust the search or clear filters to see the full library.</p>
              <button type="button" onClick={clearFilters} className="mt-5 rounded-lg bg-aubergine px-5 py-3 font-bold text-surface">
                Clear filters
              </button>
            </div>
          ) : (
            <div className={cn(viewMode === "grid" ? "grid gap-5 md:grid-cols-2 xl:grid-cols-3" : "flex flex-col gap-4")}>
              {filteredPapers.map((paper) => (
                <article
                  key={paper.id}
                  className={cn(
                    "group overflow-hidden rounded-[20px] bg-surface shadow-soft transition-all hover:-translate-y-1 hover:shadow-deep",
                    viewMode === "list" && "flex flex-col sm:flex-row"
                  )}
                >
                  <div className={cn("h-28", categoryColors[paper.category], viewMode === "list" ? "sm:h-auto sm:w-28" : "w-full")} />
                  <div className="flex min-w-0 flex-1 flex-col p-5">
                    <div className="mb-3 flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <h2 className="line-clamp-2 text-lg font-extrabold leading-snug text-aubergine">{paper.title}</h2>
                        <p className="mt-1 line-clamp-1 text-xs text-aubergine/40">{paper.fileName}</p>
                      </div>
                      <button
                        type="button"
                        aria-label={`Remove ${paper.title}`}
                        onClick={() => removePaper(paper.id)}
                        className="rounded-lg p-2 text-aubergine/30 opacity-100 transition-colors hover:bg-cream-dark/40 hover:text-terracotta sm:opacity-0 sm:group-hover:opacity-100"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                    <p className="line-clamp-3 min-h-[60px] text-sm leading-5 text-aubergine/55">
                      {paper.abstract || "Metadata indexed locally. Add a text abstract during upload or edit later when backend extraction is available."}
                    </p>
                    <div className="mt-5 flex flex-wrap items-center gap-2 text-[10px] font-bold uppercase tracking-wider text-aubergine/45">
                      <span className="rounded-full bg-cream-dark/40 px-3 py-1">{paper.category}</span>
                      <span className="rounded-full bg-cream-dark/40 px-3 py-1">{statusLabels[paper.status]}</span>
                      {paper.year && <span className="rounded-full bg-cream-dark/40 px-3 py-1">{paper.year}</span>}
                      <span className="font-mono normal-case tracking-normal">{formatFileSize(paper.fileSize)}</span>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>
      </div>

      <Link
        href="/chat"
        aria-label="Open research chat"
        className="fixed bottom-8 right-8 flex h-16 w-16 items-center justify-center rounded-full bg-terracotta text-surface shadow-[0_8px_30px_rgb(194,90,77,0.4)] transition-transform hover:scale-110 active:scale-95 sm:h-20 sm:w-20"
      >
        <MessageSquare className="h-7 w-7 sm:h-8 sm:w-8" />
      </Link>
    </div>
  );
}
