"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import { FileText, Filter, Network, Search, Upload } from "lucide-react";
import { buildKnowledgeGraph, GraphNode, useResearchStore } from "@/lib/research-store";
import { cn } from "@/lib/utils";

type PositionedNode = GraphNode & {
  x: number;
  y: number;
};

const nodeStyles: Record<GraphNode["kind"], { fill: string; stroke: string; radius: number }> = {
  paper: { fill: "#C25A4D", stroke: "#A84D42", radius: 18 },
  category: { fill: "#BFD4BC", stroke: "#8FB28A", radius: 14 },
  author: { fill: "#D8C8E8", stroke: "#B7A2CC", radius: 12 },
  year: { fill: "#C5D4E0", stroke: "#9DB3C1", radius: 12 },
};

function positionNodes(nodes: GraphNode[]): PositionedNode[] {
  if (nodes.length === 0) return [];
  const centerX = 360;
  const centerY = 260;
  const paperNodes = nodes.filter((node) => node.kind === "paper");
  const contextNodes = nodes.filter((node) => node.kind !== "paper");

  const positionedPapers = paperNodes.map((node, index) => {
    const angle = (Math.PI * 2 * index) / Math.max(paperNodes.length, 1) - Math.PI / 2;
    const radius = paperNodes.length === 1 ? 0 : 150;
    return {
      ...node,
      x: centerX + Math.cos(angle) * radius,
      y: centerY + Math.sin(angle) * radius,
    };
  });

  const positionedContext = contextNodes.map((node, index) => {
    const angle = (Math.PI * 2 * index) / Math.max(contextNodes.length, 1) + Math.PI / 5;
    return {
      ...node,
      x: centerX + Math.cos(angle) * 235,
      y: centerY + Math.sin(angle) * 205,
    };
  });

  return [...positionedPapers, ...positionedContext];
}

