import assert from 'node:assert/strict';
import {
  currentTokenBeforeCursor,
  cycleOptionValue,
  inputWithPendingModeOptions,
  lineInputViewport,
  optionEditorArgs,
  richMarkupToAnsi,
  shouldEnterAcceptSuggestion,
  shouldSubmitAcceptedRootCommand,
  shouldTabAcceptSuggestion,
  stripAnsiForDisplay,
  tokenizeInput
} from './App.js';
import type {OptionEditorState} from './types.js';

function runTests(): void {
  readsCurrentTokenBeforeCursor();
  enterAcceptsPartialCommandSuggestion();
  enterAcceptsBareSlashSuggestionInsideActiveMode();
  enterDoesNotAcceptSuggestionsInsideActiveMode();
  enterSubmitsAfterCompletedCommand();
  enterSubmitsAcceptedRootSlashCommand();
  enterDoesNotSubmitNonCommandSuggestion();
  tabAcceptsSuggestionAfterTrailingSpace();
  rendersShortInputWithoutEllipsis();
  keepsCursorVisibleInLongInput();
  stripsAnsiForDisplayText();
  convertsRichChartMarkupToAnsi();
  tokenizesQuotedInputForOptionEditor();
  buildsOptionEditorArgs();
  appendsPendingModeOptionsToSubmittedInput();
  cyclesChoiceOptionValues();
  console.log('app helper tests passed');
}

function readsCurrentTokenBeforeCursor(): void {
  assert.equal(currentTokenBeforeCursor('/research NVDA --w', '/research NVDA --w'.length), '--w');
  assert.equal(currentTokenBeforeCursor('/research ', '/research '.length), '');
  assert.equal(currentTokenBeforeCursor('/research NVDA --web', '/research NVDA'.length), 'NVDA');
}

function enterAcceptsPartialCommandSuggestion(): void {
  assert.equal(shouldEnterAcceptSuggestion('/rese', '/rese'.length, 1), true);
}

function enterAcceptsBareSlashSuggestionInsideActiveMode(): void {
  assert.equal(shouldEnterAcceptSuggestion('/', '/'.length, 1, 'chart'), true);
  assert.equal(shouldEnterAcceptSuggestion('/fund', '/fund'.length, 1, 'chart'), true);
}

function enterDoesNotAcceptSuggestionsInsideActiveMode(): void {
  assert.equal(shouldEnterAcceptSuggestion('NVDA --w', 'NVDA --w'.length, 1, 'research'), false);
}

function enterSubmitsAfterCompletedCommand(): void {
  assert.equal(shouldEnterAcceptSuggestion('/research ', '/research '.length, 1), false);
}

function enterSubmitsAcceptedRootSlashCommand(): void {
  assert.equal(
    shouldSubmitAcceptedRootCommand('/rese', {
      value: '/research',
      label: '/research',
      description: 'Run research',
      replaceToken: true
    }),
    true
  );
}

function enterDoesNotSubmitNonCommandSuggestion(): void {
  assert.equal(
    shouldSubmitAcceptedRootCommand('/research NVDA --w', {
      value: '--web',
      label: '--web',
      description: 'research option',
      replaceToken: true
    }),
    false
  );
}

function tabAcceptsSuggestionAfterTrailingSpace(): void {
  assert.equal(shouldTabAcceptSuggestion(1), true);
  assert.equal(currentTokenBeforeCursor('/research ', '/research '.length), '');
}

function rendersShortInputWithoutEllipsis(): void {
  assert.deepEqual(lineInputViewport('/', 1, 10), {
    before: '/',
    atCursor: ' ',
    after: ''
  });
}

function keepsCursorVisibleInLongInput(): void {
  assert.deepEqual(lineInputViewport('/research NVDA what changed today', 21, 12), {
    before: 'VDA what c',
    atCursor: 'h',
    after: ''
  });
}

function stripsAnsiForDisplayText(): void {
  assert.equal(stripAnsiForDisplay('\u001B[32mup\u001B[0m \u001B[31mdown\u001B[0m'), 'up down');
}

function convertsRichChartMarkupToAnsi(): void {
  assert.equal(richMarkupToAnsi('[green]up[/green] [red]down[/red] [cyan]vol[/cyan]'), '\u001B[32mup\u001B[0m \u001B[31mdown\u001B[0m \u001B[36mvol\u001B[0m');
}

function tokenizesQuotedInputForOptionEditor(): void {
  assert.deepEqual(tokenizeInput('NVDA "what changed"'), ['NVDA', 'what changed']);
}

function buildsOptionEditorArgs(): void {
  const editor: OptionEditorState = {
    command: 'setup',
    selectedIndex: 0,
    values: {'--horizon': 'swing', '--journal-signal': true, '--output': undefined},
    schema: {
      name: 'setup',
      description: 'Setup',
      examples: [],
      subcommands: [],
      templates: [],
      options: [
        {flag: '--horizon', aliases: ['horizon'], value_type: 'choice', choices: ['swing', 'position'], default: 'swing', repeatable: false, description: ''},
        {flag: '--journal-signal', aliases: ['journal'], value_type: 'bool', choices: [], default: null, repeatable: false, description: ''},
        {flag: '--output', aliases: ['output'], value_type: 'path', choices: [], default: null, repeatable: false, description: ''}
      ]
    }
  };

  assert.deepEqual(optionEditorArgs(editor), ['--horizon', 'swing', '--journal-signal']);
}

function appendsPendingModeOptionsToSubmittedInput(): void {
  const editor: OptionEditorState = {
    command: 'research',
    selectedIndex: 0,
    values: {'--web': true, '--horizon': 'swing'},
    schema: {
      name: 'research',
      description: 'Research',
      examples: [],
      subcommands: [],
      templates: [],
      options: [
        {flag: '--web', aliases: ['web'], value_type: 'bool', choices: [], default: null, repeatable: false, description: ''},
        {flag: '--horizon', aliases: ['horizon'], value_type: 'choice', choices: ['swing', 'position'], default: 'swing', repeatable: false, description: ''}
      ]
    }
  };

  assert.equal(
    inputWithPendingModeOptions('NVDA "What changed?"', {bridgeState: {activeCommand: 'research'}, optionEditor: editor}),
    'NVDA "What changed?" --web --horizon swing'
  );
}

function cyclesChoiceOptionValues(): void {
  const option = {flag: '--horizon', aliases: ['horizon'], value_type: 'choice' as const, choices: ['intraday', 'swing', 'position'], default: 'swing', repeatable: false, description: ''};

  assert.equal(cycleOptionValue(option, undefined, 1), 'position');
  assert.equal(cycleOptionValue(option, 'position', 1), 'intraday');
}

runTests();
