import {emitKeypressEvents} from 'node:readline';
import React, {useCallback, useEffect, useMemo, useReducer, useRef, useState} from 'react';
import {Box, useApp, useStdin, useStdout} from 'ink';
import {BridgeClient} from './bridge.js';
import {readRuntimeConfig, type RuntimeConfig} from './config.js';
import {normalizeKeypress, printableInput, type ReadlineKey} from './keyboard.js';
import {runSadQuantCommand, type CommandOutputEvent, type RunningProcess} from './runner.js';
import {MAX_SUGGESTIONS, initialUiState, uiReducer, type UiAction} from './state.js';
import type {BridgeAction, BridgeOptionSpec, BridgeSuggestion, OptionEditorState} from './types.js';
import {Banner} from './ui/Banner.js';
import {MessageStream} from './ui/MessageStream.js';
import {ActivityIndicator} from './ui/ActivityIndicator.js';
import {SlashMenu} from './ui/SlashMenu.js';
import {OptionEditor} from './ui/OptionEditor.js';
import {HelpOverlay} from './ui/HelpOverlay.js';
import {Composer, lineInputViewport} from './ui/Composer.js';
import {StatusBar} from './ui/StatusBar.js';
import {richMarkupToAnsi, stripAnsiForDisplay} from './ui/ansi.js';

export {lineInputViewport, richMarkupToAnsi, stripAnsiForDisplay};

type KeypressInput = NodeJS.ReadStream & {
  on(event: 'keypress', listener: (input: string | undefined, key: ReadlineKey | undefined) => void): KeypressInput;
  off(event: 'keypress', listener: (input: string | undefined, key: ReadlineKey | undefined) => void): KeypressInput;
};

