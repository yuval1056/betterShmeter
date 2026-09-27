import { Children } from "react";
import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import "katex/dist/katex.min.css";

/**
 * Models often write math as \( ... \) and \[ ... \], which remark-math
 * doesn't understand (it wants $ ... $ and $$ ... $$). Rewrite them, leaving
 * fenced and inline code untouched.
 */
function normalizeMath(text: string): string {
  return text
    .split(/(```[\s\S]*?```|`[^`\n]*`)/g)
    .map((part, i) =>
      i % 2 === 1
        ? part
        : part
            .replace(/\\\[([\s\S]+?)\\\]/g, (_, m: string) => `\n$$\n${m.trim()}\n$$\n`)
            .replace(/\\\(([\s\S]+?)\\\)/g, (_, m: string) => `$${m.trim()}$`),
    )
    .join("");
}

export default function Markdown({ text }: { text: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" />,
          // The backend writes **confirm** when it asks the user to approve an
          // action; that word (and only that word) gets the highlight.
          strong: ({ node: _node, children, ...props }) =>
            /^confirm$/i.test(Children.toArray(children).join("")) ? (
              <mark className="confirm-highlight">{children}</mark>
            ) : (
              <strong {...props}>{children}</strong>
            ),
        }}
      >
        {normalizeMath(text)}
      </ReactMarkdown>
    </div>
  );
}
