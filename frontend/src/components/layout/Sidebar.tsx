"use client";

import React from "react";
import { Library, MessageSquare, Share2, Upload, Settings, LogOut } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const Sidebar = () => {
  const pathname = usePathname();

  const navItems = [
    { icon: Library, href: "/papers", label: "Library" },
    { icon: MessageSquare, href: "/chat", label: "Chat" },
    { icon: Share2, href: "/graph", label: "Graph" },
    { icon: Upload, href: "/upload", label: "Upload" },
  ];

  return (
    <aside className="fixed left-0 top-0 z-50 flex h-full w-20 flex-col items-center bg-aubergine py-8 text-cream-light">
      <nav className="flex flex-1 flex-col gap-6">
        {navItems.map((item) => {
          const isActive = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "group relative flex h-12 w-12 items-center justify-center rounded-xl transition-all duration-200",
                isActive ? "bg-surface text-aubergine" : "text-cream-light/60 hover:text-cream-light"
              )}
            >
              <item.icon className="h-6 w-6" />
            </Link>
          );
        })}
      </nav>

      <div className="flex flex-col gap-6 text-cream-light/60">
        <button className="transition-colors hover:text-cream-light cursor-pointer">
          <Settings className="h-6 w-6" />
        </button>
        <button className="transition-colors hover:text-cream-light cursor-pointer">
          <LogOut className="h-6 w-6" />
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
