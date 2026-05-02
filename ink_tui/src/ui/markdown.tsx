import React from 'react';
import {Box, Text} from 'ink';
import {theme} from './theme.js';

export function MarkdownMessage({text}: {text: string}) {
  const lines = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n');
  const rendered: React.ReactNode[] = [];
  let inCodeBlock = false;

  for (let index = 0; index < lines.length; index++) {
    const rawLine = lines[index] ?? '';
    const line = rawLine.trimEnd();
    const fence = line.match(/^```/);
    if (fence) {
      inCodeBlock = !inCodeBlock;
      rendered.push(
        <Text key={`md:${index}:fence`} color={theme.muted} dimColor>
          {inCodeBlock ? '─── code ───' : '────────────'}
        </Text>
      );
      continue;
    }

    if (inCodeBlock) {
      rendered.push(
        <Text key={`md:${index}:code`} color={theme.success} wrap="wrap">
          {'  '}{line || ' '}
        </Text>
      );
      continue;
    }

    if (!line.trim()) {
      rendered.push(<Text key={`md:${index}:blank`}> </Text>);
      continue;
    }

    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      rendered.push(
        <Text key={`md:${index}:heading`} bold color={theme.accent} wrap="wrap">
          {heading[2]}
        </Text>
      );
      continue;
    }

    const unordered = line.match(/^\s*[-*+]\s+(.+)$/);
    if (unordered) {
      rendered.push(
        <Text key={`md:${index}:ul`} wrap="wrap" color={theme.text}>
          <Text color={theme.accent}>• </Text>
          {renderInlineMarkdown(unordered[1] ?? '', index)}
        </Text>
      );
      continue;
    }

    const ordered = line.match(/^\s*(\d+)[.)]\s+(.+)$/);
    if (ordered) {
      rendered.push(
        <Text key={`md:${index}:ol`} wrap="wrap" color={theme.text}>
          <Text color={theme.accent}>{ordered[1]}. </Text>
          {renderInlineMarkdown(ordered[2] ?? '', index)}
        </Text>
      );
      continue;
    }

    const quote = line.match(/^\s*>\s?(.+)$/);
    if (quote) {
      rendered.push(
        <Text key={`md:${index}:quote`} color={theme.muted} wrap="wrap">
          │ {quote[1]}
        </Text>
      );
      continue;
    }

    rendered.push(
      <Text key={`md:${index}:p`} wrap="wrap" color={theme.text}>
        {renderInlineMarkdown(line, index)}
      </Text>
    );
  }

  return <Box flexDirection="column">{rendered}</Box>;
}

function renderInlineMarkdown(value: string, lineIndex: number): React.ReactNode[] {
  const segments: React.ReactNode[] = [];
  const pattern = /(`[^`]+`|\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\))/g;
  let cursor = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(value)) !== null) {
    if (match.index > cursor) {
      segments.push(value.slice(cursor, match.index));
    }
    const token = match[0];
    const key = `inline:${lineIndex}:${match.index}`;
    if (token.startsWith('`')) {
      segments.push(
        <Text key={key} color={theme.success}>
          {token.slice(1, -1)}
        </Text>
      );
    } else if (token.startsWith('**')) {
      segments.push(
        <Text key={key} bold>
          {token.slice(2, -2)}
        </Text>
      );
    } else {
      const link = token.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
      if (link) {
        segments.push(
          <Text key={key} color={theme.accentSoft} underline>
            {link[1]}
          </Text>
        );
      } else {
        segments.push(token);
      }
    }
    cursor = match.index + token.length;
  }

  if (cursor < value.length) {
    segments.push(value.slice(cursor));
  }
  return segments;
}
