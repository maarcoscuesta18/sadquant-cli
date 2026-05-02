import {spawn, type ChildProcess} from 'node:child_process';
import {createInterface} from 'node:readline';
import stripAnsi from 'strip-ansi';

export const SADQUANT_TUI_EVENT = '__sadquant_tui_event__';

export type CommandOutputEvent = {
  kind: 'text' | 'chart' | 'markdown' | 'status' | 'stderr';
  text: string;
};

export type RunCommandOptions = {
  python: string;
  moduleName: string;
  argv: string[];
  env: NodeJS.ProcessEnv;
  onOutput: (event: CommandOutputEvent) => void;
};

export type RunningProcess = {
  display: string;
  interrupt: () => void;
  done: Promise<number>;
};

export function runSadQuantCommand(options: RunCommandOptions): RunningProcess {
  const child = spawn(options.python, ['-m', options.moduleName, ...options.argv], {
    env: options.env,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true
  });

  const stdout = createInterface({input: child.stdout});
  const stderr = createInterface({input: child.stderr});
  stdout.on('line', line => options.onOutput(parseCommandOutputLine(line)));
  stderr.on('line', line => options.onOutput({kind: 'stderr', text: stripAnsi(line)}));

  let finished = false;
  child.once('exit', () => {
    finished = true;
  });
  const done = waitForExit(child);
  return {
    display: `sadquant ${options.argv.join(' ')}`,
    interrupt: () => {
      if (!finished) {
        child.kill('SIGINT');
        setTimeout(() => {
          if (!finished) {
            child.kill('SIGTERM');
          }
        }, 1200).unref();
        setTimeout(() => {
          if (!finished) {
            child.kill('SIGKILL');
          }
        }, 3000).unref();
      }
    },
    done
  };
}

export function parseCommandOutputLine(line: string): CommandOutputEvent {
  try {
    const event = JSON.parse(line) as unknown;
    if (isMarkdownEvent(event)) {
      return {kind: 'markdown', text: event.text};
    }
    if (isStatusEvent(event)) {
      return {kind: 'status', text: event.label};
    }
    if (isChartEvent(event)) {
      return {kind: 'chart', text: event.text};
    }
  } catch {
    // Normal command output is not JSON.
  }
  return {kind: 'text', text: line};
}

function isMarkdownEvent(value: unknown): value is {text: string} {
  return isTuiEvent(value, 'markdown', 'text');
}

function isStatusEvent(value: unknown): value is {label: string} {
  return isTuiEvent(value, 'status', 'label');
}

function isChartEvent(value: unknown): value is {text: string} {
  return isTuiEvent(value, 'chart', 'text');
}

function isTuiEvent(value: unknown, kind: string, textKey: string): boolean {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const record = value as Record<string, unknown>;
  return record[SADQUANT_TUI_EVENT] === kind && typeof record[textKey] === 'string';
}

function waitForExit(child: ChildProcess): Promise<number> {
  return new Promise(resolve => {
    child.on('close', code => resolve(code ?? 1));
    child.on('error', () => resolve(1));
  });
}