export function App({config}: {config?: RuntimeConfig}) {
  const {exit} = useApp();
  const {stdin, setRawMode, isRawModeSupported} = useStdin();
  const columns = useTerminalColumns();
  const runtimeConfig = useMemo(() => config ?? readRuntimeConfig(), [config]);
  const [state, dispatch] = useReducer(uiReducer, initialUiState);
  const [helpOpen, setHelpOpen] = useState(false);
  const bridgeRef = useRef<BridgeClient | null>(null);
  const runningRef = useRef<RunningProcess | null>(null);
  const submittingRef = useRef(false);
  const stateRef = useRef(state);
  const helpOpenRef = useRef(helpOpen);
  const suggestionRequestRef = useRef(0);
  const rawModeWarningRef = useRef(false);
  const keypressEventsReadyRef = useRef(false);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  useEffect(() => {
    helpOpenRef.current = helpOpen;
  }, [helpOpen]);

  useEffect(() => {
    const bridge = new BridgeClient(runtimeConfig.python, runtimeConfig.bridgeModule, runtimeConfig.env);
    bridgeRef.current = bridge;
    bridge
      .hello()
      .then(response => {
        if (response.state) {
          dispatch({type: 'set-bridge-state', bridgeState: response.state});
        }
      })
      .catch(error => dispatch({type: 'add-message', role: 'error', text: error.message}));
    return () => bridge.dispose();
  }, [runtimeConfig]);

  useEffect(() => {
    const bridge = bridgeRef.current;
    if (!bridge) {
      return;
    }
    const requestId = ++suggestionRequestRef.current;
    bridge
      .suggestions(state.input)
      .then(response => {
        if (requestId !== suggestionRequestRef.current) {
          return;
        }
        if (response.state) {
          dispatch({type: 'set-bridge-state', bridgeState: response.state});
        }
        dispatch({type: 'set-suggestions', suggestions: response.suggestions ?? []});
      })
      .catch(error => dispatch({type: 'add-message', role: 'error', text: error.message}));
  }, [state.input]);

  const acceptCurrentSuggestion = useCallback(async (): Promise<string | null> => {
    const bridge = bridgeRef.current;
    const currentState = stateRef.current;
    const suggestion = currentState.suggestions[currentState.suggestionIndex];
    if (!bridge || !suggestion) {
      return null;
    }
    try {
      const response = await bridge.acceptSuggestion(currentState.input, suggestion);
      let acceptedText: string | null = null;
      if (response.accepted) {
        acceptedText = response.accepted.text;
        dispatch({type: 'set-input', input: response.accepted.text, cursor: response.accepted.cursor_position});
      }
      dispatch({type: 'clear-suggestions'});
      if (response.state) {
        dispatch({type: 'set-bridge-state', bridgeState: response.state});
      }
      return acceptedText;
    } catch (error) {
      dispatch({type: 'add-message', role: 'error', text: error instanceof Error ? error.message : String(error)});
      return null;
    }
  }, []);

  const openOptionEditor = useCallback(async (commandOverride?: string, focused = true) => {
    const bridge = bridgeRef.current;
    const currentState = stateRef.current;
    const command = commandOverride ?? currentState.bridgeState.activeCommand;
    if (!bridge || !command) {
      dispatch({type: 'add-message', role: 'error', text: 'Enter a command mode first, then press Ctrl+O to edit options.'});
      return;
    }
    try {
      const response = await bridge.commandSchema(command);
      if (!response.schema) {
        dispatch({type: 'add-message', role: 'error', text: `No option schema for ${command}.`});
        return;
      }
      dispatch({type: 'set-option-editor', optionEditor: {command, schema: response.schema, selectedIndex: 0, values: {}}, focused});
      if (response.state) {
        dispatch({type: 'set-bridge-state', bridgeState: response.state});
      }
    } catch (error) {
      dispatch({type: 'add-message', role: 'error', text: error instanceof Error ? error.message : String(error)});
    }
  }, []);

  useEffect(() => {
    const activeCommand = state.bridgeState.activeCommand;
    const editor = state.optionEditor;
    if (!activeCommand) {
      if (editor) {
        dispatch({type: 'set-option-editor', optionEditor: null});
      }
      return;
    }
    if (editor && editor.command === activeCommand) {
      return;
    }
    void openOptionEditor(activeCommand, false);
  }, [state.bridgeState.activeCommand, state.optionEditor, openOptionEditor]);

  const applyOptionEditor = useCallback(() => {
    if (!stateRef.current.optionEditor) {
      return;
    }
    dispatch({type: 'set-option-editor-focus', focused: false});
  }, []);

  const stopRunningCommand = useCallback((): boolean => {
    if (!runningRef.current) {
      return false;
    }
    runningRef.current.interrupt();
    dispatch({type: 'set-interrupted', interrupted: true});
    dispatch({type: 'add-message', role: 'system', text: 'Stop requested.'});
    return true;
  }, []);

  const executeAction = useCallback(
    async (action: BridgeAction) => {
      if (!action.command) {
        dispatch({type: 'add-message', role: 'error', text: 'No command to execute.'});
        return;
      }
      const argv = normalizeCommandArgvForTui(action.command);
      const env: NodeJS.ProcessEnv = {
        ...runtimeConfig.env,
        SADQUANT_TUI: '1',
        SADQUANT_TUI_MARKDOWN: '1',
        SADQUANT_TUI_CHART_MARKUP: '1',
        SADQUANT_TUI_STATUS_EVENTS: '1',
        SADQUANT_FORCE_TERMINAL: '1',
        PYTHONUTF8: '1',
        PYTHONIOENCODING: 'utf-8',
        FORCE_COLOR: '1',
        COLUMNS: String(columns)
      };
      delete env.NO_COLOR;
      const running = runSadQuantCommand({
        python: runtimeConfig.python,
        moduleName: runtimeConfig.cliModule,
        argv,
        env,
        onOutput: event => {
          const action = outputEventToAction(event);
          if (action) {
            dispatch(action);
          }
        }
      });
      runningRef.current = running;
      dispatch({type: 'set-running', running: {display: running.display, argv}});
      dispatch({type: 'set-exit-status', status: null});
      const status = await running.done;
      runningRef.current = null;
      dispatch({type: 'set-running', running: null});
      dispatch({type: 'set-exit-status', status});
      if (status !== 0) {
        dispatch({
          type: 'add-message',
          role: 'error',
          text: `Exited ${status} ${running.display}`
        });
      }
    },
    [columns, runtimeConfig]
  );

  const submitInput = useCallback(
    async (value: string) => {
      const bridge = bridgeRef.current;
      const currentState = stateRef.current;
      const text = inputWithPendingModeOptions(value, currentState).trim();
      if (!bridge || !text) {
        return;
      }
      if (runningRef.current) {
        dispatch({type: 'add-message', role: 'system', text: 'A command is already running. Press Esc or Ctrl+C to stop it.'});
        return;
      }
      if (submittingRef.current) {
        return;
      }
      submittingRef.current = true;
      dispatch({
        type: 'add-message',
        role: 'user',
        text: userTranscriptText(currentState.bridgeState.activePrompt, currentState.bridgeState.planMode, text)
      });
      dispatch({type: 'push-history', input: text});
      dispatch({type: 'set-input', input: '', cursor: 0});
      dispatch({type: 'clear-suggestions'});
      dispatch({type: 'set-pending', pending: {label: 'Thinking'}});
      try {
        const response = await bridge.submit(text);
        if (response.state) {
          dispatch({type: 'set-bridge-state', bridgeState: response.state});
        }
        const action = response.action;
        if (!action) {
          return;
        }
        if (action.kind === 'exit') {
          dispatch({type: 'set-pending', pending: null});
          exit();
          return;
        }
        if (action.kind === 'clear') {
          dispatch({type: 'reset-ui'});
          const previous = response.state ?? currentState.bridgeState;
          if (previous.activeCommand) {
            try {
              const exitResponse = await bridge.submit('/exit-mode');
              if (exitResponse.state) {
                dispatch({type: 'set-bridge-state', bridgeState: exitResponse.state});
              }
            } catch {
              // Best-effort reset; keep transcript clean even if Python rejects.
            }
          }
          if (previous.planMode) {
            try {
              const planResponse = await bridge.submit('/plan off');
              if (planResponse.state) {
                dispatch({type: 'set-bridge-state', bridgeState: planResponse.state});
              }
            } catch {
              // Best-effort reset.
            }
          }
          return;
        }
        if (action.message) {
          dispatch({type: 'add-message', role: action.kind === 'error' ? 'error' : 'system', text: action.message});
        }
        // Option editor is auto-synced to bridgeState.activeCommand via useEffect.
        if (action.kind === 'execute') {
          dispatch({type: 'set-pending', pending: {label: 'Starting command'}});
          await executeAction(action);
        }
      } catch (error) {
        dispatch({type: 'add-message', role: 'error', text: error instanceof Error ? error.message : String(error)});
      } finally {
        submittingRef.current = false;
        dispatch({type: 'set-pending', pending: null});
      }
    },
    [executeAction, exit]
  );

  const handleKeypress = useCallback(
    (rawInput: string | undefined, rawKey: ReadlineKey | undefined) => {
      const normalized = normalizeKeypress(rawInput, rawKey);
      const input = normalized.input;
      const key = normalized.key;
      const currentState = stateRef.current;
      const helpVisible = helpOpenRef.current;

      if (key.ctrl && key.name === 'c') {
        if (!stopRunningCommand()) {
          exit();
        }
        return;
      }

      if (helpVisible) {
        if (key.name === 'escape' || input === '?' || (key.name === 'return' || key.name === 'enter')) {
          setHelpOpen(false);
          return;
        }
        return;
      }

      if (key.ctrl && key.name === 'o') {
        if (currentState.optionEditor) {
          dispatch({type: 'set-option-editor-focus', focused: !currentState.optionEditorFocused});
        } else if (currentState.bridgeState.activeCommand) {
          void openOptionEditor(currentState.bridgeState.activeCommand, true);
        } else {
          dispatch({type: 'add-message', role: 'error', text: 'Enter a command mode first, then press Ctrl+O to edit options.'});
        }
        return;
      }
      if (currentState.optionEditor && currentState.optionEditorFocused) {
        if (key.name === 'escape') {
          dispatch({type: 'set-option-editor-focus', focused: false});
          return;
        }
        if (key.name === 'return' || key.name === 'enter') {
          void applyOptionEditor();
          return;
        }
        if (key.name === 'up' || (key.ctrl && key.name === 'p')) {
          dispatch({type: 'move-option-editor', direction: -1});
          return;
        }
        if (key.name === 'down' || (key.ctrl && key.name === 'n')) {
          dispatch({type: 'move-option-editor', direction: 1});
          return;
        }
        const option = selectedOption(currentState.optionEditor);
        if (option) {
          if (key.name === 'left' || key.name === 'right') {
            dispatch({
              type: 'set-option-editor-value',
              flag: option.flag,
              value: cycleOptionValue(option, currentState.optionEditor.values[option.flag], key.name === 'right' ? 1 : -1)
            });
            return;
          }
          if ((key.name === 'space' || input === ' ') && option.value_type === 'bool') {
            dispatch({type: 'set-option-editor-value', flag: option.flag, value: currentState.optionEditor.values[option.flag] !== true});
            return;
          }
          if (key.name === 'backspace' && option.value_type !== 'bool') {
            const current = String(currentState.optionEditor.values[option.flag] ?? '');
            dispatch({type: 'set-option-editor-value', flag: option.flag, value: current.slice(0, -1) || undefined});
            return;
          }
          const printable = printableInput(input);
          if (!key.ctrl && !key.meta && printable && option.value_type !== 'bool') {
            const current = String(currentState.optionEditor.values[option.flag] ?? '');
            dispatch({type: 'set-option-editor-value', flag: option.flag, value: `${current}${printable}`});
            return;
          }
        }
        return;
      }
      if (key.name === 'escape') {
        if (stopRunningCommand()) {
          return;
        }
        if (currentState.suggestions.length > 0) {
          dispatch({type: 'clear-suggestions'});
        } else if (currentState.input) {
          dispatch({type: 'set-input', input: '', cursor: 0});
        } else if (currentState.bridgeState.activeCommand) {
          void submitInput('/exit-mode');
        }
        return;
      }
      if (key.name === 'return' || key.name === 'enter') {
        if (shouldEnterAcceptSuggestion(currentState.input, currentState.inputCursor, currentState.suggestions.length, currentState.bridgeState.activeCommand)) {
          const suggestion = currentState.suggestions[currentState.suggestionIndex];
          void acceptCurrentSuggestion().then(acceptedText => {
            if (acceptedText && shouldSubmitAcceptedRootCommand(currentState.input, suggestion)) {
              void submitInput(acceptedText);
            }
          });
          return;
        }
        void submitInput(currentState.input);
        return;
      }
      if (key.name === 'tab') {
        if (shouldTabAcceptSuggestion(currentState.suggestions.length)) {
          void acceptCurrentSuggestion();
        }
        return;
      }
      if (key.ctrl && key.name === 'u') {
        dispatch({type: 'delete-input-before-cursor'});
        return;
      }
      if (key.ctrl && key.name === 'k') {
        dispatch({type: 'delete-input-after-cursor'});
        return;
      }
      if (key.ctrl && key.name === 'w') {
        dispatch({type: 'delete-input-word-backward'});
        return;
      }
      if (key.ctrl && key.name === 'l') {
        dispatch({type: 'clear-messages'});
        return;
      }
      if (key.name === 'up' || (key.ctrl && key.name === 'p')) {
        if (currentState.suggestions.length > 0) {
          dispatch({type: 'move-suggestion', direction: -1});
        } else {
          dispatch({type: 'history', direction: 1});
        }
        return;
      }
      if (key.name === 'down' || (key.ctrl && key.name === 'n')) {
        if (currentState.suggestions.length > 0) {
          dispatch({type: 'move-suggestion', direction: 1});
        } else {
          dispatch({type: 'history', direction: -1});
        }
        return;
      }
      if (key.name === 'pageup') {
        dispatch({type: 'move-suggestion', direction: -1, amount: MAX_SUGGESTIONS, wrap: false});
        return;
      }
      if (key.name === 'pagedown') {
        dispatch({type: 'move-suggestion', direction: 1, amount: MAX_SUGGESTIONS, wrap: false});
        return;
      }
      if (key.name === 'left') {
        dispatch({type: 'move-input-cursor', offset: -1});
        return;
      }
      if (key.name === 'right') {
        dispatch({type: 'move-input-cursor', offset: 1});
        return;
      }
      if (key.name === 'home' || (key.ctrl && key.name === 'a')) {
        dispatch({type: 'move-input-cursor-to', position: 'start'});
        return;
      }
      if (key.name === 'end' || (key.ctrl && key.name === 'e')) {
        dispatch({type: 'move-input-cursor-to', position: 'end'});
        return;
      }
      if (key.name === 'backspace') {
        dispatch({type: 'delete-input-backward'});
        return;
      }
      if (key.name === 'delete') {
        dispatch({type: 'delete-input-forward'});
        return;
      }
      if (input === '?' && currentState.input.length === 0 && !currentState.optionEditor) {
        setHelpOpen(true);
        return;
      }
      const printable = printableInput(input);
      if (!key.ctrl && !key.meta && printable) {
        dispatch({type: 'insert-input', text: printable});
      }
    },
    [acceptCurrentSuggestion, applyOptionEditor, exit, openOptionEditor, stopRunningCommand, submitInput]
  );

  useEffect(() => {
    if (!isRawModeSupported) {
      if (!rawModeWarningRef.current) {
        rawModeWarningRef.current = true;
        dispatch({type: 'add-message', role: 'error', text: 'Interactive input requires a TTY with raw mode support.'});
      }
      return;
    }
    const input = stdin as KeypressInput;
    if (!keypressEventsReadyRef.current) {
      emitKeypressEvents(input);
      keypressEventsReadyRef.current = true;
    }
    setRawMode(true);
    input.on('keypress', handleKeypress);
    return () => {
      input.off('keypress', handleKeypress);
      try {
        setRawMode(false);
      } catch {
        // The stream can already be closed while Ink is tearing down.
      }
    };
  }, [handleKeypress, isRawModeSupported, setRawMode, stdin]);

  const showSlashMenu = !helpOpen && state.suggestions.length > 0;
  const showOptionEditor = Boolean(state.optionEditor) && !helpOpen;
  const running = Boolean(state.running);
  const placeholder = composerPlaceholder(state.bridgeState.activeCommand, state.bridgeState.activePrompt, state.optionEditor);

  return (
    <Box flexDirection="column">
      <Banner config={runtimeConfig} />
      <MessageStream messages={state.messages} />
      <ActivityIndicator pending={state.pending?.label ?? null} running={state.running?.display ?? null} />
      {helpOpen ? <HelpOverlay columns={columns} /> : null}
      {showSlashMenu ? (
        <SlashMenu
          suggestions={state.suggestions}
          selected={state.suggestionIndex}
          start={state.suggestionWindowStart}
          columns={columns}
        />
      ) : null}
      <Composer
        prompt={state.bridgeState.activePrompt}
        planMode={state.bridgeState.planMode}
        input={state.input}
        cursor={state.inputCursor}
        columns={columns}
        running={running}
        placeholder={placeholder}
      />
      {showOptionEditor ? (
        <OptionEditor editor={state.optionEditor} focused={state.optionEditorFocused} columns={columns} />
      ) : null}
      <StatusBar
        bridgeState={state.bridgeState}
        exitStatus={state.latestExitStatus}
        interrupted={state.interrupted}
        running={running}
        columns={columns}
      />
    </Box>
  );
}