export default function GraphPage() {
  const papers = useResearchStore((state) => state.papers);
  const [query, setQuery] = useState("");
  const [selectedNodeId, setSelectedNodeId] = useState<string>();

  const graph = useMemo(() => buildKnowledgeGraph(papers), [papers]);
  const visiblePaperIds = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return new Set(papers.map((paper) => paper.id));
    return new Set(
      papers
        .filter((paper) => `${paper.title} ${paper.category} ${paper.year ?? ""} ${paper.authors.join(" ")}`.toLowerCase().includes(normalized))
        .map((paper) => paper.id)
    );
  }, [papers, query]);

  const visibleGraph = useMemo(() => {
    const links = graph.links.filter((link) => visiblePaperIds.has(String(link.source)));
    const connectedIds = new Set<string>();
    links.forEach((link) => {
      connectedIds.add(String(link.source));
      connectedIds.add(String(link.target));
    });
    const nodes = graph.nodes.filter((node) => connectedIds.has(node.id));
    return { nodes, links };
  }, [graph, visiblePaperIds]);

  const positionedNodes = useMemo(() => positionNodes(visibleGraph.nodes), [visibleGraph.nodes]);
  const nodeById = useMemo(() => new Map(positionedNodes.map((node) => [node.id, node])), [positionedNodes]);
  const selectedNode = positionedNodes.find((node) => node.id === selectedNodeId);
  const selectedPaper = papers.find((paper) => paper.id === selectedNodeId);

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
        <div className="flex flex-col gap-1">
          <span className="text-sm font-medium text-aubergine/40">Knowledge graph</span>
          <h1 className="text-4xl font-extrabold tracking-tight text-aubergine">Graph</h1>
        </div>

        <div className="relative min-w-0 xl:w-[420px]">
          <Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-aubergine/40" />
          <input
            type="text"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Filter graph by paper, author, year..."
            className="h-12 w-full rounded-lg bg-surface pl-12 pr-4 text-sm shadow-soft focus:outline-none focus:ring-2 focus:ring-terracotta/20"
          />
        </div>
      </div>

      {papers.length === 0 ? (
        <div className="flex min-h-[520px] flex-col items-center justify-center rounded-[28px] border border-dashed border-aubergine/15 bg-surface/50 p-8 text-center">
          <div className="mb-5 flex h-20 w-20 items-center justify-center rounded-2xl bg-cream-dark/40 text-terracotta">
            <Network className="h-10 w-10" />
          </div>
          <h2 className="text-2xl font-extrabold text-aubergine">Graph is waiting for papers</h2>
          <p className="mt-2 max-w-md text-sm leading-6 text-aubergine/50">
            Upload documents to generate paper, category, author, and year nodes from the local library.
          </p>
          <Link href="/upload" className="mt-6 flex items-center gap-2 rounded-lg bg-terracotta px-6 py-3 font-bold text-surface shadow-soft">
            <Upload className="h-5 w-5" />
            Upload papers
          </Link>
        </div>
      ) : (
        <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
          <section className="overflow-hidden rounded-[28px] bg-surface shadow-soft">
            <div className="flex flex-col gap-4 border-b border-aubergine/5 p-5 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-terracotta text-surface">
                  <Network className="h-5 w-5" />
                </div>
                <div>
                  <h2 className="font-extrabold text-aubergine">Local knowledge graph</h2>
                  <p className="text-xs text-aubergine/45">
                    {visibleGraph.nodes.length} nodes | {visibleGraph.links.length} links
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2 text-[10px] font-bold uppercase tracking-wider text-aubergine/45">
                {Object.keys(nodeStyles).map((kind) => (
                  <span key={kind} className="flex items-center gap-2 rounded-full bg-cream-dark/35 px-3 py-1">
                    <span className={cn("h-2 w-2 rounded-full", kind === "paper" && "bg-terracotta", kind === "category" && "bg-sage", kind === "author" && "bg-lilac", kind === "year" && "bg-sky")} />
                    {kind}
                  </span>
                ))}
              </div>
            </div>

            <div className="overflow-x-auto bg-cream-light/40">
              <svg viewBox="0 0 720 520" className="h-[520px] min-w-[720px]">
                <g>
                  {visibleGraph.links.map((link) => {
                    const source = nodeById.get(String(link.source));
                    const target = nodeById.get(String(link.target));
                    if (!source || !target) return null;
                    const isActive = selectedNodeId === source.id || selectedNodeId === target.id;
                    return (
                      <line
                        key={`${link.source}-${link.target}-${link.label}`}
                        x1={source.x}
                        y1={source.y}
                        x2={target.x}
                        y2={target.y}
                        stroke={isActive ? "#C25A4D" : "#3A2E3D"}
                        strokeOpacity={isActive ? 0.45 : 0.12}
                        strokeWidth={isActive ? 2.5 : 1.5}
                      />
                    );
                  })}
                </g>
                <g>
                  {positionedNodes.map((node) => {
                    const style = nodeStyles[node.kind];
                    const isSelected = selectedNodeId === node.id;
                    return (
                      <g
                        key={node.id}
                        role="button"
                        tabIndex={0}
                        onClick={() => setSelectedNodeId(node.id)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") setSelectedNodeId(node.id);
                        }}
                        className="cursor-pointer"
                      >
                        <circle
                          cx={node.x}
                          cy={node.y}
                          r={isSelected ? style.radius + 5 : style.radius}
                          fill={style.fill}
                          stroke={isSelected ? "#3A2E3D" : style.stroke}
                          strokeWidth={isSelected ? 4 : 2}
                        />
                        <text
                          x={node.x}
                          y={node.y + style.radius + 18}
                          textAnchor="middle"
                          className="fill-aubergine text-[11px] font-bold"
                        >
                          {node.label.length > 24 ? `${node.label.slice(0, 24)}...` : node.label}
                        </text>
                      </g>
                    );
                  })}
                </g>
              </svg>
            </div>
          </section>

          <aside className="flex flex-col gap-6">
            <section className="rounded-[28px] bg-surface p-6 shadow-soft">
              <div className="flex items-center gap-3">
                <Filter className="h-5 w-5 text-terracotta" />
                <h2 className="text-sm font-bold uppercase tracking-wider text-aubergine/40">Selection</h2>
              </div>
              {selectedNode ? (
                <div className="mt-5">
                  <div className="text-xl font-extrabold text-aubergine">{selectedNode.label}</div>
                  <div className="mt-2 w-max rounded-full bg-cream-dark/40 px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-aubergine/45">
                    {selectedNode.kind}
                  </div>
                  {selectedPaper && (
                    <div className="mt-5 space-y-3 text-sm text-aubergine/60">
                      <p>{selectedPaper.abstract || "This paper currently has local file metadata only."}</p>
                      <Link href="/chat" className="inline-flex rounded-lg bg-terracotta px-4 py-3 font-bold text-surface">
                        Ask about this paper
                      </Link>
                    </div>
                  )}
                </div>
              ) : (
                <div className="mt-5 flex min-h-[180px] flex-col items-center justify-center rounded-2xl bg-cream-dark/20 p-5 text-center">
                  <FileText className="mb-3 h-8 w-8 text-aubergine/20" />
                  <p className="text-sm leading-6 text-aubergine/45">Select a node to inspect its local metadata.</p>
                </div>
              )}
            </section>

            <section className="rounded-[28px] bg-surface p-6 shadow-soft">
              <h2 className="text-sm font-bold uppercase tracking-wider text-aubergine/40">Graph contract</h2>
              <p className="mt-4 text-sm leading-6 text-aubergine/55">
                This MVP graph is built from uploaded local paper records. It mirrors the future backend schema with paper, category, author, and year relationships.
              </p>
            </section>
          </aside>
        </div>
      )}
    </div>
  );
}
