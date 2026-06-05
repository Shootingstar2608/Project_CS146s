"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Renders assistant answers as GitHub-flavored markdown. Raw HTML is not
 * rendered (no rehype-raw), so model output can't inject markup.
 */
export default function Markdown({ children }: { children: string }) {
  return (
    <div className="prose-chat">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  );
}
