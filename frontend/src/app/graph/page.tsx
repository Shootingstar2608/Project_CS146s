"use client";

import React, { useMemo, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { FileText, Filter, Network, Search, Upload } from "lucide-react";
import { GraphNode } from "@/lib/research-store";
import { cn } from "@/lib/utils";

type PositionedNode = GraphNode & {
  x: number;
  y: number;
};

type GraphEdge = {
  source: string | { id: string; x?: number; y?: number };
  target: string | { id: string; x?: number; y?: number };
  label: string;
  properties?: Record<string, unknown>;
};

type ForceGraphProps = {
  graphData: { nodes: PositionedNode[]; links: GraphEdge[] };
  nodeId: string;
  nodeLabel: (node: PositionedNode) => string;
  linkLabel: (link: GraphEdge) => string;
  width: number;
  height: number;
  backgroundColor: string;
  nodeCanvasObject: (node: PositionedNode, ctx: CanvasRenderingContext2D, globalScale: number) => void;
  nodePointerAreaPaint: (node: PositionedNode, color: string, ctx: CanvasRenderingContext2D) => void;
  linkCanvasObject: (link: GraphEdge, ctx: CanvasRenderingContext2D, globalScale: number) => void;
  linkCanvasObjectMode: (link: GraphEdge) => string;
  linkColor: (link: GraphEdge) => string;
  linkOpacity: number;
  linkDirectionalArrowLength: number;
  linkDirectionalArrowRelPos: number;
  nodeRelSize: number;
  cooldownTicks: number;
  d3AlphaDecay: number;
  d3VelocityDecay: number;
  enableNodeDrag: boolean;
  enableZoomInteraction: boolean;
  onNodeHover: (node: PositionedNode | null) => void;
  onNodeClick: (node: PositionedNode) => void;
  onBackgroundClick: () => void;
};

const ForceGraph2D = dynamic(
  () => import("react-force-graph-2d").then((mod) => mod.default as React.ComponentType<ForceGraphProps>),
  { ssr: false }
) as React.ComponentType<ForceGraphProps>;

const nodeStyles: Record<GraphNode["kind"], { fill: string; stroke: string; radius: number }> = {
  paper: { fill: "#C25A4D", stroke: "#A84D42", radius: 18 },
  author: { fill: "#D8C8E8", stroke: "#B7A2CC", radius: 12 },
  organization: { fill: "#F0C7A9", stroke: "#D6996D", radius: 12 },
  conference: { fill: "#CFE2F3", stroke: "#97B7D1", radius: 12 },
  topic: { fill: "#BFD4BC", stroke: "#8FB28A", radius: 12 },
  task: { fill: "#E7D7B8", stroke: "#C9B07A", radius: 12 },
  methodology: { fill: "#F1D0D5", stroke: "#D69AA6", radius: 12 },
  dataset: { fill: "#D7E3D0", stroke: "#9FB191", radius: 12 },
  result: { fill: "#C8D7E8", stroke: "#93A8C2", radius: 12 },
  year: { fill: "#C5D4E0", stroke: "#9DB3C1", radius: 12 },
  category: { fill: "#BFD4BC", stroke: "#8FB28A", radius: 12 },
};

const kindOrder: GraphNode["kind"][] = [
  "author",
  "organization",
  "conference",
  "topic",
  "task",
  "methodology",
  "dataset",
  "result",
  "year",
  "category",
];

const kindAngles: Record<GraphNode["kind"], number> = {
  paper: 0,
  author: Math.PI,
  organization: (Math.PI * 5) / 6,
  conference: -Math.PI / 2,
  topic: (Math.PI * 2) / 3,
  task: -Math.PI / 3,
  methodology: Math.PI / 3,
  dataset: -Math.PI / 6,
  result: Math.PI / 2,
  year: (Math.PI * 11) / 6,
  category: -Math.PI * 0.9,
};

function prettyKind(kind: GraphNode["kind"]) {
  return kind.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatEdgeLabel(label: string) {
  return label.replace(/_/g, " ");
}

function resolveNodeId(nodeRef: GraphEdge["source"] | GraphEdge["target"]) {
  return typeof nodeRef === "string" ? nodeRef : nodeRef.id;
}

function drawLabelBubble(
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  textSize: number,
  globalScale: number
) {
  ctx.font = `${textSize / globalScale}px Inter, sans-serif`;
  const metrics = ctx.measureText(text);
  const width = Math.min(260 / globalScale, Math.max(96 / globalScale, metrics.width + 18 / globalScale));
  const height = 22 / globalScale;
  const rectX = x - width / 2;
  const rectY = y - height / 2;

  ctx.fillStyle = "rgba(255, 249, 243, 0.98)";
  ctx.strokeStyle = "rgba(194, 90, 77, 0.25)";
  ctx.lineWidth = 1 / globalScale;
  ctx.beginPath();
  ctx.roundRect(rectX, rectY, width, height, 10 / globalScale);
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = "#3A2E3D";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, x, y + 0.5 / globalScale);
}

function stableHash(value: string) {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) % 1000003;
  }
  return hash;
}

