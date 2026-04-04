import { useState, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";
import { docsTree, docPages, firstPageId, type DocNode } from "@/docs/manifest";

// ── Markdown component overrides ────────────────────────────────────────────

const markdownComponents = {
  h1: ({ children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h1 className="text-2xl font-bold text-gray-50 mb-4" {...props}>
      {children}
    </h1>
  ),
  h2: ({ children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h2
      className="text-base font-semibold text-gray-50 border-b border-gray-800 pb-2 mt-8 mb-3"
      {...props}
    >
      {children}
    </h2>
  ),
  h3: ({ children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h3 className="text-sm font-semibold text-gray-50 mt-6 mb-2" {...props}>
      {children}
    </h3>
  ),
  p: ({ children, ...props }: React.HTMLAttributes<HTMLParagraphElement>) => (
    <p className="text-sm text-gray-400 mb-3 leading-relaxed" {...props}>
      {children}
    </p>
  ),
  ul: ({ children, ...props }: React.HTMLAttributes<HTMLUListElement>) => (
    <ul
      className="list-disc list-inside space-y-1 text-sm text-gray-400 mb-3"
      {...props}
    >
      {children}
    </ul>
  ),
  ol: ({ children, ...props }: React.HTMLAttributes<HTMLOListElement>) => (
    <ol
      className="list-decimal list-inside space-y-1 text-sm text-gray-400 mb-3"
      {...props}
    >
      {children}
    </ol>
  ),
  li: ({ children, ...props }: React.HTMLAttributes<HTMLLIElement>) => (
    <li className="text-sm text-gray-400" {...props}>
      {children}
    </li>
  ),
  strong: ({ children, ...props }: React.HTMLAttributes<HTMLElement>) => (
    <strong className="font-semibold text-gray-200" {...props}>
      {children}
    </strong>
  ),
  code: ({
    children,
    className,
    ...props
  }: React.HTMLAttributes<HTMLElement>) => {
    // Inline code vs code blocks
    const isBlock = className?.includes("language-");
    if (isBlock) {
      return (
        <code className={cn("text-xs text-gray-300", className)} {...props}>
          {children}
        </code>
      );
    }
    return (
      <code
        className="rounded-md bg-gray-900 px-1.5 py-0.5 text-xs font-mono text-blue-300"
        {...props}
      >
        {children}
      </code>
    );
  },
  pre: ({ children, ...props }: React.HTMLAttributes<HTMLPreElement>) => (
    <pre
      className="rounded-xl bg-gray-900 border border-gray-800 p-4 text-xs font-mono text-gray-300 overflow-x-auto whitespace-pre-wrap mb-4"
      {...props}
    >
      {children}
    </pre>
  ),
  table: ({ children, ...props }: React.HTMLAttributes<HTMLTableElement>) => (
    <div className="overflow-x-auto mb-4">
      <table className="w-full text-sm" {...props}>
        {children}
      </table>
    </div>
  ),
  thead: ({
    children,
    ...props
  }: React.HTMLAttributes<HTMLTableSectionElement>) => (
    <thead
      className="border-b border-gray-800 text-left text-gray-400"
      {...props}
    >
      {children}
    </thead>
  ),
  th: ({
    children,
    ...props
  }: React.HTMLAttributes<HTMLTableCellElement>) => (
    <th className="pb-2 pr-4 font-medium text-gray-400" {...props}>
      {children}
    </th>
  ),
  td: ({
    children,
    ...props
  }: React.HTMLAttributes<HTMLTableCellElement>) => (
    <td className="py-2 pr-4 text-gray-400" {...props}>
      {children}
    </td>
  ),
  tbody: ({
    children,
    ...props
  }: React.HTMLAttributes<HTMLTableSectionElement>) => (
    <tbody className="divide-y divide-gray-800/50" {...props}>
      {children}
    </tbody>
  ),
  blockquote: ({
    children,
    ...props
  }: React.HTMLAttributes<HTMLQuoteElement>) => (
    <blockquote
      className="border-l-2 border-blue-500/50 pl-4 text-sm text-gray-400 italic mb-3"
      {...props}
    >
      {children}
    </blockquote>
  ),
  hr: (props: React.HTMLAttributes<HTMLHRElement>) => (
    <hr className="border-gray-800 my-6" {...props} />
  ),
  a: ({
    children,
    href,
    ...props
  }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a
      href={href}
      className="text-blue-400 hover:text-blue-300 underline underline-offset-2"
      {...props}
    >
      {children}
    </a>
  ),
};

// ── Sidebar navigation ──────────────────────────────────────────────────────

function NavItem({
  node,
  active,
  onSelect,
  depth = 0,
}: {
  node: DocNode;
  active: string;
  onSelect: (id: string) => void;
  depth?: number;
}) {
  if (node.kind === "page") {
    return (
      <button
        onClick={() => onSelect(node.id)}
        className={cn(
          "w-full text-left rounded-lg px-3 py-1.5 text-sm transition-colors",
          depth > 0 && "ml-3",
          active === node.id
            ? "bg-gray-800 text-gray-50 font-medium"
            : "text-gray-400 hover:bg-gray-900 hover:text-gray-50"
        )}
      >
        {node.title}
      </button>
    );
  }

  return (
    <div className={cn(depth > 0 && "ml-3")}>
      <p
        className={cn(
          "text-xs font-semibold uppercase tracking-wider mb-1 mt-4",
          depth === 0 ? "text-gray-500" : "text-gray-600"
        )}
      >
        {node.title}
      </p>
      <div className="space-y-0.5">
        {node.children.map((child) => (
          <NavItem
            key={child.id}
            node={child}
            active={active}
            onSelect={onSelect}
            depth={depth + 1}
          />
        ))}
      </div>
    </div>
  );
}

// ── Page component ──────────────────────────────────────────────────────────

export function DocsPage() {
  const [active, setActive] = useState(() => firstPageId(docsTree));

  const page = docPages[active];

  const handleSelect = useCallback((id: string) => {
    setActive(id);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  return (
    <div className="flex gap-8 min-h-full">
      {/* Sidebar nav */}
      <aside className="w-56 shrink-0">
        <nav className="sticky top-0 space-y-0.5 max-h-[calc(100vh-4rem)] overflow-y-auto pb-8">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-500">
            Documentation
          </p>
          {docsTree.map((node) => (
            <NavItem
              key={node.id}
              node={node}
              active={active}
              onSelect={handleSelect}
            />
          ))}
        </nav>
      </aside>

      {/* Content */}
      <div className="flex-1 min-w-0 max-w-3xl pb-16">
        {page ? (
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={markdownComponents}
          >
            {page.content}
          </ReactMarkdown>
        ) : (
          <div className="text-sm text-gray-500">Page not found.</div>
        )}
      </div>
    </div>
  );
}
