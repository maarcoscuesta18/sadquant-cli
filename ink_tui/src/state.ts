import type {BridgeState, BridgeSuggestion, OptionEditorState, PendingOperation, RunningCommand, TranscriptMessage, UiState} from './types.js';

export const MAX_SUGGESTIONS = 8;

export const initialBridgeState: BridgeState = {
  modeLabel: 'NORMAL',
  planMode: false,
  activeCommand: null,
  activePrompt: '/',
  plannedCommand: null
};

export const initialUiState: UiState = {
  input: '',
  inputCursor: 0,
  messages: [],
  suggestions: [],
  suggestionIndex: 0,
  suggestionWindowStart: 0,
  bridgeState: initialBridgeState,
  running: null,
  pending: null,
  optionEditor: null,
  optionEditorFocused: false,
  latestExitStatus: null,
  history: [],
  historyIndex: null,
  historyDraft: null,
  interrupted: false
};

export type UiAction =
  | {type: 'set-input'; input: string; cursor?: number}
  | {type: 'insert-input'; text: string}
  | {type: 'move-input-cursor'; offset: number}
  | {type: 'move-input-cursor-to'; position: 'start' | 'end'}
  | {type: 'delete-input-backward'}
  | {type: 'delete-input-forward'}
  | {type: 'delete-input-before-cursor'}
  | {type: 'delete-input-after-cursor'}
  | {type: 'delete-input-word-backward'}
  | {type: 'add-message'; role: TranscriptMessage['role']; text: string}
  | {type: 'clear-messages'}
  | {type: 'reset-ui'}
  | {type: 'set-suggestions'; suggestions: BridgeSuggestion[]}
  | {type: 'clear-suggestions'}
  | {type: 'move-suggestion'; direction: 1 | -1; amount?: number; wrap?: boolean}
  | {type: 'set-bridge-state'; bridgeState: BridgeState}
  | {type: 'set-running'; running: RunningCommand | null}
  | {type: 'set-pending'; pending: PendingOperation | null}
  | {type: 'set-option-editor'; optionEditor: OptionEditorState | null; focused?: boolean}
  | {type: 'set-option-editor-focus'; focused: boolean}
  | {type: 'move-option-editor'; direction: 1 | -1}
  | {type: 'set-option-editor-value'; flag: string; value: string | boolean | undefined}
  | {type: 'set-exit-status'; status: number | null}
  | {type: 'push-history'; input: string}
  | {type: 'history'; direction: 1 | -1}
  | {type: 'set-interrupted'; interrupted: boolean};

export function uiReducer(state: UiState, action: UiAction): UiState {
  switch (action.type) {
    case 'set-input':
      return withInput(state, action.input, action.cursor ?? action.input.length);
    case 'insert-input':
      return insertInput(state, action.text);
    case 'move-input-cursor':
      return {...state, inputCursor: clamp(state.inputCursor + action.offset, 0, state.input.length)};
    case 'move-input-cursor-to':
      return {...state, inputCursor: action.position === 'start' ? 0 : state.input.length};
    case 'delete-input-backward':
      return deleteInputBackward(state);
    case 'delete-input-forward':
      return deleteInputForward(state);
    case 'delete-input-before-cursor':
      return deleteInputBeforeCursor(state);
    case 'delete-input-after-cursor':
      return deleteInputAfterCursor(state);
    case 'delete-input-word-backward':
      return deleteInputWordBackward(state);
    case 'add-message':
      return {
        ...state,
        messages: [
          ...state.messages,
          {id: nextMessageId(state.messages), role: action.role, text: action.text}
        ]
      };
    case 'clear-messages':
      return {...state, messages: []};
    case 'reset-ui':
      return {
        ...initialUiState,
        bridgeState: state.bridgeState,
        history: state.history
      };
    case 'set-suggestions':
      return {
        ...state,
        suggestions: action.suggestions,
        suggestionIndex: 0,
        suggestionWindowStart: 0
      };
    case 'clear-suggestions':
      return {...state, suggestions: [], suggestionIndex: 0, suggestionWindowStart: 0};
    case 'move-suggestion':
      if (state.suggestions.length === 0) {
        return state;
      }
      const amount = action.amount ?? 1;
      const nextIndex =
        action.wrap === false
          ? clamp(state.suggestionIndex + action.direction * amount, 0, state.suggestions.length - 1)
          : wrapIndex(state.suggestionIndex + action.direction * amount, state.suggestions.length);
      return {
        ...state,
        suggestionIndex: nextIndex,
        suggestionWindowStart: suggestionWindowStart(nextIndex, state.suggestions.length)
      };
    case 'set-bridge-state':
      return {...state, bridgeState: action.bridgeState};
    case 'set-running':
      return {...state, running: action.running, pending: action.running ? null : state.pending, interrupted: false};
    case 'set-pending':
      return {...state, pending: action.pending};
    case 'set-option-editor':
      return {...state, optionEditor: action.optionEditor, optionEditorFocused: Boolean(action.optionEditor && action.focused), suggestions: []};
    case 'set-option-editor-focus':
      return state.optionEditor ? {...state, optionEditorFocused: action.focused} : state;
    case 'move-option-editor':
      if (!state.optionEditor || state.optionEditor.schema.options.length === 0) {
        return state;
      }
      return {
        ...state,
        optionEditor: {
          ...state.optionEditor,
          selectedIndex: wrapIndex(state.optionEditor.selectedIndex + action.direction, state.optionEditor.schema.options.length)
        }
      };
    case 'set-option-editor-value':
      if (!state.optionEditor) {
        return state;
      }
      return {
        ...state,
        optionEditor: {
          ...state.optionEditor,
          values: {...state.optionEditor.values, [action.flag]: action.value}
        }
      };
    case 'set-exit-status':
      return {...state, latestExitStatus: action.status};
    case 'push-history':
      if (!action.input.trim()) {
        return state;
      }
      return {
        ...state,
        history: [action.input, ...state.history.filter(item => item !== action.input)].slice(0, 50),
        historyIndex: null
      };
    case 'history':
      return applyHistory(state, action.direction);
    case 'set-interrupted':
      return {...state, interrupted: action.interrupted};
    default:
      return state;
  }
}

