"use client";

import { useState } from "react";
import { ExternalLink, FileText, Hash } from "lucide-react";
import type { Citation as CitationType } from "@/lib/types";

interface CitationProps {
  citation: CitationType;
  index: number;
  onHover?: (citation: CitationType | null) => void;
  onClick?: () => void;
}

export default function Citation({
  citation,
  index,
  onHover,
  onClick,
}: CitationProps) {
  const [showTooltip, setShowTooltip] = useState(false);

  const handleMouseEnter = () => {
    setShowTooltip(true);
    onHover?.(citation);
  };

  const handleMouseLeave = () => {
    setShowTooltip(false);
    onHover?.(null);
  };

  const getSourceIcon = () => {
    if (
      citation.source?.includes("10-K") ||
      citation.source?.includes("10-Q")
    ) {
      return <FileText className="w-3 h-3" />;
    }
    return <Hash className="w-3 h-3" />;
  };

  const truncateSource = (source: string | undefined, maxLength = 20) => {
    if (!source) return "Source";
    if (source.length <= maxLength) return source;
    return source.slice(0, maxLength) + "...";
  };

  return (
    <div className="relative inline-block">
      <button
        className="citation-chip group"
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onClick={onClick}
      >
        <span className="flex items-center gap-1">
          {getSourceIcon()}
          <span className="font-semibold">[{index}]</span>
          <span className="hidden sm:inline">
            {truncateSource(citation.source)}
          </span>
        </span>

        {/* Provenance link indicator */}
        {citation.provenance_hash && (
          <ExternalLink className="w-3 h-3 ml-1 opacity-0 group-hover:opacity-100 transition-opacity" />
        )}
      </button>

      {/* Tooltip */}
      {showTooltip && (
        <div
          className="absolute z-50 bottom-full left-0 mb-2 w-80 p-3 
                     bg-white dark:bg-slate-800 rounded-lg shadow-lg border 
                     border-slate-200 dark:border-slate-600"
        >
          {/* Source header */}
          <div className="flex items-start justify-between gap-2 mb-2">
            <div className="flex-1">
              <p className="font-medium text-slate-900 dark:text-white text-sm">
                {citation.source}
              </p>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Document: {citation.document_id}
              </p>
            </div>
            {citation.score !== undefined && (
              <span className="px-2 py-0.5 bg-vesper-100 text-vesper-700 text-xs rounded-full">
                {(citation.score * 100).toFixed(0)}% match
              </span>
            )}
          </div>

          {/* Citation text */}
          <blockquote className="text-sm text-slate-600 dark:text-slate-300 italic border-l-2 border-vesper-400 pl-2 line-clamp-4">
            "{citation.text}"
          </blockquote>

          {/* Metadata */}
          <div className="flex items-center gap-3 mt-2 text-xs text-slate-500">
            {citation.page && <span>Page {citation.page}</span>}
            {citation.span_start !== undefined &&
              citation.span_end !== undefined && (
                <span>
                  Chars {citation.span_start}-{citation.span_end}
                </span>
              )}
            {citation.provenance_hash && (
              <a
                href={`#provenance/${citation.provenance_hash}`}
                className="text-vesper-600 hover:underline flex items-center gap-1"
                onClick={(e) => e.stopPropagation()}
              >
                <Hash className="w-3 h-3" />
                Verify
              </a>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Component to display a list of all citations with full details
 */
export function CitationList({ citations }: { citations: CitationType[] }) {
  return (
    <div className="space-y-3">
      <h3 className="font-semibold text-slate-900 dark:text-white">
        References
      </h3>

      {citations.map((citation, index) => (
        <div
          key={citation.id || index}
          className="p-4 bg-slate-50 dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700"
        >
          <div className="flex items-start gap-3">
            <span
              className="flex-shrink-0 w-6 h-6 bg-vesper-100 text-vesper-700 rounded-full 
                           flex items-center justify-center text-sm font-medium"
            >
              {index + 1}
            </span>

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <h4 className="font-medium text-slate-900 dark:text-white truncate">
                  {citation.source}
                </h4>
                {citation.score !== undefined && (
                  <span className="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded-full flex-shrink-0">
                    {(citation.score * 100).toFixed(0)}%
                  </span>
                )}
              </div>

              <p className="text-sm text-slate-600 dark:text-slate-400 mb-2">
                {citation.document_id}
                {citation.page && ` • Page ${citation.page}`}
              </p>

              <blockquote
                className="text-sm text-slate-700 dark:text-slate-300 
                                    bg-white dark:bg-slate-700 p-3 rounded border-l-4 border-vesper-400"
              >
                {citation.text}
              </blockquote>

              {citation.provenance_hash && (
                <a
                  href={`#provenance/${citation.provenance_hash}`}
                  className="inline-flex items-center gap-1 mt-2 text-xs text-vesper-600 hover:underline"
                >
                  <Hash className="w-3 h-3" />
                  {citation.provenance_hash.slice(0, 16)}...
                </a>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
