import { AlertTriangle, RotateCw } from "lucide-react";

type ErrorStateProps = {
  title?: string;
  message?: string;
  onRetry?: () => void;
};

/** Inline error panel for failed data fetches, with an optional retry. */
export default function ErrorState({
  title = "Something went wrong",
  message = "The backend request failed. Check that the API is running and try again.",
  onRetry,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className="flex min-h-[260px] flex-col items-center justify-center rounded-[28px] border border-dashed border-terracotta/30 bg-rose/15 p-8 text-center"
    >
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-surface text-terracotta shadow-soft">
        <AlertTriangle className="h-8 w-8" />
      </div>
      <h2 className="text-lg font-extrabold text-aubergine">{title}</h2>
      <p className="mt-2 max-w-md text-sm leading-6 text-aubergine/60">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-5 inline-flex items-center gap-2 rounded-lg bg-terracotta px-5 py-3 text-sm font-bold text-surface shadow-soft transition-transform hover:-translate-y-0.5 active:translate-y-0 motion-reduce:transition-none motion-reduce:hover:translate-y-0"
        >
          <RotateCw className="h-4 w-4" />
          Try again
        </button>
      )}
    </div>
  );
}