function nextMessageId(messages: TranscriptMessage[]): number {
  const last = messages.at(-1);
  return last ? last.id + 1 : 1;
}

function withInput(state: UiState, input: string, cursor: number): UiState {
  return {
    ...state,
    input,
    inputCursor: clamp(cursor, 0, input.length),
    suggestions: [],
    suggestionIndex: 0,
    suggestionWindowStart: 0,
    historyIndex: null,
    historyDraft: null
  };
}

function insertInput(state: UiState, text: string): UiState {
  if (!text) {
    return state;
  }
  const input = `${state.input.slice(0, state.inputCursor)}${text}${state.input.slice(state.inputCursor)}`;
  return withInput(state, input, state.inputCursor + text.length);
}

function deleteInputBackward(state: UiState): UiState {
  if (state.inputCursor <= 0) {
    return state;
  }
  const input = `${state.input.slice(0, state.inputCursor - 1)}${state.input.slice(state.inputCursor)}`;
  return withInput(state, input, state.inputCursor - 1);
}

function deleteInputForward(state: UiState): UiState {
  if (state.inputCursor >= state.input.length) {
    return state;
  }
  const input = `${state.input.slice(0, state.inputCursor)}${state.input.slice(state.inputCursor + 1)}`;
  return withInput(state, input, state.inputCursor);
}

function deleteInputBeforeCursor(state: UiState): UiState {
  if (state.inputCursor <= 0) {
    return state;
  }
  const input = state.input.slice(state.inputCursor);
  return withInput(state, input, 0);
}

function deleteInputAfterCursor(state: UiState): UiState {
  if (state.inputCursor >= state.input.length) {
    return state;
  }
  const input = state.input.slice(0, state.inputCursor);
  return withInput(state, input, state.inputCursor);
}

function deleteInputWordBackward(state: UiState): UiState {
  if (state.inputCursor <= 0) {
    return state;
  }
  const beforeCursor = state.input.slice(0, state.inputCursor);
  const wordStart = previousWordStart(beforeCursor);
  const deleteStart = collapseWhitespaceBoundary(state.input, wordStart, state.inputCursor);
  const input = `${state.input.slice(0, deleteStart)}${state.input.slice(state.inputCursor)}`;
  return withInput(state, input, deleteStart);
}

function previousWordStart(value: string): number {
  let index = value.length;
  while (index > 0 && /\s/.test(value[index - 1] ?? '')) {
    index--;
  }
  while (index > 0 && !/\s/.test(value[index - 1] ?? '')) {
    index--;
  }
  return index;
}

function collapseWhitespaceBoundary(input: string, wordStart: number, cursor: number): number {
  if (wordStart <= 0 || cursor >= input.length) {
    return wordStart;
  }
  const beforeWord = input[wordStart - 1] ?? '';
  const afterCursor = input[cursor] ?? '';
  if (/\s/.test(beforeWord) && /\s/.test(afterCursor)) {
    return wordStart - 1;
  }
  return wordStart;
}

function wrapIndex(index: number, length: number): number {
  return ((index % length) + length) % length;
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

export function suggestionWindowStart(selected: number, total: number, size = MAX_SUGGESTIONS): number {
  if (total <= size) {
    return 0;
  }
  return Math.max(0, Math.min(selected - Math.floor(size / 2), total - size));
}

function applyHistory(state: UiState, direction: 1 | -1): UiState {
  if (state.history.length === 0) {
    return state;
  }
  const current = state.historyIndex ?? -1;
  const next = Math.max(-1, Math.min(state.history.length - 1, current + direction));
  const historyDraft = state.historyIndex === null ? state.input : state.historyDraft;
  const input = next === -1 ? historyDraft ?? '' : state.history[next] ?? '';
  return {
    ...state,
    historyIndex: next === -1 ? null : next,
    historyDraft: next === -1 ? null : historyDraft,
    input,
    inputCursor: input.length,
    suggestions: [],
    suggestionIndex: 0,
    suggestionWindowStart: 0
  };
}
