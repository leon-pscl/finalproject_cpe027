import type { TranscriptSegment, TranscriptNote } from './api';

export interface NoteReference {
  number: number;
  segmentId: string;
  text: string;
  start: number;
}

function escapeYaml(value: string): string {
  return JSON.stringify(value);
}

export function notesToMarkdown(
  notes: TranscriptNote[],
  fileName: string,
  transcript: TranscriptSegment[] = [],
): string {
  const now = new Date().toISOString();
  const segmentMap = new Map(transcript.map((segment) => [segment.id, segment]));
  const referenceNumbers = new Map<string, number>();
  notes.forEach((note) => {
    note.supporting_segment_ids.forEach((id) => {
      if (!referenceNumbers.has(id)) referenceNumbers.set(id, referenceNumbers.size + 1);
    });
  });

  const bodyLines: string[] = [];
  let currentSection = '';
  notes.forEach((note) => {
    if (note.section !== currentSection) {
      currentSection = note.section;
      const heading = note.section.charAt(0).toUpperCase() + note.section.slice(1).toLowerCase();
      const sectionNumber = bodyLines.filter((line) => /^## \d+\./.test(line)).length + 1;
      if (bodyLines.length) bodyLines.push('', '---', '');
      bodyLines.push(`## ${sectionNumber}. ${heading}`, '');
    }
    const refs = note.supporting_segment_ids
      .map((id) => referenceNumbers.get(id))
      .filter((value): value is number => value !== undefined)
      .map((number) => `[${number}]`)
      .join('');
    bodyLines.push(`- **${note.title}:** ${note.description}${refs ? ` ${refs}` : ''}`);
  });

  const sources = [...referenceNumbers.entries()]
    .sort((a, b) => a[1] - b[1])
    .map(([id, number]) => {
      const segment = segmentMap.get(id);
      return `- [${number}] \`${id}\`${segment ? ` ${segment.text}` : ''}`;
    });

  const extraExample = [
    '---',
    '',
    '## Worked Example (Extra, not from the lecture)',
    '',
    '- **BANANA:** There are 6 letters total: 3 A\'s, 2 N\'s, and 1 B.',
    '  If all letters were distinct, there would be \(6! = 720\) arrangements.',
    '  Because the repeated A\'s can be swapped in \(3!\) ways and the repeated N\'s in \(2!\) ways without changing the word,',
    '  divide by those overcounts:',
    '',
    '  \[',
    '  \\frac{6!}{3!\,2!} = \\frac{720}{6 \\cdot 2} = 60',
    '  \]',
    '',
    '  So there are **60** distinct arrangements.',
    '',
    '  Relevant lecture idea: repeated letters cause overcounting, so divide by the factorial of each repeated count.',
  ].join('\n');

  return `---
title: ${escapeYaml(fileName)}
created: ${now}
updated: ${now}
tags: [lecture, transcript, notes]
type: lecture-notes
status: draft
---

# ${fileName}

A generated study summary of the lecture. Edit anywhere; changes are saved locally.

${bodyLines.join('\n')}

${extraExample}

${sources.length ? '---\n\n## Sources\n\n' + sources.join('\n') + '\n' : ''}
`;
}

export function parseReferences(markdown: string, transcript: TranscriptSegment[] = []): NoteReference[] {
  const segmentMap = new Map(transcript.map((segment) => [segment.id, segment]));
  const references: NoteReference[] = [];
  const lines = markdown.split(/\r?\n/);
  let inSources = false;
  for (const line of lines) {
    if (/^##\s*Sources\s*$/i.test(line)) {
      inSources = true;
      continue;
    }
    if (inSources && /^##\s/.test(line)) inSources = false;
    if (!inSources) continue;
    const match = line.match(/^- \[(\d+)\] `([^`]+)`(?:\s+(.*))?$/);
    if (!match) continue;
    const number = Number(match[1]);
    const segmentId = match[2];
    const segment = segmentMap.get(segmentId);
    references.push({
      number,
      segmentId,
      text: match[3]?.trim() || segment?.text || '',
      start: segment?.start ?? 0,
    });
  }
  return references.sort((a, b) => a.number - b.number);
}

export function normalizeMath(markdown: string): string {
  return markdown.replace(/\\\[([\s\S]*?)\\\]/g, (_match, expression: string) =>
    `$$${expression.trim()}$$`,
  );
}

export function frontmatterValue(markdown: string, key: string): string {
  const match = markdown.match(/^---\n([\s\S]*?)\n---/);
  if (!match) return '';
  const line = match[1].split(/\r?\n/).find((entry) => new RegExp(`^${key}:\\s*`).test(entry));
  return line ? line.replace(new RegExp(`^${key}:\\s*`), '').trim() : '';
}

export function removeFrontmatterTag(markdown: string, tag: string): string {
  return markdown.replace(/^tags:\s*\[([^\]]*)\]/m, (_, current) => {
    const tags = current
      .split(',')
      .map((item: string) => item.trim())
      .filter((item: string) => item && item !== tag);
    return `tags: [${tags.join(', ')}]`;
  });
}