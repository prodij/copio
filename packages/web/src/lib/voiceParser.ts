/*
  Honest-voice renderer.

  The agent emits prose with two tokens that the renderer recognizes:

    1. Citation superscripts: ¹ ² ³ ⁴ ⁵ ⁶ ⁷ ⁸ ⁹  (or [1], [2]...)
       - Rendered as <sup class="cite"> with hover popover.
    2. Inference markers: sentences starting with "I infer", "I think",
       "I'm 70% on this", "I might be wrong", "my read is", "this is a guess"
       - Rendered as <em class="inferred"> in muted italic.

  Per DESIGN.md: "I can see X" claims = Inter regular + --text-primary.
  "I infer Y" claims = Inter italic + --text-muted. Visual differentiation
  via color shift + italic style, NOT font family.
*/

export type Segment =
  | { kind: "text"; value: string }
  | { kind: "inferred"; value: string }
  | { kind: "cite"; index: number }
  | { kind: "linebreak" };

const SUPERSCRIPT_MAP: Record<string, number> = {
  "¹": 1, "²": 2, "³": 3,
  "⁴": 4, "⁵": 5, "⁶": 6,
  "⁷": 7, "⁸": 8, "⁹": 9,
};

const SUPERSCRIPT_RE = /[¹²³⁴-⁹]|\[(\d+)\]/g;

const INFERENCE_PATTERNS = [
  /^I infer\b/i,
  /^I think\b/i,
  /^My read is\b/i,
  /^I might be wrong\b/i,
  /^This is a guess\b/i,
  /^I'm \d{1,3}% on this\b/i,
  /^I am \d{1,3}% on this\b/i,
];

export function isInferenceSentence(sentence: string): boolean {
  const trimmed = sentence.trimStart();
  return INFERENCE_PATTERNS.some((re) => re.test(trimmed));
}

function splitSentences(paragraph: string): string[] {
  // Conservative split — preserves trailing whitespace + punctuation.
  // We do NOT use `—` (em dashes are forbidden by voice rules) so this is safe.
  const out: string[] = [];
  let current = "";
  for (let i = 0; i < paragraph.length; i++) {
    current += paragraph[i];
    const ch = paragraph[i];
    const next = paragraph[i + 1];
    if ((ch === "." || ch === "?" || ch === "!") && (next === " " || next === undefined)) {
      out.push(current);
      current = "";
    }
  }
  if (current.trim().length > 0) out.push(current);
  return out;
}

function parseSegmentsForLine(line: string): Segment[] {
  const segments: Segment[] = [];
  const sentences = splitSentences(line);
  for (const sentence of sentences) {
    const treatAsInferred = isInferenceSentence(sentence);
    let cursor = 0;
    SUPERSCRIPT_RE.lastIndex = 0;
    let match: RegExpExecArray | null;
    while ((match = SUPERSCRIPT_RE.exec(sentence)) !== null) {
      const before = sentence.slice(cursor, match.index);
      if (before) {
        segments.push({
          kind: treatAsInferred ? "inferred" : "text",
          value: before,
        });
      }
      const indexFromBracket = match[1];
      const indexFromSuper = SUPERSCRIPT_MAP[match[0]];
      const idx = indexFromBracket
        ? parseInt(indexFromBracket, 10)
        : indexFromSuper ?? 0;
      if (idx > 0) {
        segments.push({ kind: "cite", index: idx });
      }
      cursor = match.index + match[0].length;
    }
    const tail = sentence.slice(cursor);
    if (tail) {
      segments.push({
        kind: treatAsInferred ? "inferred" : "text",
        value: tail,
      });
    }
  }
  return segments;
}

export function parseVoice(text: string): Segment[][] {
  // Returns paragraphs; each paragraph is a list of segments. Lines are
  // separated by blank lines (\n\n) per Markdown convention.
  const paragraphs = text.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean);
  return paragraphs.map(parseSegmentsForLine);
}
