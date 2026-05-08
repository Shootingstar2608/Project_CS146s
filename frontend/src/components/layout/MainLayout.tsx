"use client";

import React from "react";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

interface MainLayoutProps {
  children: React.ReactNode;
}

const MainLayout: React.FC<MainLayoutProps> = ({ children }) => {
  return (
    <div className="relative min-h-screen">
      <Sidebar />
      <div className="pl-20">
        <Topbar />
        <main className="mx-auto mt-[60px] max-w-[1400px] p-4 sm:p-6 lg:p-10">
          {children}
        </main>
      </div>
    </div>
  );
};

export default MainLayout;
