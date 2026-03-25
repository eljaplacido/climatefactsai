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
 * Handles LLM-generated content with formatting like **bold**, *italic*, lists, etc.
 */
export default function Markdown({ content, className = "" }: MarkdownProps) {
  // Custom components for better styling
  const components: Components = {
    // Paragraphs
    p: ({ children }) => (
      <p className="mb-3 last:mb-0 text-gray-700">{children}</p>
    ),
    // Headings
    h1: ({ children }) => (
      <h1 className="text-2xl font-bold mb-4 text-gray-900">{children}</h1>
    ),
    h2: ({ children }) => (
      <h2 className="text-xl font-bold mb-3 text-gray-900">{children}</h2>
    ),
    h3: ({ children }) => (
      <h3 className="text-lg font-semibold mb-2 text-gray-900">{children}</h3>
    ),
    // Lists
    ul: ({ children }) => (
      <ul className="list-disc list-inside mb-3 space-y-1 text-gray-700">{children}</ul>
    ),
    ol: ({ children }) => (
      <ol className="list-decimal list-inside mb-3 space-y-1 text-gray-700">{children}</ol>
    ),
    li: ({ children }) => <li className="ml-2">{children}</li>,
    // Emphasis
    strong: ({ children }) => (
      <strong className="font-semibold text-gray-900">{children}</strong>
    ),
    em: ({ children }) => <em className="italic">{children}</em>,
    // Code
    code: ({ children, className }) => {
      const isInline = !className;
      return isInline ? (
        <code className="px-1.5 py-0.5 bg-gray-100 rounded text-sm font-mono text-gray-800">
          {children}
        </code>
      ) : (
        <code className="block p-3 bg-gray-100 rounded text-sm font-mono text-gray-800 overflow-x-auto">
          {children}
        </code>
      );
    },
    // Links
    a: ({ href, children }) => (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="text-clilens-primary hover:text-clilens-teal-600 underline"
      >
        {children}
      </a>
    ),
    // Blockquotes
    blockquote: ({ children }) => (
      <blockquote className="border-l-4 border-gray-300 pl-4 py-2 mb-3 text-gray-600 italic">
        {children}
      </blockquote>
    ),
  };

  return (
    <div className={className}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
