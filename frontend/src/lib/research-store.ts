"use client";

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export type PaperStatus = "indexed" | "needs_review";

export type PaperCategory =
  | "ML/AI"
  | "IoT/Hardware"
  | "Networks"
  | "Theory"
  | "Surveys"
  | "Uncategorized";

export type ViewMode = "grid" | "list";

export type Paper = {
  id: string;
  title: string;
  fileName: string;
  fileType: string;
  fileSize: number;
  categories: PaperCategory[];
  status: PaperStatus;
  authors: string[];
  year?: string;
  abstract?: string;
  addedAt: string;
};

export type NewPaperInput = {
  fileName: string;
  fileType: string;
  fileSize: number;
  abstract?: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
  sourcePaperIds: string[];
};

export type ChatSession = {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messages: ChatMessage[];
};

export type GraphNode = {
  id: string;
  label: string;
  kind:
    | "paper"
    | "category"
    | "author"
    | "year"
    | "organization"
    | "conference"
    | "topic"
    | "task"
    | "methodology"
    | "dataset"
    | "result";
  aliases?: string[];
  description?: string;
  original_id?: string | null;
};

export type GraphLink = {
  source: string;
  target: string;
  label: string;
};

type ResearchState = {
  papers: Paper[];
  sessions: ChatSession[];
  activeSessionId?: string;
  addPapers: (inputs: NewPaperInput[]) => Paper[];
  removePaper: (paperId: string) => void;
  updatePaper: (paperId: string, updates: Partial<Pick<Paper, "title" | "categories" | "authors" | "year" | "abstract">>) => void;
  createSession: (title?: string) => string;
  setActiveSession: (sessionId: string) => void;
  deleteSession: (sessionId: string) => void;
  sendMessage: (message: string) => void;
  clearWorkspace: () => void;
};

const categoryKeywords: Record<PaperCategory, string[]> = {
  "ML/AI": ["bert", "transformer", "llm", "learning", "neural", "model", "ai", "machine", "vision"],
  "IoT/Hardware": ["iot", "sensor", "edge", "device", "hardware", "embedded", "mcu", "raspberry"],
  Networks: ["network", "wireless", "routing", "protocol", "latency", "throughput", "5g"],
  Theory: ["proof", "theorem", "optimization", "graph", "complexity", "algorithm"],
  Surveys: ["survey", "review", "taxonomy", "overview"],
  Uncategorized: [],
};

export const paperCategories = Object.keys(categoryKeywords) as PaperCategory[];

export function formatFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function makeId(prefix: string) {
  const random =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2);
  return `${prefix}_${random}`;
}

