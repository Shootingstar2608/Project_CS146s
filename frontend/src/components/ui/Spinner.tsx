import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export default function Spinner({ className }: { className?: string }) {
  return (
    <Loader2
      className={cn("h-5 w-5 animate-spin text-terracotta motion-reduce:animate-none", className)}
      aria-hidden
    />
  );
}
