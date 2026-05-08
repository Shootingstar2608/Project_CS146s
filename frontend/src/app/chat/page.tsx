"use client";

import React from "react";
import { Plus, MessageSquare, Search, Send, Paperclip, ChevronRight, Share2, Maximize2 } from "lucide-react";

const ChatPage = () => {
  return (
    <div className="flex h-[calc(100vh-140px)] gap-6">
      {/* Left Chat History Sidebar */}
      <aside className="w-[280px] flex-shrink-0 flex flex-col bg-surface/50 rounded-[28px] overflow-hidden border border-aubergine/5">
        <div className="p-6 border-b border-aubergine/5">
            <h3 className="text-xs font-bold uppercase tracking-wider text-aubergine/40 mb-4">Conversations</h3>
            <button className="flex w-full items-center justify-center gap-2 rounded-xl border-2 border-dashed border-aubergine/10 py-3 text-sm font-bold text-aubergine/60 transition-colors hover:border-terracotta/40 hover:text-terracotta cursor-pointer">
                <Plus className="h-4 w-4" />
                <span>New chat</span>
            </button>
        </div>
        
        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-6">
            <div className="flex flex-col gap-2">
                <span className="px-2 text-[10px] font-bold uppercase tracking-wider text-aubergine/30">Today</span>
                <div className="flex flex-col gap-1">
                    <button className="flex items-center gap-3 rounded-xl bg-cream-dark/30 p-3 text-left border-l-4 border-terracotta cursor-pointer">
                        <MessageSquare className="h-4 w-4 text-terracotta" />
                        <span className="line-clamp-1 text-sm font-medium text-aubergine">Comparison of BERT and Transformer</span>
                    </button>
                </div>
            </div>
            
            <div className="flex flex-col gap-2">
                <span className="px-2 text-[10px] font-bold uppercase tracking-wider text-aubergine/30">Yesterday</span>
                <div className="flex flex-col gap-1">
                    <button className="flex items-center gap-3 rounded-xl p-3 text-left hover:bg-cream-dark/20 transition-colors cursor-pointer">
                        <MessageSquare className="h-4 w-4 text-aubergine/40" />
                        <span className="line-clamp-1 text-sm font-medium text-aubergine/60">Edge ML Survey 2023</span>
                    </button>
                </div>
            </div>
        </div>

        <div className="p-4 border-t border-aubergine/5">
            <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-aubergine/30" />
                <input 
                    type="text" 
                    placeholder="Search conversations..."
                    className="w-full rounded-lg bg-cream-dark/20 py-2 pl-9 pr-3 text-xs font-mono focus:outline-none"
                />
            </div>
        </div>
      </aside>

      {/* Center Conversation Pane */}
      <div className="flex flex-1 flex-col bg-surface rounded-[28px] shadow-soft overflow-hidden">
        <div className="p-6 border-b border-aubergine/5 flex flex-col gap-4">
            <h1 className="text-xl font-bold text-aubergine">Comparison of BERT and Transformer</h1>
            <div className="flex items-center gap-2">
                <div className="flex items-center gap-2 rounded-full bg-cream-dark/30 px-3 py-1 text-[10px] font-mono text-aubergine/60">
                    <div className="h-1.5 w-1.5 rounded-full bg-sage" />
                    <span>BERT-2018</span>
                </div>
                <div className="flex items-center gap-2 rounded-full bg-cream-dark/30 px-3 py-1 text-[10px] font-mono text-aubergine/60">
                    <div className="h-1.5 w-1.5 rounded-full bg-lilac" />
                    <span>Transformer-2017</span>
                </div>
            </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-8">
            {/* User Message */}
            <div className="flex justify-end">
                <div className="max-w-[70%] rounded-[20px] bg-terracotta p-4 text-surface text-sm leading-relaxed shadow-soft">
                    Compare the F1 scores of BERT and Transformer models on the SQuAD dataset as reported in their original papers.
                </div>
            </div>

            {/* Agent Message */}
            <div className="flex flex-col gap-3">
                <div className="flex flex-col rounded-[20px] border border-aubergine/5 bg-cream-dark/10 p-4">
                    <div className="mb-4 flex items-center gap-2 text-[10px] font-mono text-aubergine/40 border-b border-aubergine/5 pb-2">
                        <ChevronRight className="h-3 w-3" />
                        <span>Planning approach... done</span>
                    </div>
                    <div className="flex flex-col gap-4 text-sm text-aubergine leading-relaxed">
                        <p>Based on the knowledge graph, both models achieve significant results on SQuAD, though BERT demonstrates a clear improvement due to its bidirectional architecture.</p>
                        <p>According to <span className="font-mono text-terracotta underline decoration-terracotta/30 cursor-help">Vaswani et al., 2017</span>, the Transformer achieved a competitive score, while <span className="font-mono text-terracotta underline decoration-terracotta/30 cursor-help">Devlin et al., 2018</span> reported BERT reached an F1 score of 93.2 on SQuAD v1.1.</p>
                    </div>
                    
                    <div className="mt-6 flex items-center gap-4 border-t border-aubergine/5 pt-4">
                        <button className="text-[11px] font-bold uppercase tracking-wider text-terracotta cursor-pointer">Sources (2)</button>
                        <button className="text-[11px] font-bold uppercase tracking-wider text-aubergine/30 cursor-pointer">Reasoning trace</button>
                    </div>
                </div>
            </div>
        </div>

        <div className="p-6">
            <div className="relative flex items-end gap-3 rounded-2xl border border-aubergine/10 bg-surface p-3 shadow-soft focus-within:ring-2 focus-within:ring-terracotta/10">
                <button className="mb-1 p-2 text-aubergine/30 hover:text-aubergine transition-colors cursor-pointer">
                    <Paperclip className="h-5 w-5" />
                </button>
                <textarea 
                    rows={1}
                    placeholder="Ask a research question..."
                    className="flex-1 py-2 text-sm focus:outline-none resize-none"
                />
                <button className="rounded-xl bg-terracotta p-2 text-surface shadow-soft transition-transform hover:scale-105 active:scale-95 cursor-pointer">
                    <Send className="h-5 w-5" />
                </button>
            </div>
        </div>
      </div>

      {/* Right Graph Sidebar */}
      <aside className="w-[360px] flex-shrink-0 flex flex-col bg-surface/50 rounded-[28px] overflow-hidden border border-aubergine/5 relative">
        <div className="p-6 border-b border-aubergine/5 flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-aubergine/40">Reasoning Graph</h3>
            <Share2 className="h-4 w-4 text-aubergine/30" />
        </div>
        
        <div className="flex-1 flex items-center justify-center p-8">
            <div className="flex flex-col items-center gap-4 text-center">
                <div className="h-32 w-32 rounded-full border-2 border-dashed border-aubergine/10 flex items-center justify-center">
                    <Share2 className="h-12 w-12 text-aubergine/10" />
                </div>
                <p className="text-xs text-aubergine/30 max-w-[180px]">Ask a question to see the agent's reasoning path.</p>
            </div>
        </div>

        <div className="absolute bottom-6 right-6 flex flex-col gap-2">
            <button className="flex h-10 w-10 items-center justify-center rounded-xl bg-surface shadow-soft text-aubergine/60 hover:text-aubergine cursor-pointer">
                <Maximize2 className="h-5 w-5" />
            </button>
        </div>
      </aside>
    </div>
  );
};

export default ChatPage;
