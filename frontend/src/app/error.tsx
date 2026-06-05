"use client";

import { useEffect } from "react";
import Link from "next/link";
import { AlertTriangle, RotateCw } from "lucide-react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Surface to the console / monitoring; replace with your reporter.
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center px-6 text-center">
      <div className="mb-5 flex h-20 w-20 items-center justify-center rounded-2xl bg-rose/30 text-terracotta">
        <AlertTriangle className="h-10 w-10" />
      </div>
      <h1 className="text-2xl font-extrabold text-aubergine">Something broke on this page</h1>
      <p className="mt-2 max-w-md text-sm leading-6 text-aubergine/60">
        An unexpected error occurred while rendering. You can retry, or head back to the library.
      </p>
      <div className="mt-6 flex items-center gap-3">
        <button
          type="button"
          onClick={reset}
          className="inline-flex items-center gap-2 rounded-lg bg-terracotta px-5 py-3 text-sm font-bold text-surface shadow-soft transition-transform hover:-translate-y-0.5 active:translate-y-0 motion-reduce:transition-none motion-reduce:hover:translate-y-0"
        >
          <RotateCw className="h-4 w-4" />
          Try again
        </button>
        <Link
          href="/papers"
          className="rounded-lg px-5 py-3 text-sm font-bold text-aubergine/60 transition-colors hover:bg-cream-dark/30"
        >
          Back to library
        </Link>
      </div>
    </div>
  );
}
