"use client";

import React, { ChangeEvent, DragEvent, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { CheckCircle2, FileText, FolderOpen, Library, UploadCloud, X } from "lucide-react";
import { formatFileSize, NewPaperInput, useResearchStore } from "@/lib/research-store";
import { cn } from "@/lib/utils";

const readableTypes = new Set([
  "text/plain",
  "text/markdown",
  "text/csv",
  "application/json",
]);

function canReadText(file: File) {
  return readableTypes.has(file.type) || /\.(txt|md|csv|json)$/i.test(file.name);
}

async function toPaperInput(file: File): Promise<NewPaperInput> {
  let abstract: string | undefined;

  if (canReadText(file)) {
    const text = await file.text();
    abstract = text.replace(/\s+/g, " ").trim().slice(0, 900);
  }

  return {
    fileName: file.name,
    fileType: file.type,
    fileSize: file.size,
    abstract,
  };
}

export default function UploadPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const papers = useResearchStore((state) => state.papers);
  const addPapers = useResearchStore((state) => state.addPapers);
  const [queuedFiles, setQueuedFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isIndexing, setIsIndexing] = useState(false);
  const [lastIndexedCount, setLastIndexedCount] = useState(0);

  const totalQueuedSize = useMemo(
    () => queuedFiles.reduce((total, file) => total + file.size, 0),
    [queuedFiles]
  );

  const appendFiles = (files: FileList | File[]) => {
    const incoming = Array.from(files);
    setQueuedFiles((current) => {
      const seen = new Set(current.map((file) => `${file.name}:${file.size}`));
      const next = incoming.filter((file) => !seen.has(`${file.name}:${file.size}`));
      return [...current, ...next];
    });
  };

  const handleInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) appendFiles(event.target.files);
    event.target.value = "";
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    appendFiles(event.dataTransfer.files);
  };

  const indexQueuedFiles = async () => {
    if (queuedFiles.length === 0) return;
    setIsIndexing(true);
    const inputs = await Promise.all(queuedFiles.map(toPaperInput));
    addPapers(inputs);
    setLastIndexedCount(inputs.length);
    setQueuedFiles([]);
    setIsIndexing(false);
  };

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-1">
        <span className="text-sm font-medium text-aubergine/40">Ingestion</span>
        <h1 className="text-4xl font-extrabold tracking-tight text-aubergine">Upload Papers</h1>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
        <section className="rounded-[28px] bg-surface p-6 shadow-soft sm:p-8">
          <div
            onDragOver={(event) => {
              event.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            className={cn(
              "flex min-h-[320px] flex-col items-center justify-center rounded-[24px] border-2 border-dashed p-8 text-center transition-colors",
              isDragging ? "border-terracotta bg-cream-dark/40" : "border-aubergine/10 bg-cream-dark/20"
            )}
          >
            <div className="mb-5 flex h-20 w-20 items-center justify-center rounded-2xl bg-surface text-terracotta shadow-soft">
              <UploadCloud className="h-10 w-10" />
            </div>
            <h2 className="text-2xl font-extrabold text-aubergine">Drop research files here</h2>
            <p className="mt-2 max-w-lg text-sm leading-6 text-aubergine/50">
              PDFs are indexed as local document records. Text, Markdown, CSV, and JSON files also contribute readable snippets to chat search.
            </p>
            <input
              ref={inputRef}
              type="file"
              multiple
              accept=".pdf,.txt,.md,.csv,.json,application/pdf,text/plain,text/markdown,text/csv,application/json"
              onChange={handleInputChange}
              className="hidden"
            />
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="mt-6 rounded-lg bg-aubergine px-6 py-3 font-bold text-surface shadow-soft transition-colors hover:bg-aubergine/90"
            >
              Choose files
            </button>
          </div>

          <div className="mt-6 flex flex-col gap-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 className="text-sm font-bold uppercase tracking-wider text-aubergine/40">Queue</h3>
                <p className="text-sm text-aubergine/50">
                  {queuedFiles.length} file{queuedFiles.length === 1 ? "" : "s"} selected
                  {queuedFiles.length > 0 ? ` | ${formatFileSize(totalQueuedSize)}` : ""}
                </p>
              </div>
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => setQueuedFiles([])}
                  disabled={queuedFiles.length === 0 || isIndexing}
                  className="rounded-lg px-4 py-3 text-sm font-bold text-aubergine/50 transition-colors hover:bg-cream-dark/30 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Clear
                </button>
                <button
                  type="button"
                  onClick={indexQueuedFiles}
                  disabled={queuedFiles.length === 0 || isIndexing}
                  className="rounded-lg bg-terracotta px-5 py-3 text-sm font-bold text-surface shadow-soft transition-transform hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0"
                >
                  {isIndexing ? "Indexing..." : "Index locally"}
                </button>
              </div>
            </div>

            {queuedFiles.length > 0 ? (
              <div className="grid gap-3 md:grid-cols-2">
                {queuedFiles.map((file) => (
                  <div key={`${file.name}:${file.size}`} className="flex items-center gap-3 rounded-2xl bg-cream-dark/25 p-4">
                    <FileText className="h-5 w-5 flex-shrink-0 text-terracotta" />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-bold text-aubergine">{file.name}</div>
                      <div className="text-xs text-aubergine/40">{formatFileSize(file.size)}</div>
                    </div>
                    <button
                      type="button"
                      aria-label={`Remove ${file.name}`}
                      onClick={() => setQueuedFiles((current) => current.filter((item) => item !== file))}
                      className="rounded-lg p-2 text-aubergine/35 hover:bg-surface hover:text-terracotta"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-2xl bg-cream-dark/20 p-5 text-sm text-aubergine/45">
                Queue files to index them into the local library.
              </div>
            )}
          </div>
        </section>

        <aside className="flex flex-col gap-6">
          <section className="rounded-[28px] bg-surface p-6 shadow-soft">
            <h2 className="text-sm font-bold uppercase tracking-wider text-aubergine/40">Local library</h2>
            <div className="mt-5 grid grid-cols-2 gap-3">
              <div className="rounded-2xl bg-cream-dark/30 p-4">
                <div className="text-3xl font-extrabold text-aubergine">{papers.length}</div>
                <div className="text-xs font-bold uppercase tracking-wider text-aubergine/40">Papers</div>
              </div>
              <div className="rounded-2xl bg-cream-dark/30 p-4">
                <div className="text-3xl font-extrabold text-aubergine">{papers.filter((paper) => paper.status === "indexed").length}</div>
                <div className="text-xs font-bold uppercase tracking-wider text-aubergine/40">Indexed</div>
              </div>
            </div>
            {lastIndexedCount > 0 && (
              <div className="mt-5 flex items-start gap-3 rounded-2xl bg-sage/25 p-4 text-sm text-aubergine/70">
                <CheckCircle2 className="mt-0.5 h-5 w-5 flex-shrink-0 text-[#5E9A6B]" />
                <span>{lastIndexedCount} file{lastIndexedCount === 1 ? "" : "s"} added to the library.</span>
              </div>
            )}
          </section>

          <section className="rounded-[28px] bg-surface p-6 shadow-soft">
            <h2 className="text-sm font-bold uppercase tracking-wider text-aubergine/40">Next actions</h2>
            <div className="mt-5 flex flex-col gap-3">
              <Link href="/papers" className="flex items-center gap-3 rounded-2xl bg-cream-dark/25 p-4 font-bold text-aubergine transition-colors hover:bg-cream-dark/45">
                <Library className="h-5 w-5 text-terracotta" />
                Review library
              </Link>
              <Link href="/graph" className="flex items-center gap-3 rounded-2xl bg-cream-dark/25 p-4 font-bold text-aubergine transition-colors hover:bg-cream-dark/45">
                <FolderOpen className="h-5 w-5 text-terracotta" />
                Open graph
              </Link>
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}
