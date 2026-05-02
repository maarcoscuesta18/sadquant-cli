import React from 'react';
import {Box, Static, Text} from 'ink';
import type {TranscriptMessage} from '../types.js';
import {theme} from './theme.js';
import {MessageBlock} from './blocks.js';

export function MessageStream({messages}: {messages: TranscriptMessage[]}) {
  if (messages.length === 0) {
    return (
      <Box marginTop={1} flexDirection="column">
        <Text color={theme.muted}>
          Welcome to <Text color={theme.accent} bold>SadQuant</Text>.
        </Text>
        <Text color={theme.muted}>
          Type <Text color={theme.accent}>/</Text> to browse commands, or ask a question. Press <Text color={theme.accent}>?</Text> for help.
        </Text>
      </Box>
    );
  }

  return (
    <Box flexDirection="column">
      <Static items={messages}>
        {message => <MessageBlock key={message.id} message={message} />}
      </Static>
    </Box>
  );
}
