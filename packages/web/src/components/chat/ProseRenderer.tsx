"use client";

import { Fragment } from "react";
import type { Citation } from "@/lib/api";
import { parseVoice, type Segment } from "@/lib/voiceParser";
import { CitationPill } from "./CitationPill";

type Props = { text: string; citations: Citation[]; streaming?: boolean };

export function ProseRenderer({ text, citations, streaming = false }: Props) {
  const paragraphs = parseVoice(text);
  return (
    <div className="prose-body">
      {paragraphs.map((segments, pIdx) => (
        <p key={pIdx}>
          {segments.map((seg, sIdx) => renderSegment(seg, sIdx, citations))}
          {streaming && pIdx === paragraphs.length - 1 && (
            <span className="streaming-caret" aria-hidden />
          )}
        </p>
      ))}
      {paragraphs.length === 0 && streaming && (
        <p>
          <span className="streaming-caret" aria-hidden />
        </p>
      )}
    </div>
  );
}

function renderSegment(seg: Segment, key: number, citations: Citation[]) {
  if (seg.kind === "linebreak") {
    return <br key={key} />;
  }
  if (seg.kind === "cite") {
    const cite = citations[seg.index - 1];
    if (cite == null) {
      return (
        <sup key={key} className="cite">
          {seg.index}
        </sup>
      );
    }
    return <CitationPill key={key} citation={cite} index={seg.index} />;
  }
  if (seg.kind === "inferred") {
    return (
      <em key={key} className="inferred">
        {seg.value}
      </em>
    );
  }
  return <Fragment key={key}>{seg.value}</Fragment>;
}