function composerPlaceholder(
  activeCommand: string | null,
  activePrompt: string,
  editor: import('./types.js').OptionEditorState | null
): string {
  if (!activeCommand) {
    return 'Type / to browse commands, or ask SadQuant anything…';
  }
  if (editor && editor.command === activeCommand) {
    const example = editor.schema.examples?.[0]?.trim() ?? '';
    if (example) {
      return stripCommandPrefix(example, activePrompt, editor.schema.name);
    }
  }
  return `prompt for /${activeCommand}…`;
}

function stripCommandPrefix(example: string, activePrompt: string, commandName: string): string {
  const withSpace = (prefix: string) => (example.startsWith(`${prefix} `) ? example.slice(prefix.length + 1) : null);
  return withSpace(activePrompt) ?? withSpace(`/${commandName}`) ?? withSpace(commandName) ?? example;
}

function useTerminalColumns(): number {
  const {stdout} = useStdout();
  const [columns, setColumns] = useState(() => stdout.columns ?? 120);

  useEffect(() => {
    const updateColumns = () => setColumns(stdout.columns ?? 120);
    stdout.on('resize', updateColumns);
    updateColumns();
    return () => {
      stdout.off('resize', updateColumns);
    };
  }, [stdout]);

  return Math.max(24, columns);
}

