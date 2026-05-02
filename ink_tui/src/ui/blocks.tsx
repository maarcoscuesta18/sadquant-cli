import React from 'react';
import {Box, Text} from 'ink';
import type {TranscriptMessage} from '../types.js';
import {theme} from './theme.js';
import {MarkdownMessage} from './markdown.js';
import {renderAnsiText} from './ansi.js';

export function MessageBlock({message}: {message: TranscriptMessage}) {
  const lines = splitDisplayLines(message.text);
  if (isBlank(message.text) && message.role !== 'user') {
    return null;
  }

  switch (message.role) {
    case 'user':
      return <UserBlock message={message} lines={lines} />;
    case 'markdown':
      return <AssistantBlock message={message} />;
    case 'error':
      return <ErrorBlock message={message} lines={lines} />;
    case 'stderr':
      return <ErrorBlock message={message} lines={lines} subtle />;
    case 'system':
      return <SystemBlock message={message} lines={lines} />;
    case 'output':
    default:
      return <OutputBlock message={message} lines={lines} />;
  }
}

function UserBlock({message, lines}: {message: TranscriptMessage; lines: string[]}) {
  return (
    <Box flexDirection="column" marginTop={1}>
      {lines.map((line, index) => (
        <Text key={`${message.id}:${index}`} wrap="wrap">
          <Text color={theme.accent} bold>
            {index === 0 ? '> ' : '  '}
          </Text>
          <Text color={theme.textBright}>{line.length > 0 ? line : ' '}</Text>
        </Text>
      ))}
    </Box>
  );
}

function AssistantBlock({message}: {message: TranscriptMessage}) {
  return (
    <Box flexDirection="column" marginTop={1}>
      <MarkdownMessage text={message.text} />
    </Box>
  );
}

function OutputBlock({message, lines}: {message: TranscriptMessage; lines: string[]}) {
  return (
    <Box flexDirection="column">
      {lines.map((line, index) => (
        <Text key={`${message.id}:${index}`} wrap="truncate-end" color={theme.text}>
          {renderAnsiText(line.length > 0 ? line : ' ', theme.text)}
        </Text>
      ))}
    </Box>
  );
}

function SystemBlock({message, lines}: {message: TranscriptMessage; lines: string[]}) {
  return (
    <Box flexDirection="column">
      {lines.map((line, index) => (
        <Text key={`${message.id}:${index}`} wrap="wrap" color={theme.muted} dimColor>
          {index === 0 ? '· ' : '  '}
          {line}
        </Text>
      ))}
    </Box>
  );
}

function ErrorBlock({message, lines, subtle}: {message: TranscriptMessage; lines: string[]; subtle?: boolean}) {
  return (
    <Box flexDirection="column" marginTop={subtle ? 0 : 1}>
      {lines.map((line, index) => (
        <Text key={`${message.id}:${index}`} wrap="wrap" color={theme.danger}>
          {index === 0 ? (subtle ? '· ' : '✗ ') : '  '}
          {line.length > 0 ? line : ' '}
        </Text>
      ))}
    </Box>
  );
}

function isBlank(text: string): boolean {
  return text.replace(/\s/g, '').length === 0;
}

function splitDisplayLines(text: string): string[] {
  const lines = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n');
  return lines.length > 0 ? lines : [' '];
}
