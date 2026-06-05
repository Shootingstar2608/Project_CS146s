import Spinner from "@/components/ui/Spinner";

export default function Loading() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3 text-aubergine/50">
      <Spinner className="h-8 w-8" />
      <p className="text-sm font-medium">Loading…</p>
    </div>
  );
}
