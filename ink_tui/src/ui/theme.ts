import type {TranscriptMessage} from '../types.js';

export type ThemeColor = 'cyan' | 'gray' | 'white' | 'red' | 'green' | 'yellow' | 'blue' | 'magenta' | 'whiteBright';

export const theme = {
  accent: 'cyan' as ThemeColor,
  accentSoft: 'blue' as ThemeColor,
  text: 'white' as ThemeColor,
  textBright: 'whiteBright' as ThemeColor,
  muted: 'gray' as ThemeColor,
  subtle: 'gray' as ThemeColor,
  success: 'green' as ThemeColor,
  warn: 'yellow' as ThemeColor,
  danger: 'red' as ThemeColor
};

export type Role = TranscriptMessage['role'];

export type RoleStyle = {
  color: ThemeColor;
  label: string;
  glyph: string;
};

const ROLE_STYLES: Record<Role, RoleStyle> = {
  user: {color: theme.accent, label: 'you', glyph: '>'},
  markdown: {color: theme.text, label: 'sadquant', glyph: '~'},
  output: {color: theme.muted, label: 'tool', glyph: '·'},
  stderr: {color: theme.danger, label: 'tool', glyph: '!'},
  system: {color: theme.muted, label: 'system', glyph: '*'},
  error: {color: theme.danger, label: 'error', glyph: '!'}
};

export function roleStyle(role: Role): RoleStyle {
  return ROLE_STYLES[role];
}
