import type { Metadata, Viewport } from "next";
import { Plus_Jakarta_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import MainLayout from "@/components/layout/MainLayout";
import ReactQueryProvider from "@/components/providers/ReactQueryProvider";

const sans = Plus_Jakarta_Sans({
  variable: "--font-sans",
  subsets: ["latin"],
});

const mono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "MLIoT Knowledge Agent",
    template: "%s · MLIoT Knowledge Agent",
  },
  description:
    "Hybrid GraphRAG research assistant — query academic papers across a Neo4j knowledge graph and a vector index.",
};

export const viewport: Viewport = {
  themeColor: "#3A2E3D",
  colorScheme: "light",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${sans.variable} ${mono.variable} h-full antialiased`}
    >
      <body className="min-h-full font-sans text-primary">
        <ReactQueryProvider>
          <MainLayout>{children}</MainLayout>
        </ReactQueryProvider>
      </body>
    </html>
  );
}