export function currentTokenBeforeCursor(input: string, cursor = input.length): string {
  const safeCursor = Math.max(0, Math.min(cursor, input.length));
  const beforeCursor = input.slice(0, safeCursor);
  if (!beforeCursor || /\s$/.test(beforeCursor)) {
    return '';
  }
  return beforeCursor.split(/\s+/).at(-1) ?? '';
}

export function tokenizeInput(input: string): string[] {
  const tokens: string[] = [];
  const pattern = /"([^"]*)"|'([^']*)'|(\S+)/g;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(input)) !== null) {
    tokens.push(match[1] ?? match[2] ?? match[3] ?? '');
  }
  return tokens;
}

export function optionEditorArgs(editor: OptionEditorState): string[] {
  const args: string[] = [];
  for (const option of editor.schema.options) {
    const value = editor.values[option.flag];
    if (value === undefined || value === false || value === '') {
      continue;
    }
    args.push(option.flag);
    if (option.value_type !== 'bool') {
      args.push(String(value));
    }
  }
  return args;
}

export function inputWithPendingModeOptions(input: string, state: {bridgeState: {activeCommand: string | null}; optionEditor: OptionEditorState | null}): string {
  const editor = state.optionEditor;
  if (!state.bridgeState.activeCommand || !editor || editor.command !== state.bridgeState.activeCommand) {
    return input;
  }
  const args = optionEditorArgs(editor);
  if (args.length === 0) {
    return input;
  }
  const separator = input.trim() ? ' ' : '';
  return `${input.trimEnd()}${separator}${args.join(' ')}`;
}

