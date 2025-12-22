"use client";

import { useState, useRef, useEffect } from "react";
import { useSession, signIn, signOut } from "next-auth/react";
import {
  Send,
  Copy,
  Check,
  Loader2,
  LogOut,
  FileText,
  User,
} from "lucide-react";
import { useChatStore } from "@/lib/store";
import { createSSEStream, type StreamEvent } from "@/lib/sse";
import { Citation as CitationType } from "@/lib/types";
import ChatMessage from "@/components/ChatMessage";
import Citation from "@/components/Citation";
import TraceView from "@/components/TraceView";

export default function HomePage() {
  const { data: session, status } = useSession();
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showTrace, setShowTrace] = useState(false);
  const [currentTraceId, setCurrentTraceId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const { messages, addMessage, updateLastMessage, clearMessages } =
    useChatStore();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput("");
    setIsLoading(true);

    // Add user message
    addMessage({
      role: "user",
      content: userMessage,
      timestamp: new Date(),
    });

    // Add placeholder for assistant response
    addMessage({
      role: "assistant",
      content: "",
      timestamp: new Date(),
      isStreaming: true,
      citations: [],
    });

    try {
      abortControllerRef.current = new AbortController();

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";
      const token = (session as any)?.accessToken || "";

      await createSSEStream(
        `${apiUrl}/v1/ask`,
        {
          query: userMessage,
          tenant_id: (session?.user as any)?.tenantId || "default",
        },
        {
          token,
          signal: abortControllerRef.current.signal,
          onEvent: (event: StreamEvent) => {
            switch (event.type) {
              case "token":
                updateLastMessage((prev) => ({
                  ...prev,
                  content: prev.content + (event.data?.token || ""),
                }));
                break;
              case "citation":
                updateLastMessage((prev) => ({
                  ...prev,
                  citations: [
                    ...(prev.citations || []),
                    ...(Array.isArray(event.data) ? event.data : [event.data]),
                  ],
                }));
                break;
              case "metadata":
                if (event.data?.trace_id) {
                  setCurrentTraceId(event.data.trace_id);
                }
                break;
              case "done":
                updateLastMessage((prev) => ({
                  ...prev,
                  isStreaming: false,
                }));
                break;
              case "error":
                updateLastMessage((prev) => ({
                  ...prev,
                  content:
                    prev.content ||
                    "An error occurred while processing your request.",
                  isStreaming: false,
                  error: event.data?.message,
                }));
                break;
            }
          },
          onError: (error) => {
            console.error("SSE Error:", error);
            updateLastMessage((prev) => ({
              ...prev,
              content: prev.content || "Connection error. Please try again.",
              isStreaming: false,
              error: error.message,
            }));
          },
        }
      );
    } catch (error) {
      console.error("Request error:", error);
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  };

  const handleStop = () => {
    abortControllerRef.current?.abort();
    setIsLoading(false);
    updateLastMessage((prev) => ({
      ...prev,
      isStreaming: false,
    }));
  };

  const copyWithCitations = () => {
    const lastAssistantMessage = messages
      .filter((m) => m.role === "assistant")
      .pop();
    if (!lastAssistantMessage) return;

    let markdown = lastAssistantMessage.content;

    if (lastAssistantMessage.citations?.length) {
      markdown += "\n\n---\n**References:**\n";
      lastAssistantMessage.citations.forEach((citation, index) => {
        markdown += `\n[${index + 1}] ${citation.source} (${
          citation.document_id
        })\n`;
        markdown += `> "${citation.text}"\n`;
      });
    }

    navigator.clipboard.writeText(markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Authentication check
  if (status === "loading") {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-vesper-600" />
      </div>
    );
  }

  if (!session) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-6">
        <div className="text-center">
          <h1 className="text-4xl font-bold text-slate-900 dark:text-white mb-2">
            VESPER
          </h1>
          <p className="text-slate-600 dark:text-slate-400">
            AI-powered financial document analysis
          </p>
        </div>
        <button
          onClick={() => signIn("cognito")}
          className="flex items-center gap-2 px-6 py-3 bg-vesper-600 text-white rounded-lg 
                     hover:bg-vesper-700 transition-colors font-medium"
        >
          <User className="w-5 h-5" />
          Sign in with Cognito
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-slate-50 dark:bg-slate-900">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800">
        <div className="flex items-center gap-3">
          <FileText className="w-8 h-8 text-vesper-600" />
          <div>
            <h1 className="text-xl font-semibold text-slate-900 dark:text-white">
              VESPER Analyst
            </h1>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Financial Document Q&A
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {currentTraceId && (
            <button
              onClick={() => setShowTrace(!showTrace)}
              className="text-sm text-vesper-600 hover:text-vesper-700 font-medium"
            >
              {showTrace ? "Hide Trace" : "View Trace"}
            </button>
          )}

          <div className="flex items-center gap-2">
            <span className="text-sm text-slate-600 dark:text-slate-400">
              {session.user?.email}
            </span>
            <button
              onClick={() => signOut()}
              className="p-2 text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
              title="Sign out"
            >
              <LogOut className="w-5 h-5" />
            </button>
          </div>
        </div>
      </header>

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Chat area */}
        <main
          className={`flex-1 flex flex-col ${showTrace ? "w-2/3" : "w-full"}`}
        >
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-center">
                <FileText className="w-16 h-16 text-slate-300 dark:text-slate-600 mb-4" />
                <h2 className="text-xl font-medium text-slate-700 dark:text-slate-300 mb-2">
                  Ask about financial documents
                </h2>
                <p className="text-slate-500 dark:text-slate-400 max-w-md">
                  Get insights from SEC filings, earnings reports, and financial
                  statements with verifiable citations.
                </p>
              </div>
            ) : (
              messages.map((message, index) => (
                <ChatMessage
                  key={index}
                  message={message}
                  onCitationClick={(citation) =>
                    console.log("Citation clicked:", citation)
                  }
                />
              ))
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input area */}
          <div className="border-t border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4">
            <form
              onSubmit={handleSubmit}
              className="flex items-end gap-4 max-w-4xl mx-auto"
            >
              <div className="flex-1 relative">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSubmit(e);
                    }
                  }}
                  placeholder="Ask a question about your financial documents..."
                  className="w-full px-4 py-3 border border-slate-300 dark:border-slate-600 rounded-lg
                           bg-white dark:bg-slate-700 text-slate-900 dark:text-white
                           placeholder:text-slate-400 focus:outline-none focus:ring-2 
                           focus:ring-vesper-500 focus:border-transparent resize-none"
                  rows={1}
                  disabled={isLoading}
                />
              </div>

              <div className="flex items-center gap-2">
                {messages.length > 0 && (
                  <button
                    type="button"
                    onClick={copyWithCitations}
                    className="p-3 text-slate-500 hover:text-slate-700 dark:hover:text-slate-300
                             border border-slate-300 dark:border-slate-600 rounded-lg"
                    title="Copy with citations"
                  >
                    {copied ? (
                      <Check className="w-5 h-5 text-green-500" />
                    ) : (
                      <Copy className="w-5 h-5" />
                    )}
                  </button>
                )}

                {isLoading ? (
                  <button
                    type="button"
                    onClick={handleStop}
                    className="p-3 bg-red-500 text-white rounded-lg hover:bg-red-600"
                    title="Stop generation"
                  >
                    <Loader2 className="w-5 h-5 animate-spin" />
                  </button>
                ) : (
                  <button
                    type="submit"
                    disabled={!input.trim()}
                    className="p-3 bg-vesper-600 text-white rounded-lg hover:bg-vesper-700
                             disabled:opacity-50 disabled:cursor-not-allowed"
                    title="Send message"
                  >
                    <Send className="w-5 h-5" />
                  </button>
                )}
              </div>
            </form>
          </div>
        </main>

        {/* Trace panel */}
        {showTrace && currentTraceId && (
          <aside className="w-1/3 border-l border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 overflow-y-auto">
            <TraceView
              traceId={currentTraceId}
              onClose={() => setShowTrace(false)}
            />
          </aside>
        )}
      </div>
    </div>
  );
}
