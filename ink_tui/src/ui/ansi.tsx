import React from 'react';
import {Text} from 'ink';
import type {ThemeColor} from './theme.js';

export function stripAnsiForDisplay(value: string): string {
  return value.replace(/\u001B\[[0-9;]*m/g, '');
}

export function richMarkupToAnsi(value: string): string {
  return value
    .replace(/\[(\/)?green\]/g, (_, close) => (close ? '\u001B[0m' : '\u001B[32m'))
    .replace(/\[(\/)?red\]/g, (_, close) => (close ? '\u001B[0m' : '\u001B[31m'))
    .replace(/\[(\/)?cyan\]/g, (_, close) => (close ? '\u001B[0m' : '\u001B[36m'));
}

export function renderAnsiText(value: string, defaultColor: ThemeColor): React.ReactNode[] {
  const segments: React.ReactNode[] = [];
  const pattern = /\u001B\[([0-9;]*)m/g;
  let cursor = 0;
  let color: ThemeColor = defaultColor;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(value)) !== null) {
    if (match.index > cursor) {
      segments.push(
        <Text key={`ansi:${cursor}`} color={color}>
          {value.slice(cursor, match.index)}
        </Text>
      );
    }
    color = applyAnsiColor(match[1] ?? '', color, defaultColor);
    cursor = match.index + match[0].length;
  }

  if (cursor < value.length) {
    segments.push(
      <Text key={`ansi:${cursor}`} color={color}>
        {value.slice(cursor)}
      </Text>
    );
  }

  return segments.length > 0 ? segments : [<Text key="ansi:empty" color={defaultColor}>{value}</Text>];
}

function applyAnsiColor(sequence: string, currentColor: ThemeColor, defaultColor: ThemeColor): ThemeColor {
  const codes = sequence
    .split(';')
    .filter(Boolean)
    .map(value => Number.parseInt(value, 10))
    .filter(Number.isFinite);

  if (codes.length === 0) {
    return defaultColor;
  }

  let color = currentColor;
  for (const code of codes) {
    if (code === 0 || code === 39) {
      color = defaultColor;
    } else if (code === 31 || code === 91) {
      color = 'red';
    } else if (code === 32 || code === 92) {
      color = 'green';
    } else if (code === 33 || code === 93) {
      color = 'yellow';
    } else if (code === 34 || code === 94) {
      color = 'blue';
    } else if (code === 35 || code === 95) {
      color = 'magenta';
    } else if (code === 36 || code === 96) {
      color = 'cyan';
    } else if (code === 37 || code === 97) {
      color = 'white';
    } else if (code === 90) {
      color = 'gray';
    }
  }
  return color;
}