function seededJitter(value: string, spread: number) {
  return ((stableHash(value) % 1000) / 999 - 0.5) * spread;
}

// Deterministic grouped layout so the graph stays readable across renders.
function layoutGraph(nodes: GraphNode[], edges: GraphEdge[]): PositionedNode[] {
  if (nodes.length === 0) return [];

  const canvasW = 720;
  const canvasH = 520;
  const padding = 60;
  const centerX = canvasW / 2;
  const centerY = canvasH / 2;

  const positions: Record<string, { x: number; y: number; vx: number; vy: number }> = {};
  const paperNodes = nodes.filter((n) => n.kind === "paper");
  const otherNodes = nodes.filter((n) => n.kind !== "paper");

  const paperCols = Math.max(1, Math.ceil(Math.sqrt(paperNodes.length)));
  const paperRows = Math.ceil(paperNodes.length / paperCols);
  const cellW = (canvasW - 2 * padding) / paperCols;
  const cellH = (canvasH - 2 * padding) / paperRows;

  paperNodes.forEach((node, i) => {
    const col = i % paperCols;
    const row = Math.floor(i / paperCols);
    positions[node.id] = {
      x: padding + cellW * (col + 0.5) + seededJitter(node.id, 28),
      y: padding + cellH * (row + 0.5) + seededJitter(`${node.id}:y`, 28),
      vx: 0,
      vy: 0,
    };
  });

  const adjacency: Record<string, string[]> = {};
  edges.forEach((e) => {
    const s = String(e.source);
    const t = String(e.target);
    adjacency[s] = adjacency[s] || [];
    adjacency[t] = adjacency[t] || [];
    adjacency[s].push(t);
    adjacency[t].push(s);
  });

  const paperLookup = new Set(paperNodes.map((node) => node.id));
  const kindSlots = new Map<string, number>();

  otherNodes.forEach((node) => {
    const conns = adjacency[String(node.id)] || [];
    const connectedPaperId = conns.find((nid) => paperLookup.has(nid));
    if (connectedPaperId && positions[connectedPaperId]) {
      const paperPos = positions[connectedPaperId];
      const kindCount = kindSlots.get(node.kind) ?? 0;
      kindSlots.set(node.kind, kindCount + 1);
      const angle = ((stableHash(`${node.kind}:${node.id}`) % 360) / 360) * Math.PI * 2;
      const ring = 52 + (kindCount % 3) * 18;
      positions[node.id] = {
        x: Math.max(padding, Math.min(canvasW - padding, paperPos.x + Math.cos(angle) * ring)),
        y: Math.max(padding, Math.min(canvasH - padding, paperPos.y + Math.sin(angle) * ring)),
        vx: 0,
        vy: 0,
      };
    } else {
      const kindIndex = Math.max(0, kindOrder.indexOf(node.kind as (typeof kindOrder)[number]));
      const baseAngle = kindAngles[node.kind] ?? (kindIndex / Math.max(1, kindOrder.length)) * Math.PI * 2;
      const angle = baseAngle + seededJitter(`${node.id}:angle`, 0.45);
      const dist = 132 + kindIndex * 13 + seededJitter(`${node.id}:dist`, 34);
      positions[node.id] = {
        x: centerX + Math.cos(angle) * dist,
        y: centerY + Math.sin(angle) * dist,
        vx: 0,
        vy: 0,
      };
    }
  });

  return nodes.map((node) => ({
    ...node,
    x: positions[node.id].x,
    y: positions[node.id].y,
  }));
}

