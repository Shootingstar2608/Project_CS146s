import { cn } from "@/lib/utils";

/** Neutral placeholder block used while data loads. */
export default function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-2xl bg-aubergine/10 motion-reduce:animate-none",
        className
      )}
      aria-hidden
    />
  );
}
