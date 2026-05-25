"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

interface MarkdownProps {
  content: string;
  className?: string;
}

/**
 * Markdown renderer with GitHub Flavored Markdown support.
 *
 * Phase 9 (2026-05-25) — added dark-mode pairs everywhere. Previously
 * every text colour was light-mode-only (`text-gray-700`), so the
 * deep-search analysis report rendered as low-contrast text on dark
 * backgrounds (and vice versa when the host container forced a colour).
 * Every text utility now has its `dark:` partner.
 */
export default function Markdown({ content, className = "" }: MarkdownProps) {
  const components: Components = {
    p: ({ children }) => (
      <p className="mb-3 last:mb-0 text-gray-800 dark:text-slate-200 leading-relaxed">
        {children}
      </p>
    ),
    h1: ({ children }) => (
      <h1 className="text-2xl font-bold mb-4 text-gray-900 dark:text-slate-50">
        {children}
      </h1>
    ),
    h2: ({ children }) => (
      <h2 className="text-xl font-bold mb-3 text-gray-900 dark:text-slate-50">
        {children}
      </h2>
    ),
    h3: ({ children }) => (
      <h3 className="text-lg font-semibold mb-2 text-gray-900 dark:text-slate-100">
        {children}
      </h3>
    ),
    h4: ({ children }) => (
      <h4 className="text-base font-semibold mb-2 text-gray-900 dark:text-slate-100">
        {children}
      </h4>
    ),
    ul: ({ children }) => (
      <ul className="list-disc list-outside ml-6 mb-3 space-y-1 text-gray-800 dark:text-slate-200">
        {children}
      </ul>
    ),
    ol: ({ children }) => (
      <ol className="list-decimal list-outside ml-6 mb-3 space-y-1 text-gray-800 dark:text-slate-200">
        {children}
      </ol>
    ),
    li: ({ children }) => <li className="pl-1">{children}</li>,
    strong: ({ children }) => (
      <strong className="font-semibold text-gray-900 dark:text-slate-50">
        {children}
      </strong>
    ),
    em: ({ children }) => (
      <em className="italic text-gray-800 dark:text-slate-200">{children}</em>
    ),
    code: ({ children, className }) => {
      const isInline = !className;
      return isInline ? (
        <code className="px-1.5 py-0.5 bg-gray-100 dark:bg-slate-800 rounded text-sm font-mono text-gray-800 dark:text-slate-200">
          {children}
        </code>
      ) : (
        <code className="block p-3 bg-gray-100 dark:bg-slate-800 rounded text-sm font-mono text-gray-800 dark:text-slate-200 overflow-x-auto">
          {children}
        </code>
      );
    },
    a: ({ href, children }) => (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="text-teal-700 dark:text-teal-300 hover:text-teal-900 dark:hover:text-teal-200 underline underline-offset-2"
      >
        {children}
      </a>
    ),
    blockquote: ({ children }) => (
      <blockquote className="border-l-4 border-gray-300 dark:border-slate-600 pl-4 py-2 mb-3 text-gray-700 dark:text-slate-300 italic">
        {children}
      </blockquote>
    ),
    table: ({ children }) => (
      <div className="overflow-x-auto mb-3">
        <table className="min-w-full text-sm border border-gray-200 dark:border-slate-700">
          {children}
        </table>
      </div>
    ),
    th: ({ children }) => (
      <th className="px-3 py-2 text-left font-semibold bg-gray-50 dark:bg-slate-800 text-gray-900 dark:text-slate-100 border-b border-gray-200 dark:border-slate-700">
        {children}
      </th>
    ),
    td: ({ children }) => (
      <td className="px-3 py-2 text-gray-800 dark:text-slate-200 border-b border-gray-100 dark:border-slate-800">
        {children}
      </td>
    ),
    hr: () => <hr className="my-4 border-gray-200 dark:border-slate-700" />,
  };

  return (
    <div className={className}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
