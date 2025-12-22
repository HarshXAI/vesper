"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { User, Bot, AlertCircle } from "lucide-react";
import type { Message, Citation as CitationType } from "@/lib/types";
import Citation from "./Citation";

interface ChatMessageProps {
  message: Message;
  onCitationClick?: (citation: CitationType) => void;
}

export default function ChatMessage({
  message,
  onCitationClick,
}: ChatMessageProps) {
  const isUser = message.role === "user";
  const [hoveredCitation, setHoveredCitation] = useState<CitationType | null>(
    null
  );

  return (
    <div className={`flex gap-4 ${isUser ? "flex-row-reverse" : "flex-row"}`}>
      {/* Avatar */}
      <div
        className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center
          ${
            isUser
              ? "bg-vesper-100 text-vesper-600"
              : "bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300"
          }`}
      >
        {isUser ? <User className="w-5 h-5" /> : <Bot className="w-5 h-5" />}
      </div>

      {/* Message content */}
      <div
        className={`flex-1 max-w-3xl ${isUser ? "text-right" : "text-left"}`}
      >
        <div
          className={`inline-block px-4 py-3 rounded-2xl ${
            isUser
              ? "bg-vesper-600 text-white rounded-br-md"
              : "bg-white dark:bg-slate-800 text-slate-900 dark:text-white rounded-bl-md shadow-sm border border-slate-200 dark:border-slate-700"
          }`}
        >
          {/* Error state */}
          {message.error && (
            <div className="flex items-center gap-2 text-red-500 dark:text-red-400 mb-2">
              <AlertCircle className="w-4 h-4" />
              <span className="text-sm">{message.error}</span>
            </div>
          )}

          {/* Message text */}
          <div
            className={`markdown-content ${
              isUser ? "" : "prose dark:prose-invert max-w-none"
            }`}
          >
            {isUser ? (
              <p className="whitespace-pre-wrap">{message.content}</p>
            ) : (
              <>
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    // Inject citation markers into text
                    p: ({ children }) => <p>{children}</p>,
                  }}
                >
                  {message.content}
                </ReactMarkdown>

                {/* Streaming cursor */}
                {message.isStreaming && <span className="streaming-cursor" />}
              </>
            )}
          </div>

          {/* Citations */}
          {!isUser && message.citations && message.citations.length > 0 && (
            <div className="mt-4 pt-3 border-t border-slate-200 dark:border-slate-600">
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-2">
                Sources ({message.citations.length})
              </p>
              <div className="flex flex-wrap gap-2">
                {message.citations.map((citation, index) => (
                  <Citation
                    key={citation.id || index}
                    citation={citation}
                    index={index + 1}
                    onHover={setHoveredCitation}
                    onClick={() => onCitationClick?.(citation)}
                  />
                ))}
              </div>

              {/* Citation preview popover */}
              {hoveredCitation && (
                <div className="mt-3 p-3 bg-slate-50 dark:bg-slate-700 rounded-lg text-sm">
                  <p className="font-medium text-slate-700 dark:text-slate-300 mb-1">
                    {hoveredCitation.source}
                  </p>
                  <p className="text-slate-600 dark:text-slate-400 text-xs italic line-clamp-3">
                    "{hoveredCitation.text}"
                  </p>
                  {hoveredCitation.page && (
                    <p className="text-xs text-slate-500 mt-1">
                      Page {hoveredCitation.page}
                    </p>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Timestamp */}
        <p className="text-xs text-slate-400 mt-1 px-1">
          {new Date(message.timestamp).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </p>
      </div>
    </div>
  );
}
