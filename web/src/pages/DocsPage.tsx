import { useParams, useNavigate, Navigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { docPages, docsTree, type DocNode } from "@/docs/manifest";

// ── Main page ────────────────────────────────────────────────────────────────

export function DocsPage() {
  const { "*": slug } = useParams();
  const navigate = useNavigate();

  // Default to the overview page
  const currentSlug = slug || "overview";

  // If the slug doesn't match any known page, redirect to overview
  if (slug && !docPages[slug]) {
    return <Navigate to="/docs/overview" replace />;
  }

  const page = docPages[currentSlug];

  return (
    // -m-6 counteracts the p-6 on Layout's <main> so we fill edge-to-edge
    <div
      className="-m-6 flex overflow-hidden"
      style={{ height: "calc(100vh - 56px)" }}
    >
      {/* ── Docs sidebar ──────────────────────────────────────────────── */}
      <aside className="w-60 flex-shrink-0 overflow-y-auto border-r border-gray-800 bg-gray-950">
        <div className="px-3 py-4">
          <p className="mb-3 px-2 text-[11px] font-semibold uppercase tracking-widest text-gray-500">
            Documentation
          </p>
          <DocNavTree
            nodes={docsTree}
            currentSlug={currentSlug}
            onNavigate={(id) => navigate(`/docs/${id}`)}
          />
        </div>
      </aside>

      {/* ── Content area ──────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl px-10 py-10">
          {page ? (
            <article className="prose-doc">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={markdownComponents}
              >
                {page.content}
              </ReactMarkdown>
            </article>
          ) : (
            <div className="text-gray-400">Page not found.</div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Docs nav tree ────────────────────────────────────────────────────────────

function DocNavTree({
  nodes,
  currentSlug,
  onNavigate,
  depth = 0,
}: {
  nodes: DocNode[];
  currentSlug: string;
  onNavigate: (id: string) => void;
  depth?: number;
}) {
  return (
    <ul className="space-y-0.5">
      {nodes.map((node) =>
        node.kind === "page" ? (
          <li key={node.id}>
            <button
              onClick={() => onNavigate(node.id)}
              className={cn(
                "w-full rounded-md px-2 py-1.5 text-left text-sm transition-colors",
                depth > 0 && "pl-4",
                currentSlug === node.id
                  ? "bg-blue-600/15 font-medium text-blue-400"
                  : "text-gray-400 hover:bg-gray-800 hover:text-gray-200"
              )}
            >
              {node.title}
            </button>
          </li>
        ) : (
          <DocNavSection
            key={node.id}
            node={node}
            currentSlug={currentSlug}
            onNavigate={onNavigate}
            depth={depth}
          />
        )
      )}
    </ul>
  );
}

function DocNavSection({
  node,
  currentSlug,
  onNavigate,
  depth,
}: {
  node: Extract<DocNode, { kind: "section" }>;
  currentSlug: string;
  onNavigate: (id: string) => void;
  depth: number;
}) {
  // Auto-expand if any descendant is active
  const isAncestorActive = isDescendantActive(node, currentSlug);
  const [open, setOpen] = useState(isAncestorActive);

  return (
    <li>
      <button
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-xs font-semibold uppercase tracking-wider transition-colors",
          depth > 0 && "pl-4",
          "text-gray-500 hover:text-gray-300"
        )}
      >
        <span>{node.title}</span>
        <ChevronIcon open={open} />
      </button>
      {open && (
        <div className={cn("mt-0.5", depth === 0 ? "ml-2" : "ml-4")}>
          <DocNavTree
            nodes={node.children}
            currentSlug={currentSlug}
            onNavigate={onNavigate}
            depth={depth + 1}
          />
        </div>
      )}
    </li>
  );
}

function isDescendantActive(node: DocNode, slug: string): boolean {
  if (node.kind === "page") return node.id === slug;
  return node.children.some((child) => isDescendantActive(child, slug));
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      className={cn(
        "h-3 w-3 flex-shrink-0 transition-transform duration-150",
        open ? "rotate-90" : ""
      )}
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={2.5}
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M8.25 4.5l7.5 7.5-7.5 7.5"
      />
    </svg>
  );
}

// ── Markdown component overrides ─────────────────────────────────────────────
// Maps markdown elements to styled React components matching the design system.

const markdownComponents: React.ComponentProps<
  typeof ReactMarkdown
>["components"] = {
  h1: ({ children }) => (
    <h1 className="mb-4 mt-0 text-3xl font-bold tracking-tight text-gray-50">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="mb-3 mt-10 border-b border-gray-800 pb-2 text-xl font-semibold text-gray-100">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="mb-2 mt-6 text-base font-semibold text-gray-200">
      {children}
    </h3>
  ),
  h4: ({ children }) => (
    <h4 className="mb-2 mt-4 text-sm font-semibold text-gray-300">
      {children}
    </h4>
  ),
  p: ({ children }) => (
    <p className="mb-4 text-sm leading-7 text-gray-300">{children}</p>
  ),
  a: ({ href, children }) => (
    <a
      href={href}
      className="text-blue-400 underline decoration-blue-600/40 underline-offset-2 transition-colors hover:text-blue-300 hover:decoration-blue-400"
      target={href?.startsWith("http") ? "_blank" : undefined}
      rel={href?.startsWith("http") ? "noopener noreferrer" : undefined}
    >
      {children}
    </a>
  ),
  ul: ({ children }) => (
    <ul className="mb-4 space-y-1 pl-5 text-sm text-gray-300 [&>li]:list-disc [&>li]:leading-7">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol className="mb-4 space-y-1 pl-5 text-sm text-gray-300 [&>li]:list-decimal [&>li]:leading-7">
      {children}
    </ol>
  ),
  li: ({ children }) => <li className="leading-7">{children}</li>,
  blockquote: ({ children }) => (
    <blockquote className="my-4 border-l-2 border-blue-500/40 pl-4 text-sm italic text-gray-400">
      {children}
    </blockquote>
  ),
  code: ({ className, children, ...props }) => {
    const isBlock = "node" in props;
    void isBlock; // unused but kept for type narrowing clarity
    // Inline code
    return (
      <code
        className={cn(
          "rounded px-1.5 py-0.5 font-mono text-[0.8125rem] text-blue-400",
          "bg-blue-950/30 ring-1 ring-blue-600/20",
          className
        )}
      >
        {children}
      </code>
    );
  },
  pre: ({ children }) => (
    <pre className="my-4 overflow-x-auto rounded-lg border border-gray-800 bg-gray-900 p-4 font-mono text-[0.8125rem] leading-relaxed text-gray-200">
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div className="my-4 overflow-x-auto rounded-lg border border-gray-800">
      <table className="w-full text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="border-b border-gray-800 bg-gray-900">{children}</thead>
  ),
  tbody: ({ children }) => (
    <tbody className="divide-y divide-gray-800">{children}</tbody>
  ),
  tr: ({ children }) => <tr>{children}</tr>,
  th: ({ children }) => (
    <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wider text-gray-400">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="px-4 py-2.5 text-sm text-gray-300">{children}</td>
  ),
  hr: () => <hr className="my-8 border-gray-800" />,
  strong: ({ children }) => (
    <strong className="font-semibold text-gray-100">{children}</strong>
  ),
  em: ({ children }) => (
    <em className="italic text-gray-300">{children}</em>
  ),
};
