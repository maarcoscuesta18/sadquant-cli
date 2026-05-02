import React from 'react';
import {Box, Text} from 'ink';
import {theme} from './theme.js';

type Binding = {keys: string; description: string};

const BINDINGS: Binding[] = [
  {keys: 'enter', description: 'send input · accept selected slash command'},
  {keys: 'tab', description: 'accept the highlighted suggestion'},
  {keys: '↑ / ↓', description: 'navigate suggestions · scroll history'},
  {keys: 'pgup/pgdn', description: 'page through long suggestion lists'},
  {keys: '← / →', description: 'move cursor · cycle option choices when focused'},
  {keys: 'esc', description: 'stop running · close palette · exit command mode'},
  {keys: 'ctrl+c', description: 'stop running command · quit when idle'},
  {keys: 'ctrl+l', description: 'clear the message stream'},
  {keys: 'ctrl+o', description: 'open / focus / close the options panel'},
  {keys: 'ctrl+u / ctrl+k', description: 'delete to start / end of line'},
  {keys: 'ctrl+w', description: 'delete previous word'},
  {keys: 'home / end', description: 'jump cursor to start / end'},
  {keys: '?', description: 'toggle this help overlay (when input is empty)'}
];

export function HelpOverlay({columns}: {columns: number}) {
  const keyWidth = 18;
  const descriptionWidth = Math.max(20, columns - keyWidth - 8);
  return (
    <Box marginTop={1} borderStyle="round" borderColor={theme.accent} paddingX={1} flexDirection="column">
      <Text color={theme.accent} bold>keybindings</Text>
      {BINDINGS.map(binding => (
        <Text key={binding.keys} wrap="truncate-end">
          <Text color={theme.accent}>{binding.keys.padEnd(keyWidth)}</Text>
          <Text color={theme.muted}>{truncate(binding.description, descriptionWidth)}</Text>
        </Text>
      ))}
      <Text color={theme.muted}>
        Press <Text color={theme.accent}>?</Text> or <Text color={theme.accent}>esc</Text> to close.
      </Text>
    </Box>
  );
}

function truncate(value: string, width: number): string {
  if (value.length <= width) {
    return value;
  }
  return `${value.slice(0, Math.max(1, width - 1))}…`;
}
