import React from 'react';
import {Box, Text} from 'ink';
import type {BridgeOptionSpec, OptionEditorState} from '../types.js';
import {theme} from './theme.js';

export function OptionEditor({
  editor,
  focused,
  columns
}: {
  editor: OptionEditorState | null;
  focused: boolean;
  columns: number;
}) {
  if (!editor) {
    return null;
  }
  const labelWidth = Math.min(22, Math.max(12, longestFlag(editor.schema.options)));
  const valueWidth = Math.max(10, Math.min(28, Math.floor((columns - labelWidth - 12) / 2)));
  const helpWidth = Math.max(12, columns - labelWidth - valueWidth - 12);
  const borderColor = focused ? theme.accent : theme.muted;

  return (
    <Box marginTop={1} borderStyle="round" borderColor={borderColor} paddingX={1} flexDirection="column">
      <Box justifyContent="space-between">
        <Text color={theme.accent} bold>options · /{editor.schema.name}</Text>
        <Text color={theme.muted}>
          {focused ? (
            <Text color={theme.warn}>editing · enter saves · esc blurs</Text>
          ) : (
            <Text>ctrl+o to edit</Text>
          )}
        </Text>
      </Box>
      {editor.schema.options.length === 0 ? (
        <Text color={theme.muted}>No configurable options.</Text>
      ) : (
        editor.schema.options.map((option, index) => {
          const isSelected = focused && index === editor.selectedIndex;
          const value = editor.values[option.flag];
          const display = optionDisplayValue(option, value);
          const valueColor = value === undefined || value === '' ? theme.muted : theme.success;
          return (
            <Text key={option.flag} wrap="truncate-end" inverse={isSelected} color={isSelected ? theme.textBright : theme.text}>
              {' '}{padEnd(option.aliases[0] ?? option.flag, labelWidth)}  <Text color={isSelected ? theme.textBright : valueColor}>{padEnd(display, valueWidth)}</Text>  <Text color={isSelected ? theme.textBright : theme.muted}>{padEnd(option.description, helpWidth)}</Text>{' '}
            </Text>
          );
        })
      )}
      {focused ? (
        <Text color={theme.muted}>
          <Text color={theme.accent}>↑↓</Text> select · <Text color={theme.accent}>←→</Text> cycle · <Text color={theme.accent}>space</Text> toggle · <Text color={theme.accent}>enter</Text> save · <Text color={theme.accent}>esc</Text> blur
        </Text>
      ) : (
        <Text color={theme.muted} dimColor>
          values are appended automatically when you submit
        </Text>
      )}
    </Box>
  );
}

function optionDisplayValue(option: BridgeOptionSpec, value: string | boolean | undefined): string {
  if (option.value_type === 'bool') {
    return value === true ? 'on' : 'off';
  }
  if (value === undefined || value === '') {
    return option.default ? `default ${option.default}` : '—';
  }
  return String(value);
}

function longestFlag(options: BridgeOptionSpec[]): number {
  let max = 0;
  for (const option of options) {
    const label = option.aliases[0] ?? option.flag;
    if (label.length > max) {
      max = label.length;
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
