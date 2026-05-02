export type BridgeCommand = {
  name: string;
  args: string[];
  argv: string[];
  raw: string;
  native: boolean;
  display: string;
};

export type BridgeAction = {
  kind: 'clear' | 'error' | 'execute' | 'exit' | 'help' | 'mode' | 'plan' | 'planned';
  message: string;
  command: BridgeCommand | null;
};

export type BridgeSuggestion = {
  value: string;
  label: string;
  description: string;
  replaceToken: boolean;
};

export type BridgeOptionSpec = {
  flag: string;
  aliases: string[];
  value_type: 'bool' | 'choice' | 'int' | 'text' | 'path';
  choices: string[];
  default: string | null;
  repeatable: boolean;
  description: string;
};

export type BridgeCommandSchema = {
  name: string;
  description: string;
  examples: string[];
  subcommands: string[];
  templates: Array<Record<string, unknown>>;
  options: BridgeOptionSpec[];
};

export type BridgeState = {
  modeLabel: string;
  planMode: boolean;
  activeCommand: string | null;
  activePrompt: string;
  plannedCommand: BridgeCommand | null;
};

export type TranscriptMessage = {
  id: number;
  role: 'user' | 'system' | 'output' | 'markdown' | 'stderr' | 'error';
  text: string;
};

export type RunningCommand = {
  display: string;
  argv: string[];
};

export type PendingOperation = {
  label: string;
};

export type OptionEditorState = {
  command: string;
  schema: BridgeCommandSchema;
  selectedIndex: number;
  values: Record<string, string | boolean | undefined>;
};

export type UiState = {
  input: string;
  inputCursor: number;
  messages: TranscriptMessage[];
  suggestions: BridgeSuggestion[];
  suggestionIndex: number;
  suggestionWindowStart: number;
  bridgeState: BridgeState;
  running: RunningCommand | null;
  pending: PendingOperation | null;
  optionEditor: OptionEditorState | null;
  optionEditorFocused: boolean;
  latestExitStatus: number | null;
  history: string[];
  historyIndex: number | null;
  historyDraft: string | null;
  interrupted: boolean;
};
