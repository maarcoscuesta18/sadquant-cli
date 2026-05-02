import React from 'react';
import {Box, Text} from 'ink';
import type {RuntimeConfig} from '../config.js';
import {theme} from './theme.js';

export function Banner({config}: {config: RuntimeConfig}) {
  return (
    <Box paddingX={1}>
      <Text color={theme.accent} bold>SadQuant</Text>
      <Text color={theme.muted}> v{config.version}  </Text>
      <Text color={theme.muted} dimColor>·  {truncatePath(config.project)}</Text>
    </Box>
  );
}

function truncatePath(value: string): string {
  if (value.length <= 60) {
    return value;
  }
  return `…${value.slice(value.length - 59)}`;
}
