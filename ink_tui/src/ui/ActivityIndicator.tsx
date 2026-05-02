import React, {useEffect, useState} from 'react';
import {Box, Text} from 'ink';
import {theme} from './theme.js';

const SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];

export function ActivityIndicator({pending, running}: {pending: string | null; running: string | null}) {
  const active = Boolean(pending || running);
  const frame = useSpinnerFrame(active);
  const label = pending ?? (running ? `Running ${running}` : null);
  if (!label) {
    return null;
  }
  return (
    <Box marginTop={1} paddingX={1}>
      <Text color={theme.warn}>{SPINNER_FRAMES[frame]} </Text>
      <Text color={theme.muted}>{label}</Text>
    </Box>
  );
}

function useSpinnerFrame(active: boolean): number {
  const [frame, setFrame] = useState(0);
  useEffect(() => {
    if (!active) {
      setFrame(0);
      return;
    }
    const timer = setInterval(() => setFrame(current => (current + 1) % SPINNER_FRAMES.length), 90);
    return () => clearInterval(timer);
  }, [active]);
  return frame;
}