export function selectedOption(editor: OptionEditorState): BridgeOptionSpec | null {
  return editor.schema.options[editor.selectedIndex] ?? null;
}

export function cycleOptionValue(option: BridgeOptionSpec, current: string | boolean | undefined, direction: 1 | -1): string | boolean | undefined {
  if (option.value_type === 'bool') {
    return current !== true;
  }
  if (option.choices.length === 0) {
    return current;
  }
  const currentText = typeof current === 'string' ? current : option.default ?? option.choices[0] ?? '';
  const currentIndex = Math.max(0, option.choices.indexOf(currentText));
  return option.choices[wrapNumber(currentIndex + direction, option.choices.length)];
}

function wrapNumber(index: number, length: number): number {
  return ((index % length) + length) % length;
}

export function shouldEnterAcceptSuggestion(input: string, cursor: number, suggestionCount: number, activeCommand: string | null = null): boolean {
  if (suggestionCount === 0 || currentTokenBeforeCursor(input, cursor).length === 0) {
    return false;
  }
  return activeCommand === null || isBareRootSlashPrefix(input);
}

export function shouldTabAcceptSuggestion(suggestionCount: number): boolean {
  return suggestionCount > 0;
}

export function shouldSubmitAcceptedRootCommand(input: string, suggestion: BridgeSuggestion | undefined): boolean {
  return Boolean(suggestion?.value.startsWith('/') && suggestion.value.trim() === suggestion.value && isBareRootSlashPrefix(input));
}

