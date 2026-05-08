"use client";

import React from "react";
import { Plus, Search, LayoutGrid, List, ChevronDown, MessageSquare } from "lucide-react";
import { cn } from "@/lib/utils";

import Link from "next/link";

const PapersPage = () => {
  return (
    <div className="flex flex-col gap-10">
      {/* Page Header */}
      <div className="flex items-end justify-between">
        <div className="flex flex-col gap-1">
          <span className="text-sm font-medium text-aubergine/40">Library</span>
          <h1 className="text-4xl font-extrabold tracking-tight text-aubergine">Papers</h1>
        </div>

        <div className="flex items-center gap-4">
          <div className="relative">
            <Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-aubergine/40" />
            <input
              type="text"
              placeholder="Search by title, author, or DOI..."
              className="h-12 w-[480px] rounded-lg bg-surface pl-12 pr-4 text-sm shadow-soft focus:outline-none focus:ring-2 focus:ring-terracotta/20"
            />
          </div>
          
          <div className="flex h-12 items-center rounded-lg bg-cream-dark/30 p-1">
            <button className="flex h-10 w-10 items-center justify-center rounded-md bg-surface text-aubergine shadow-soft">
              <LayoutGrid className="h-5 w-5" />
            </button>
            <button className="flex h-10 w-10 items-center justify-center rounded-md text-aubergine/40">
              <List className="h-5 w-5" />
            </button>
          </div>

          <button className="flex h-12 items-center gap-2 rounded-lg bg-terracotta px-6 font-bold text-surface shadow-soft transition-transform hover:-translate-y-0.5 active:translate-y-0">
            <Plus className="h-5 w-5" />
            <span>Upload Papers</span>
          </button>
        </div>
      </div>

      <div className="flex gap-8">
        {/* Filter Sidebar */}
        <aside className="w-[280px] flex-shrink-0 flex flex-col gap-8">
            <section className="flex flex-col gap-4">
                <h3 className="text-xs font-bold uppercase tracking-wider text-aubergine/40">Categories</h3>
                <div className="flex flex-col gap-3">
                    {[
                        { label: "ML/AI", color: "bg-sage", count: 47 },
                        { label: "IoT/Hardware", color: "bg-rose", count: 12 },
                        { label: "Networks", color: "bg-peach", count: 8 },
                        { label: "Theory", color: "bg-lilac", count: 5 },
                        { label: "Surveys", color: "bg-sky", count: 3 },
                    ].map((cat) => (
                        <label key={cat.label} className="flex items-center justify-between cursor-pointer group">
                            <div className="flex items-center gap-3">
                                <div className={cn("h-2 w-2 rounded-full", cat.color)} />
                                <span className="text-sm font-medium text-aubergine/80 group-hover:text-aubergine">{cat.label}</span>
                            </div>
                            <span className="text-xs font-bold text-aubergine/30">{cat.count}</span>
                        </label>
                    ))}
                </div>
            </section>
            
            <section className="flex flex-col gap-4">
                <h3 className="text-xs font-bold uppercase tracking-wider text-aubergine/40">Status</h3>
                <div className="flex flex-col gap-3">
                    {[
                        { label: "Indexed", color: "bg-[#5E9A6B]" },
                        { label: "Processing", color: "bg-[#D9A547]" },
                        { label: "Failed", color: "bg-[#A8362A]" },
                    ].map((status) => (
                        <label key={status.label} className="flex items-center gap-3 cursor-pointer group">
                            <div className={cn("h-2 w-2 rounded-full", status.color)} />
                            <span className="text-sm font-medium text-aubergine/80 group-hover:text-aubergine">{status.label}</span>
                        </label>
                    ))}
                </div>
            </section>

            <button className="text-sm font-bold text-terracotta hover:underline text-left">
                Clear filters
            </button>
        </aside>

        {/* Main Content */}
        <div className="flex-1 flex flex-col gap-10">
            {/* Featured Row */}
            <div className="grid grid-cols-2 gap-6">
                {[1, 2].map((i) => (
                    <div key={i} className="group relative flex h-[200px] overflow-hidden rounded-[28px] bg-surface shadow-soft transition-all hover:-translate-y-1 hover:shadow-deep">
                        <div className={cn("w-[160px] h-full", i === 1 ? "bg-sage/40" : "bg-lilac/40")} />
                        <div className="flex flex-1 flex-col p-6">
                            <div className="mb-2 inline-flex self-start rounded-full bg-cream-dark/30 px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-aubergine/60">
                                Featured
                            </div>
                            <h2 className="mb-2 line-clamp-2 text-xl font-bold leading-tight text-aubergine">
                                {i === 1 ? "Attention Is All You Need" : "BERT: Pre-training of Deep Bidirectional Transformers"}
                            </h2>
                            <p className="line-clamp-2 text-sm text-aubergine/60 mb-4">
                                {i === 1 
                                    ? "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks..." 
                                    : "We introduce a new language representation model called BERT, which stands for Bidirectional Encoder Representations..."}
                            </p>
                            <div className="mt-auto flex items-center justify-between">
                                <div className="flex -space-x-2">
                                    {[1, 2, 3].map(a => (
                                        <div key={a} className="h-6 w-6 rounded-full border-2 border-surface bg-cream-dark" />
                                    ))}
                                </div>
                                <span className="font-mono text-[10px] text-aubergine/40">NIPS 2017</span>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Paper Grid */}
            <div className="grid grid-cols-4 gap-6">
                {Array.from({ length: 8 }).map((_, i) => (
                    <div key={i} className="group flex flex-col overflow-hidden rounded-[20px] bg-surface shadow-soft transition-all hover:-translate-y-1 hover:shadow-deep">
                        <div className={cn("h-[100px] w-full", ["bg-rose/30", "bg-sky/30", "bg-peach/30", "bg-sage/30"][i % 4])} />
                        <div className="flex flex-col p-5">
                            <h3 className="mb-1 line-clamp-2 text-base font-bold leading-snug text-aubergine">
                                Large Language Models are Zero-Shot Reasoners
                            </h3>
                            <p className="mb-3 line-clamp-1 text-xs text-aubergine/40">
                                Kojima et al.
                            </p>
                            <span className="mt-auto font-mono text-[10px] text-aubergine/40">NeurIPS 2022</span>
                        </div>
                    </div>
                ))}
            </div>
        </div>
      </div>

      {/* Floating Chat Button */}
      <Link href="/chat" className="fixed bottom-10 right-10 flex h-20 w-20 items-center justify-center rounded-full bg-terracotta text-surface shadow-[0_8px_30px_rgb(194,90,77,0.4)] transition-transform hover:scale-110 active:scale-95">
        <MessageSquare className="h-8 w-8" />
      </Link>
    </div>
  );
};

export default PapersPage;