function positionNodes(nodes: GraphNode[], edges: GraphEdge[] = []): PositionedNode[] {
  return layoutGraph(nodes, edges);
}

export default function GraphPage() {
  type PaperSummary = {
    id: string;
    title?: string;
    fileName?: string;
    abstract?: string;
  };

  const [papers, setPapers] = useState<PaperSummary[]>([]);
  const [viewPaperId, setViewPaperId] = useState<string | "global">("global");
  const [query, setQuery] = useState("");
  const [selectedNodeId, setSelectedNodeId] = useState<string>();
  const [hoveredNodeId, setHoveredNodeId] = useState<string>();
  const [graphData, setGraphData] = useState<{ nodes: GraphNode[]; links: GraphEdge[] }>({ nodes: [], links: [] });

  React.useEffect(() => {
    import("@/lib/api").then(({ getDocuments, getGraphData }) => {
      getDocuments().then(setPapers).catch(console.error);
      // Load global graph by default
      getGraphData().then(setGraphData).catch(console.error);

      // If user picks a paper later, we'll call getGraphSubgraph
    });
  }, []);

  const visibleGraph = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (normalized.length > 0) {
      const visibleNodeIds = new Set(
        graphData.nodes
          .filter((node) => {
            const haystack = `${node.label} ${node.kind} ${(node.aliases ?? []).join(" ")} ${node.description ?? ""}`.toLowerCase();
            return haystack.includes(normalized);
          })
          .map((node) => node.id)
      );
      const links = graphData.links.filter((link) => visibleNodeIds.has(String(link.source)) || visibleNodeIds.has(String(link.target)));
      const connectedIds = new Set<string>();
      links.forEach((link) => {
        connectedIds.add(String(link.source));
        connectedIds.add(String(link.target));
      });
      const nodes = graphData.nodes.filter((node) => connectedIds.has(node.id) || visibleNodeIds.has(node.id));
      return { nodes, links };
    }
    // Mặc định hiện toàn bộ graph (Backend đã limit sẵn 200 nodes)
    return graphData;
  }, [graphData, query]);

  const positionedNodes = useMemo(() => positionNodes(visibleGraph.nodes, visibleGraph.links), [visibleGraph.nodes, visibleGraph.links]);
  const nodeById = useMemo(() => new Map(positionedNodes.map((node) => [node.id, node])), [positionedNodes]);
  const selectedNode = positionedNodes.find((node) => node.id === selectedNodeId);
  const activeNodeId = hoveredNodeId ?? selectedNodeId;
  const selectedPaper = papers.find((paper) => paper.title === selectedNode?.label);
  const connectedEdges = useMemo(
    () => visibleGraph.links.filter((link) => String(link.source) === selectedNodeId || String(link.target) === selectedNodeId),
    [selectedNodeId, visibleGraph.links]
  );
  const forceGraphData = useMemo(
    () => ({
      nodes: positionedNodes,
      links: visibleGraph.links,
    }),
    [positionedNodes, visibleGraph.links]
  );

  const renderNode = (node: PositionedNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const style = nodeStyles[node.kind];
    const isActive = activeNodeId === node.id;
    const radius = isActive ? style.radius + 5 : style.radius;

    ctx.beginPath();
    ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false);
    ctx.fillStyle = style.fill;
    ctx.fill();
    ctx.lineWidth = isActive ? 4 : 2;
    ctx.strokeStyle = isActive ? "#3A2E3D" : style.stroke;
    ctx.stroke();

    if (isActive) {
      const shortLabel = node.label.length > 38 ? `${node.label.slice(0, 38)}…` : node.label;
      const labelY = node.y > 330 ? node.y - radius - 18 : node.y + radius + 20;
      drawLabelBubble(ctx, shortLabel, node.x, labelY, 10, globalScale);
    }
  };

  const renderLink = (link: GraphEdge, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const sourceId = resolveNodeId(link.source);
    const targetId = resolveNodeId(link.target);
    const isActive = selectedNodeId === sourceId || selectedNodeId === targetId;
    const sourceNode = nodeById.get(sourceId);
    const targetNode = nodeById.get(targetId);
    if (!sourceNode || !targetNode) return;

    const midX = (sourceNode.x + targetNode.x) / 2;
    const midY = (sourceNode.y + targetNode.y) / 2;

    ctx.save();
    ctx.strokeStyle = isActive ? "rgba(194, 90, 77, 0.55)" : "rgba(58, 46, 61, 0.12)";
    ctx.lineWidth = isActive ? 2.5 : 1.5;
    ctx.beginPath();
    ctx.moveTo(sourceNode.x, sourceNode.y);
    ctx.lineTo(targetNode.x, targetNode.y);
    ctx.stroke();

    if (isActive) {
      drawLabelBubble(ctx, formatEdgeLabel(link.label), midX, midY - 10, 9, globalScale);
    }

    ctx.restore();
  };

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
            Upload documents to generate paper, author, topic, method, dataset, result, and year nodes from the local library.
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
                  <h2 className="font-extrabold text-aubergine">Global knowledge graph</h2>
                  <p className="text-xs text-aubergine/45">
                    {visibleGraph.nodes.length} nodes | {visibleGraph.links.length} links
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <label className="text-xs text-aubergine/45">View:</label>
                <select
                  value={viewPaperId}
                  onChange={async (e) => {
                    const val = e.target.value;
                    setViewPaperId(val as string);
                    const api = await import('@/lib/api');
                    try {
                      if (val === 'global') {
                        const g = await api.getGraphData();
                        setGraphData(g);
                      } else {
                        const g = await api.getGraphSubgraph(val);
                        setGraphData(g);
                      }
                      setSelectedNodeId(undefined);
                    } catch (err) {
                      console.error(err);
                    }
                  }}
                  className="rounded-md bg-surface px-2 py-1 text-sm"
                >
                  <option value="global">Global graph</option>
                  {papers.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.title || p.fileName || p.id}
                    </option>
                  ))}
                </select>
                <span className="ml-2 rounded-lg bg-cream-dark/40 px-3 py-2 text-xs text-aubergine/55">Drag nodes, scroll to zoom</span>
              </div>
              <div className="flex flex-wrap gap-2 text-[10px] font-bold uppercase tracking-wider text-aubergine/45">
                {kindOrder.map((kind) => (
                  <span key={kind} className="flex items-center gap-2 rounded-full bg-cream-dark/35 px-3 py-1">
                    <span className={cn("h-2 w-2 rounded-full", kind === "author" && "bg-lilac", kind === "organization" && "bg-amber-400", kind === "conference" && "bg-sky", kind === "topic" && "bg-sage", kind === "task" && "bg-yellow-600", kind === "methodology" && "bg-rose-400", kind === "dataset" && "bg-emerald-500", kind === "result" && "bg-slate-400", kind === "year" && "bg-sky-500", kind === "category" && "bg-sage")}></span>
                    {prettyKind(kind)}
                  </span>
                ))}
              </div>
            </div>

            <div className="overflow-x-auto bg-cream-light/40">
              <div className="h-[520px] min-w-[720px]">
                <ForceGraph2D
                  graphData={forceGraphData}
                  nodeId="id"
                  nodeLabel={(node) => node.label}
                  linkLabel={(link) => formatEdgeLabel(link.label)}
                  width={720}
                  height={520}
                  backgroundColor="#FFF8F1"
                  nodeCanvasObject={renderNode}
                  nodePointerAreaPaint={(node, color, ctx) => {
                    ctx.fillStyle = color;
                    ctx.beginPath();
                    ctx.arc(node.x, node.y, 28, 0, 2 * Math.PI, false);
                    ctx.fill();
                  }}
                  linkCanvasObject={renderLink}
                  linkCanvasObjectMode={() => "before"}
                  linkColor={() => "rgba(58, 46, 61, 0.12)"}
                  linkOpacity={1}
                  linkDirectionalArrowLength={4}
                  linkDirectionalArrowRelPos={1}
                  nodeRelSize={4}
                  cooldownTicks={120}
                  d3AlphaDecay={0.03}
                  d3VelocityDecay={0.35}
                  enableNodeDrag
                  enableZoomInteraction
                  onNodeHover={(node) => setHoveredNodeId(node ? node.id : undefined)}
                  onNodeClick={(node) => setSelectedNodeId(node.id)}
                  onBackgroundClick={() => setSelectedNodeId(undefined)}
                />
              </div>
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
                    {prettyKind(selectedNode.kind)}
                  </div>
                  {selectedNode.aliases?.length ? (
                    <div className="mt-4 text-sm text-aubergine/55">
                      <span className="font-bold text-aubergine/70">Aliases: </span>
                      {selectedNode.aliases.join(", ")}
                    </div>
                  ) : null}
                  {selectedNode.description ? <p className="mt-4 text-sm leading-6 text-aubergine/60">{selectedNode.description}</p> : null}
                  {selectedPaper && (
                    <div className="mt-5 space-y-3 text-sm text-aubergine/60">
                      <p>{selectedPaper.abstract || "This paper currently has local file metadata only."}</p>
                      <Link href="/chat" className="inline-flex rounded-lg bg-terracotta px-4 py-3 font-bold text-surface">
                        Ask about this paper
                      </Link>
                    </div>
                  )}
                  {connectedEdges.length > 0 ? (
                    <div className="mt-5 border-t border-aubergine/8 pt-4 text-sm text-aubergine/55">
                      <div className="mb-2 text-[10px] font-bold uppercase tracking-widest text-aubergine/35">Connected edges</div>
                      <ul className="space-y-2">
                        {connectedEdges.slice(0, 6).map((edge) => (
                          <li key={`${edge.source}-${edge.target}-${edge.label}`} className="rounded-xl bg-cream-dark/25 px-3 py-2">
                            {formatEdgeLabel(edge.label)}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              ) : (
                <div className="mt-5 flex min-h-[180px] flex-col items-center justify-center rounded-2xl bg-cream-dark/20 p-5 text-center">
                  <FileText className="mb-3 h-8 w-8 text-aubergine/20" />
                  <p className="text-sm leading-6 text-aubergine/45">Select a node to inspect its local metadata and connected relations.</p>
                </div>
              )}
            </section>

            <section className="rounded-[28px] bg-surface p-6 shadow-soft">
              <h2 className="text-sm font-bold uppercase tracking-wider text-aubergine/40">Graph contract</h2>
              <p className="mt-4 text-sm leading-6 text-aubergine/55">
                This graph now mirrors the thesis schema more closely: paper, author, organization, conference, topic, task, methodology, dataset, and result nodes plus explicit edges.
              </p>
            </section>
          </aside>
        </div>
      )}
    </div>
  );
}
