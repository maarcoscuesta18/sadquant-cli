import React from 'react';
import {Box, Text} from 'ink';
import type {BridgeState} from '../types.js';
import {theme} from './theme.js';

export function StatusBar({
  bridgeState,
  exitStatus,
  interrupted,
  running,
  columns
}: {
  bridgeState: BridgeState;
  exitStatus: number | null;
  interrupted: boolean;
  running: boolean;
  columns: number;
}) {
  const modeLabel = bridgeState.planMode ? 'PLAN' : bridgeState.modeLabel.toUpperCase();
  const modeColor = bridgeState.planMode ? theme.warn : theme.accent;
  const planned = bridgeState.plannedCommand?.display ?? null;

  return (
    <Box paddingX={1} columnGap={1} flexWrap="wrap">
      <Text inverse color={modeColor}>{` ${modeLabel} `}</Text>
      <Text color={theme.muted}>·</Text>
      <Text color={theme.muted}>
        cmd <Text color={bridgeState.activeCommand ? theme.text : theme.muted}>{bridgeState.activeCommand ?? '—'}</Text>
      </Text>
      <Text color={theme.muted}>·</Text>
      <Text color={theme.muted}>
        planned <Text color={planned ? theme.text : theme.muted}>{planned ?? '—'}</Text>
      </Text>
      <Text color={theme.muted}>·</Text>
      <Text color={theme.muted}>
        exit <Text color={exitColor(exitStatus)}>{exitStatus === null ? '—' : String(exitStatus)}</Text>
      </Text>
      <Text color={theme.muted}>·</Text>
      <Text color={theme.muted}>
        {running ? <Text color={theme.warn}>running</Text> : interrupted ? <Text color={theme.danger}>interrupted</Text> : <Text color={theme.success}>idle</Text>}
      </Text>
      <Text color={theme.muted}>·</Text>
      <Text color={theme.muted}>cols {columns}</Text>
    </Box>
  );
}

function exitColor(status: number | null) {
  if (status === null) return theme.muted;
  if (status === 0) return theme.success;
  return theme.danger;
}
