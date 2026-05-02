import React from 'react';
import {Box, Text} from 'ink';
import type {BridgeSuggestion} from '../types.js';
import {MAX_SUGGESTIONS} from '../state.js';
import {theme} from './theme.js';

export function SlashMenu({
  suggestions,
  selected,
  start,
  columns
}: {
  suggestions: BridgeSuggestion[];
  selected: number;
  start: number;
  columns: number;
}) {
  if (suggestions.length === 0) {
    return null;
  }

  const visible = suggestions.slice(start, start + MAX_SUGGESTIONS);
  const labelWidth = Math.min(20, Math.max(10, longestLabel(suggestions)));
  const descriptionWidth = Math.max(12, Math.min(80, columns - labelWidth - 12));

  return (
    <Box marginTop={1} borderStyle="round" borderColor={theme.accent} paddingX={1} flexDirection="column">
      <Box justifyContent="space-between">
        <Text color={theme.accent} bold>commands</Text>
        <Text color={theme.muted}>
          {start + 1}-{Math.min(start + MAX_SUGGESTIONS, suggestions.length)} of {suggestions.length}
        </Text>
      </Box>
      {visible.map((suggestion, index) => {
        const actualIndex = start + index;
        const isSelected = actualIndex === selected;
        const detail =
          suggestion.value === suggestion.label
            ? suggestion.description
            : `${suggestion.value}  —  ${suggestion.description}`;
        return (
          <Text
            key={`${suggestion.label}-${suggestion.value}-${actualIndex}`}
            wrap="truncate-end"
            color={isSelected ? theme.textBright : theme.text}
            inverse={isSelected}
          >
            {' '}{padEnd(suggestion.label, labelWidth)}  <Text color={isSelected ? theme.textBright : theme.muted}>{padEnd(detail, descriptionWidth)}</Text>{' '}
          </Text>
        );
      })}
      <Text color={theme.muted}>
        <Text color={theme.accent}>↑↓</Text> navigate · <Text color={theme.accent}>tab</Text> accept · <Text color={theme.accent}>enter</Text> run · <Text color={theme.accent}>esc</Text> close
      </Text>
    </Box>
  );
}

function longestLabel(suggestions: BridgeSuggestion[]): number {
  let max = 0;
  for (const suggestion of suggestions) {
    if (suggestion.label.length > max) {
      max = suggestion.label.length;
    }
  }
  return max;
}

function padEnd(value: string, width: number): string {
  if (value.length >= width) {
    return width <= 1 ? value.slice(0, width) : `${value.slice(0, Math.max(1, width - 1))}…`;
  }
  return value.padEnd(width);
}
