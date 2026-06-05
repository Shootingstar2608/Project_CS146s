"use client";

import Link from "next/link";
import { Download, FileText, ChevronLeft } from "lucide-react";
import { useParams } from "next/navigation";
import { getErrorMessage, resolveApiUrl } from "@/lib/api";
import { useDocuments } from "@/lib/queries";
import Spinner from "@/components/ui/Spinner";

export default function PaperDetailPage() {
  const params = useParams();
  const paperId = params.id as string;
  const { data: papers = [], isPending, isError, error } = useDocuments();
  const paper = papers.find((p) => p.id === paperId) ?? null;

  if (isPending) {
    return (
      <div className="flex min-h-[600px] items-center justify-center">
        <Spinner className="h-8 w-8" />
      </div>
    );
  }

  if (isError || !paper) {
    return (
      <div className="flex min-h-[600px] flex-col items-center justify-center gap-4">
        <FileText className="h-16 w-16 text-aubergine/20" />
        <p className="text-lg font-semibold text-aubergine">
          {isError ? getErrorMessage(error, "Error loading paper") : "Paper not found"}
        </p>
        <Link href="/papers" className="text-terracotta hover:underline">
          ← Back to papers
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/papers" className="flex items-center gap-2 text-terracotta hover:underline">
          <ChevronLeft className="h-4 w-4" />
          Papers
        </Link>
      </div>

      <div className="rounded-[28px] bg-surface p-8 shadow-soft">
        <div className="mb-6 flex items-start justify-between">
          <div className="flex-1">
            <h1 className="mb-3 text-3xl font-extrabold text-aubergine">{paper.title || paper.fileName}</h1>
            {paper.authors?.length > 0 && (
              <p className="mb-2 text-sm text-aubergine/60">
                <span className="font-semibold">Authors:</span> {paper.authors.join(", ")}
              </p>
            )}
            {paper.year && (
              <p className="mb-2 text-sm text-aubergine/60">
                <span className="font-semibold">Year:</span> {paper.year}
              </p>
            )}
            {paper.categories?.length > 0 && (
              <div className="mb-4 flex flex-wrap gap-2">
                {paper.categories.map((cat: string) => (
                  <span key={cat} className="inline-block rounded-full bg-cream-dark/30 px-3 py-1 text-xs font-semibold uppercase text-aubergine/60">
                    {cat}
                  </span>
                ))}
              </div>
            )}
          </div>
          {paper.downloadUrl && (
            <a
              href={resolveApiUrl(paper.downloadUrl)}
              download
              className="flex items-center gap-2 rounded-lg bg-terracotta px-4 py-3 font-semibold text-surface hover:bg-terracotta/90"
            >
              <Download className="h-4 w-4" />
              Download PDF
            </a>
          )}
        </div>

        {paper.abstract && (
          <div className="mb-8 border-t border-aubergine/10 pt-6">
            <h2 className="mb-3 text-lg font-bold text-aubergine">Abstract</h2>
            <p className="leading-relaxed text-aubergine/70">{paper.abstract}</p>
          </div>
        )}

        {paper.downloadUrl && (
          <div className="border-t border-aubergine/10 pt-6">
            <h2 className="mb-4 text-lg font-bold text-aubergine">Full Document</h2>
            <div className="rounded-lg bg-cream-light/40 p-4">
              <iframe
                src={resolveApiUrl(paper.downloadUrl)}
                width="100%"
                height="600"
                className="rounded-lg border border-aubergine/10"
              />
            </div>
            <p className="mt-3 text-center text-xs text-aubergine/50">
              If the PDF does not load, use the download button above to view it locally.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
