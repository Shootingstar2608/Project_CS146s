"use client";

import React from "react";
import { Search, Bell, Settings, User } from "lucide-react";

const Topbar = () => {
  return (
    <header className="fixed top-0 left-20 right-0 z-40 flex h-[60px] items-center justify-between bg-surface px-8 shadow-soft">
      <div className="flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-terracotta text-surface font-bold">
          M
        </div>
        <span className="text-lg font-bold tracking-tight text-aubergine">MLIoT Lab</span>
      </div>

      <div className="flex items-center gap-6">
        <div className="flex items-center gap-4 text-aubergine/60">
          <button className="hover:text-aubergine transition-colors cursor-pointer">
            <Search className="h-5 w-5" />
          </button>
          <button className="hover:text-aubergine transition-colors cursor-pointer">
            <Bell className="h-5 w-5" />
          </button>
          <button className="hover:text-aubergine transition-colors cursor-pointer">
            <Settings className="h-5 w-5" />
          </button>
        </div>
        
        <div className="flex items-center gap-3 border-l border-aubergine/10 pl-6">
          <div className="flex flex-col items-end">
            <span className="text-sm font-semibold text-aubergine leading-none">Researcher Name</span>
            <span className="text-[10px] font-bold uppercase tracking-wider text-terracotta/80 mt-1">
              Senior Researcher
            </span>
          </div>
          <div className="h-10 w-10 overflow-hidden rounded-full bg-cream-dark shadow-soft border-2 border-surface">
            <User className="h-full w-full p-2 text-aubergine/40" />
          </div>
        </div>
      </div>
    </header>
  );
};

export default Topbar;
