import assert from 'node:assert/strict';
import {MAX_SUGGESTIONS, initialBridgeState, initialUiState, suggestionWindowStart, uiReducer} from './state.js';

const suggestion = {
  value: '/chart',
  label: '/chart',
  description: 'Draw a chart',
  replaceToken: true
};

function runTests(): void {
  appendsTranscriptMessages();
  appendsMarkdownTranscriptMessages();
  editsInputAtCursor();
  movesCursorToBoundaries();
  deletesAroundCursor();
  deletesBeforeCursor();
  deletesAfterCursor();
  deletesPreviousWord();
  setsAcceptedSuggestionCursor();
  wrapsSuggestionNavigation();
  keepsSuggestionWindowOnSelectedItem();
  pagesSuggestionNavigation();
  tracksRunningAndInterruptState();
  updatesPendingStatusWithoutTranscriptMessages();
  storesCommandHistory();
  restoresHistoryDraft();
  updatesBridgeState();
  editsOptionEditorState();
  tracksOptionEditorFocus();
  console.log('state reducer tests passed');
}

function appendsTranscriptMessages(): void {
  const first = uiReducer(initialUiState, {type: 'add-message', role: 'user', text: '/providers'});
  const second = uiReducer(first, {type: 'add-message', role: 'output', text: 'Provider Status'});

  assert.deepEqual(second.messages, [
    {id: 1, role: 'user', text: '/providers'},
    {id: 2, role: 'output', text: 'Provider Status'}
  ]);
}

function appendsMarkdownTranscriptMessages(): void {
  const state = uiReducer(initialUiState, {type: 'add-message', role: 'markdown', text: '# Research\n\n- Point'});

  assert.deepEqual(state.messages, [
    {id: 1, role: 'markdown', text: '# Research\n\n- Point'}
  ]);
}

function editsInputAtCursor(): void {
  const withInput = uiReducer(initialUiState, {type: 'set-input', input: '/chart NVA', cursor: 9});
  const edited = uiReducer(withInput, {type: 'insert-input', text: 'D'});

  assert.equal(edited.input, '/chart NVDA');
  assert.equal(edited.inputCursor, 10);
}

function movesCursorToBoundaries(): void {
  const withInput = uiReducer(initialUiState, {type: 'set-input', input: '/chart NVDA', cursor: 5});
  const start = uiReducer(withInput, {type: 'move-input-cursor-to', position: 'start'});
  const end = uiReducer(start, {type: 'move-input-cursor-to', position: 'end'});
  const pastEnd = uiReducer(end, {type: 'move-input-cursor', offset: 10});
  const pastStart = uiReducer(start, {type: 'move-input-cursor', offset: -10});

  assert.equal(start.inputCursor, 0);
  assert.equal(end.inputCursor, '/chart NVDA'.length);
  assert.equal(pastEnd.inputCursor, '/chart NVDA'.length);
  assert.equal(pastStart.inputCursor, 0);
}

function deletesAroundCursor(): void {
  const withInput = uiReducer(initialUiState, {type: 'set-input', input: '/chart NVDXA', cursor: 11});
  const backward = uiReducer(withInput, {type: 'delete-input-backward'});
  const forward = uiReducer(backward, {type: 'delete-input-forward'});

  assert.equal(backward.input, '/chart NVDA');
  assert.equal(backward.inputCursor, 10);
  assert.equal(forward.input, '/chart NVD');
  assert.equal(forward.inputCursor, 10);
}

function deletesBeforeCursor(): void {
  const withInput = uiReducer(initialUiState, {type: 'set-input', input: '/research NVDA --web', cursor: 14});
  const cleared = uiReducer(withInput, {type: 'delete-input-before-cursor'});

  assert.equal(cleared.input, ' --web');
  assert.equal(cleared.inputCursor, 0);
}

function deletesAfterCursor(): void {
  const withInput = uiReducer(initialUiState, {type: 'set-input', input: '/research NVDA --web', cursor: 14});
  const cleared = uiReducer(withInput, {type: 'delete-input-after-cursor'});

  assert.equal(cleared.input, '/research NVDA');
  assert.equal(cleared.inputCursor, 14);
}

function deletesPreviousWord(): void {
  const withInput = uiReducer(initialUiState, {type: 'set-input', input: '/research NVDA --web', cursor: 14});
  const deleted = uiReducer(withInput, {type: 'delete-input-word-backward'});

  assert.equal(deleted.input, '/research --web');
  assert.equal(deleted.inputCursor, 9);
}

function setsAcceptedSuggestionCursor(): void {
  const state = uiReducer(initialUiState, {type: 'set-input', input: '/correlate ', cursor: 11});

  assert.equal(state.input, '/correlate ');
  assert.equal(state.inputCursor, 11);
}

function wrapsSuggestionNavigation(): void {
  const withSuggestions = uiReducer(initialUiState, {
    type: 'set-suggestions',
    suggestions: [suggestion, {...suggestion, value: '/scan', label: '/scan'}]
  });

  const previous = uiReducer(withSuggestions, {type: 'move-suggestion', direction: -1});
  const next = uiReducer(previous, {type: 'move-suggestion', direction: 1});

  assert.equal(previous.suggestionIndex, 1);
  assert.equal(next.suggestionIndex, 0);
}

function keepsSuggestionWindowOnSelectedItem(): void {
  const suggestions = Array.from({length: 20}, (_, index) => ({...suggestion, value: `/cmd-${index}`, label: `/cmd-${index}`}));
  let state = uiReducer(initialUiState, {type: 'set-suggestions', suggestions});

  for (let index = 0; index < 14; index++) {
    state = uiReducer(state, {type: 'move-suggestion', direction: 1});
  }

  assert.equal(state.suggestionIndex, 14);
  assert.equal(state.suggestionWindowStart, suggestionWindowStart(14, suggestions.length));
  assert.ok(state.suggestionIndex >= state.suggestionWindowStart);
  assert.ok(state.suggestionIndex < state.suggestionWindowStart + MAX_SUGGESTIONS);
}