function isBareRootSlashPrefix(input: string): boolean {
  const trimmed = input.trim();
  return trimmed.startsWith('/') && !trimmed.includes(' ');
}

function userTranscriptText(activePrompt: string, planMode: boolean, input: string): string {
  if (activePrompt === '/') {
    return planMode ? `plan ${input}` : input;
  }
  const prompt = planMode ? `plan ${activePrompt}` : activePrompt;
  return `${prompt} ${input}`;
}

function outputEventToAction(event: CommandOutputEvent): UiAction | null {
  if (event.kind === 'markdown') {
    return {type: 'add-message', role: 'markdown', text: event.text};
  }
  if (event.kind === 'chart') {
    return {type: 'add-message', role: 'output', text: richMarkupToAnsi(event.text)};
  }
  if (event.kind === 'status') {
    return {type: 'set-pending', pending: {label: event.text}};
  }
  if (event.kind === 'stderr') {
    if (isBlankText(event.text)) {
      return null;
    }
    return {type: 'add-message', role: 'stderr', text: event.text};
  }
  if (isBlankText(event.text)) {
    return null;
  }
  return {type: 'add-message', role: 'output', text: event.text};
}

function isBlankText(text: string): boolean {
  return text.replace(/\s/g, '').length === 0;
}

function normalizeCommandArgvForTui(command: NonNullable<BridgeAction['command']>): string[] {
  return command.argv;
}