function titleFromFileName(fileName: string) {
  return fileName
    .replace(/\.[^.]+$/, "")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function inferYear(text: string) {
  return text.match(/\b(19|20)\d{2}\b/)?.[0];
}

function inferCategory(text: string): PaperCategory[] {
  const lower = text.toLowerCase();
  const matches = paperCategories.filter((category) =>
    categoryKeywords[category].some((keyword) => lower.includes(keyword))
  );
  return matches.length > 0 ? matches : ["Uncategorized"];
}

function inferAuthors(text: string) {
  const byMatch = text.match(/\bby\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?(?:,\s*[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)*)/);
  if (!byMatch?.[1]) return [];
  return byMatch[1].split(",").map((author) => author.trim()).filter(Boolean).slice(0, 4);
}

function makePaper(input: NewPaperInput): Paper {
  const title = titleFromFileName(input.fileName);
  const searchable = `${title} ${input.abstract ?? ""}`;

  return {
    id: makeId("paper"),
    title,
    fileName: input.fileName,
    fileType: input.fileType || "application/octet-stream",
    fileSize: input.fileSize,
    categories: inferCategory(searchable),
    status: input.abstract || input.fileType === "application/pdf" ? "indexed" : "needs_review",
    authors: inferAuthors(searchable),
    year: inferYear(searchable),
    abstract: input.abstract,
    addedAt: new Date().toISOString(),
  };
}

function findRelevantPapers(question: string, papers: Paper[]) {
  const terms = question
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((term) => term.length > 2);

  return papers
    .map((paper) => {
      const haystack = `${paper.title} ${paper.categories.join(" ")} ${paper.year ?? ""} ${paper.authors.join(" ")} ${paper.abstract ?? ""}`.toLowerCase();
      const score = terms.reduce((total, term) => total + (haystack.includes(term) ? 1 : 0), 0);
      return { paper, score };
    })
    .filter(({ score }) => score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 4)
    .map(({ paper }) => paper);
}

function makeAssistantAnswer(question: string, papers: Paper[]) {
  if (papers.length === 0) {
    return {
      content:
        "I do not have any uploaded papers yet. Upload PDFs or text notes first, then I can search the local library and cite the matching sources.",
      sourcePaperIds: [],
    };
  }

  const relevant = findRelevantPapers(question, papers);
  const sources = relevant.length > 0 ? relevant : papers.slice(0, 3);
  const sourceLines = sources
    .map((paper, index) => {
      const meta = [paper.authors.join(", "), paper.year, paper.categories.join(", ")].filter(Boolean).join(" | ");
      return `${index + 1}. ${paper.title}${meta ? ` (${meta})` : ""}`;
    })
    .join("\n");

  const focus =
    relevant.length > 0
      ? "I found matching items in your local library and used those as sources."
      : "I could not find exact keyword matches, so I used the closest papers currently in your local library.";

  return {
    content: `${focus}\n\nSources considered:\n${sourceLines}`,
    sourcePaperIds: sources.map((paper) => paper.id),
  };
}

function makeInitialSession(): ChatSession {
  const now = new Date().toISOString();
  return {
    id: makeId("session"),
    title: "Research chat",
    createdAt: now,
    updatedAt: now,
    messages: [],
  };
}

export function buildKnowledgeGraph(papers: Paper[]) {
  const nodes = new Map<string, GraphNode>();
  const links: GraphLink[] = [];

  papers.forEach((paper) => {
    nodes.set(paper.id, { id: paper.id, label: paper.title, kind: "paper" });

    paper.categories.forEach((cat) => {
      const categoryId = `category:${cat}`;
      nodes.set(categoryId, { id: categoryId, label: cat, kind: "category" });
      links.push({ source: paper.id, target: categoryId, label: "IN_CATEGORY" });
    });

    if (paper.year) {
      const yearId = `year:${paper.year}`;
      nodes.set(yearId, { id: yearId, label: paper.year, kind: "year" });
      links.push({ source: paper.id, target: yearId, label: "PUBLISHED_IN" });
    }

    paper.authors.forEach((author) => {
      const authorId = `author:${author.toLowerCase()}`;
      nodes.set(authorId, { id: authorId, label: author, kind: "author" });
      links.push({ source: paper.id, target: authorId, label: "AUTHORED_BY" });
    });
  });

  return { nodes: Array.from(nodes.values()), links };
}

export const useResearchStore = create<ResearchState>()(
  persist(
    (set, get) => ({
      papers: [],
      sessions: [],
      activeSessionId: undefined,
      addPapers: (inputs) => {
        const created = inputs.map(makePaper);
        set((state) => ({ papers: [...created, ...state.papers] }));
        return created;
      },
      removePaper: (paperId) => {
        set((state) => ({ papers: state.papers.filter((paper) => paper.id !== paperId) }));
      },
      updatePaper: (paperId, updates) => {
        set((state) => ({
          papers: state.papers.map((paper) => (paper.id === paperId ? { ...paper, ...updates } : paper)),
        }));
      },
      createSession: (title) => {
        const session = makeInitialSession();
        session.title = title ?? session.title;
        set((state) => ({
          sessions: [session, ...state.sessions],
          activeSessionId: session.id,
        }));
        return session.id;
      },
      setActiveSession: (sessionId) => set({ activeSessionId: sessionId }),
      deleteSession: (sessionId) => {
        set((state) => {
          const sessions = state.sessions.filter((session) => session.id !== sessionId);
          return {
            sessions,
            activeSessionId: state.activeSessionId === sessionId ? sessions[0]?.id : state.activeSessionId,
          };
        });
      },
      sendMessage: (message) => {
        const trimmed = message.trim();
        if (!trimmed) return;

        const state = get();
        let activeSessionId = state.activeSessionId;
        let sessions = state.sessions;

        if (!activeSessionId || !sessions.some((session) => session.id === activeSessionId)) {
          const session = makeInitialSession();
          activeSessionId = session.id;
          sessions = [session, ...sessions];
        }

        const now = new Date().toISOString();
        const answer = makeAssistantAnswer(trimmed, state.papers);
        const userMessage: ChatMessage = {
          id: makeId("message"),
          role: "user",
          content: trimmed,
          createdAt: now,
          sourcePaperIds: [],
        };
        const assistantMessage: ChatMessage = {
          id: makeId("message"),
          role: "assistant",
          content: answer.content,
          createdAt: new Date().toISOString(),
          sourcePaperIds: answer.sourcePaperIds,
        };

        set({
          activeSessionId,
          sessions: sessions.map((session) =>
            session.id === activeSessionId
              ? {
                  ...session,
                  title: session.messages.length === 0 ? trimmed.slice(0, 52) : session.title,
                  updatedAt: now,
                  messages: [...session.messages, userMessage, assistantMessage],
                }
              : session
          ),
        });
      },
      clearWorkspace: () => set({ papers: [], sessions: [], activeSessionId: undefined }),
    }),
    {
      name: "mliot-local-workspace",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        papers: state.papers,
        sessions: state.sessions,
        activeSessionId: state.activeSessionId,
      }),
    }
  )
);
