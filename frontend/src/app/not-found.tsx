import Link from "next/link";
import { Compass } from "lucide-react";

export default function NotFound() {
  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center px-6 text-center">
      <div className="mb-5 flex h-20 w-20 items-center justify-center rounded-2xl bg-cream-dark/40 text-terracotta">
        <Compass className="h-10 w-10" />
      </div>
      <p className="text-sm font-bold uppercase tracking-wider text-aubergine/40">404</p>
      <h1 className="mt-1 text-2xl font-extrabold text-aubergine">Page not found</h1>
      <p className="mt-2 max-w-md text-sm leading-6 text-aubergine/60">
        That route doesn&apos;t exist. The library is a good place to start.
      </p>
      <Link
        href="/papers"
        className="mt-6 rounded-lg bg-terracotta px-6 py-3 text-sm font-bold text-surface shadow-soft transition-transform hover:-translate-y-0.5 active:translate-y-0 motion-reduce:transition-none motion-reduce:hover:translate-y-0"
      >
        Go to library
      </Link>
    </div>
  );
}