function pagesSuggestionNavigation(): void {
  const suggestions = Array.from({length: 20}, (_, index) => ({...suggestion, value: `/cmd-${index}`, label: `/cmd-${index}`}));
  const withSuggestions = uiReducer(initialUiState, {type: 'set-suggestions', suggestions});
  const pageDown = uiReducer(withSuggestions, {type: 'move-suggestion', direction: 1, amount: MAX_SUGGESTIONS, wrap: false});
  const pageUp = uiReducer(pageDown, {type: 'move-suggestion', direction: -1, amount: MAX_SUGGESTIONS, wrap: false});
  const pagePastEnd = uiReducer(pageDown, {type: 'move-suggestion', direction: 1, amount: 100, wrap: false});

  assert.equal(pageDown.suggestionIndex, MAX_SUGGESTIONS);
  assert.equal(pageUp.suggestionIndex, 0);
  assert.equal(pagePastEnd.suggestionIndex, suggestions.length - 1);
}

function tracksRunningAndInterruptState(): void {
  const running = uiReducer(initialUiState, {
    type: 'set-running',
    running: {display: 'sadquant providers', argv: ['providers']}
  });
  const interrupted = uiReducer(running, {type: 'set-interrupted', interrupted: true});
  const idle = uiReducer(interrupted, {type: 'set-running', running: null});

  assert.equal(running.running?.display, 'sadquant providers');
  assert.equal(interrupted.interrupted, true);
  assert.equal(idle.running, null);
  assert.equal(idle.interrupted, false);
}

function updatesPendingStatusWithoutTranscriptMessages(): void {
  const state = uiReducer(initialUiState, {type: 'set-pending', pending: {label: 'Calling openai:gpt-5.5'}});

  assert.equal(state.pending?.label, 'Calling openai:gpt-5.5');
  assert.deepEqual(state.messages, []);
}

function storesCommandHistory(): void {
  const one = uiReducer(initialUiState, {type: 'push-history', input: '/providers'});
  const two = uiReducer(one, {type: 'push-history', input: '/chart NVDA'});
  const older = uiReducer(two, {type: 'history', direction: 1});
  const oldest = uiReducer(older, {type: 'history', direction: 1});
  const newer = uiReducer(oldest, {type: 'history', direction: -1});

  assert.equal(older.input, '/chart NVDA');
  assert.equal(older.inputCursor, '/chart NVDA'.length);
  assert.equal(oldest.input, '/providers');
  assert.equal(newer.input, '/chart NVDA');
}

function restoresHistoryDraft(): void {
  const one = uiReducer(initialUiState, {type: 'push-history', input: '/providers'});
  const draft = uiReducer(one, {type: 'set-input', input: '/cha', cursor: 4});
  const history = uiReducer(draft, {type: 'history', direction: 1});
  const restored = uiReducer(history, {type: 'history', direction: -1});

  assert.equal(history.input, '/providers');
  assert.equal(restored.input, '/cha');
  assert.equal(restored.inputCursor, 4);
}

function updatesBridgeState(): void {
  const state = uiReducer(initialUiState, {
    type: 'set-bridge-state',
    bridgeState: {...initialBridgeState, modeLabel: 'PLAN', planMode: true}
  });

  assert.equal(state.bridgeState.modeLabel, 'PLAN');
  assert.deepEqual(state.messages, []);
}

function editsOptionEditorState(): void {
  const editor = {
    command: 'setup',
    selectedIndex: 0,
    values: {},
    schema: {
      name: 'setup',
      description: 'Setup',
      examples: [],
      subcommands: [],
      templates: [],
      options: [
        {flag: '--horizon', aliases: ['horizon'], value_type: 'choice' as const, choices: ['swing'], default: 'swing', repeatable: false, description: ''},
        {flag: '--journal-signal', aliases: ['journal'], value_type: 'bool' as const, choices: [], default: null, repeatable: false, description: ''}
      ]
    }
  };

  const opened = uiReducer(initialUiState, {type: 'set-option-editor', optionEditor: editor});
  const moved = uiReducer(opened, {type: 'move-option-editor', direction: 1});
  const edited = uiReducer(moved, {type: 'set-option-editor-value', flag: '--journal-signal', value: true});

  assert.equal(opened.optionEditor?.command, 'setup');
  assert.equal(opened.optionEditorFocused, false);
  assert.equal(moved.optionEditor?.selectedIndex, 1);
  assert.equal(edited.optionEditor?.values['--journal-signal'], true);
}

function tracksOptionEditorFocus(): void {
  const editor = {
    command: 'research',
    selectedIndex: 0,
    values: {},
    schema: {
      name: 'research',
      description: 'Research',
      examples: [],
      subcommands: [],
      templates: [],
      options: [
        {flag: '--web', aliases: ['web'], value_type: 'bool' as const, choices: [], default: null, repeatable: false, description: ''}
      ]
    }
  };

  const autoOpened = uiReducer(initialUiState, {type: 'set-option-editor', optionEditor: editor});
  const focused = uiReducer(autoOpened, {type: 'set-option-editor-focus', focused: true});
  const closed = uiReducer(focused, {type: 'set-option-editor', optionEditor: null});

  assert.equal(autoOpened.optionEditorFocused, false);
  assert.equal(focused.optionEditorFocused, true);
  assert.equal(closed.optionEditor, null);
  assert.equal(closed.optionEditorFocused, false);
}

runTests();
