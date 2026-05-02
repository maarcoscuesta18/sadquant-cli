import React from 'react';
import {Box, Text} from 'ink';
import {theme} from './theme.js';

export function Composer({
  prompt,
  planMode,
  input,
  cursor,
  columns,
  running,
  placeholder,
  hint
}: {
  prompt: string;
  planMode: boolean;
  input: string;
  cursor: number;
  columns: number;
  running: boolean;
  placeholder?: string;
  hint?: string;
}) {
  const promptLabel = planMode ? `plan ${prompt}` : prompt;
  const promptPill = ` ${promptLabel} `;
  const borderColor = running ? theme.warn : planMode ? theme.warn : theme.accent;
  const inputWidth = Math.max(8, columns - promptPill.length - 6);
  const hintText = hint ?? defaultHint(running);
  const isEmpty = input.length === 0;
  const ghost = isEmpty && placeholder ? placeholder.slice(0, Math.max(0, inputWidth - 1)) : '';

  return (
    <Box flexDirection="column">
      <Box borderStyle="round" borderColor={borderColor} paddingX={1}>
        <Text inverse color={borderColor}>{promptPill}</Text>
        <Text> </Text>
        <Box width={inputWidth} height={1} overflow="hidden">
          {isEmpty && ghost ? (
            <Text>
              <Text inverse color={theme.text}> </Text>
              <Text color={theme.muted} dimColor>{ghost}</Text>
            </Text>
          ) : (
            <InputLine value={input} cursor={cursor} width={inputWidth} />
          )}
        </Box>
      </Box>
      <Box paddingX={1}>
        <Text color={theme.muted}>{hintText}</Text>
      </Box>
    </Box>
  );
}

function InputLine({value, cursor, width}: {value: string; cursor: number; width: number}) {
  const visible = lineInputViewport(value, cursor, width);
  return (
    <Text>
      <Text color={theme.text}>{visible.before}</Text>
      <Text inverse color={theme.text}>{visible.atCursor}</Text>
      <Text color={theme.text}>{visible.after}</Text>
    </Text>
  );
}

function defaultHint(running: boolean): string {
  if (running) {
    return 'esc / ctrl+c stop  ·  output streams above';
  }
  return 'tab accept  ·  enter send  ·  ctrl+o options  ·  ? help  ·  ctrl+l clear';
}

export function lineInputViewport(value: string, cursor: number, width: number): {before: string; atCursor: string; after: string} {
  const safeCursor = Math.max(0, Math.min(cursor, value.length));
  const safeWidth = Math.max(1, width - 1);
  const start = Math.max(0, safeCursor - (safeWidth - 1));
  const before = value.slice(start, safeCursor);
  const afterWidth = Math.max(0, safeWidth - before.length - 1);

  return {
    before,
    atCursor: value.slice(safeCursor, safeCursor + 1) || ' ',
    after: value.slice(safeCursor + 1, safeCursor + 1 + afterWidth)
  };
}
