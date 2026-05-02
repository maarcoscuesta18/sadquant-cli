import {spawn, type ChildProcessWithoutNullStreams} from 'node:child_process';
import {createInterface} from 'node:readline';
import type {BridgeAction, BridgeCommand, BridgeCommandSchema, BridgeState, BridgeSuggestion} from './types.js';

type BridgeResponse = {
  ok: boolean;
  error?: string;
  action?: BridgeAction;
  state?: BridgeState;
  suggestions?: BridgeSuggestion[];
  accepted?: {text: string; cursor_position: number};
  schema?: BridgeCommandSchema;
  command?: BridgeCommand;
  input?: string;
};

export class BridgeClient {
  private readonly child: ChildProcessWithoutNullStreams;
  private lastStderr = '';
  private readonly pending: Array<{
    resolve: (value: BridgeResponse) => void;
    reject: (error: Error) => void;
  }> = [];

  constructor(python: string, moduleName: string, env: NodeJS.ProcessEnv) {
    this.child = spawn(python, ['-m', moduleName], {
      env,
      stdio: ['pipe', 'pipe', 'pipe'],
      windowsHide: true
    });

    const stdout = createInterface({input: this.child.stdout});
    stdout.on('line', line => this.resolveLine(line));

    this.child.stderr.on('data', chunk => {
      const text = String(chunk).trim();
      if (text) {
        this.lastStderr = text;
      }
    });

    this.child.on('error', error => this.rejectAll(error));
    this.child.on('exit', code => {
      if (this.pending.length > 0) {
        const details = this.lastStderr ? ` ${this.lastStderr}` : '';
        this.rejectAll(new Error(`TUI bridge exited with code ${code ?? 'unknown'}.${details}`));
      }
    });
  }

  hello(): Promise<BridgeResponse> {
    return this.request({type: 'hello'});
  }

  submit(text: string): Promise<BridgeResponse> {
    return this.request({type: 'submit', text});
  }

  suggestions(text: string): Promise<BridgeResponse> {
    return this.request({type: 'suggestions', text});
  }

  acceptSuggestion(text: string, suggestion: BridgeSuggestion): Promise<BridgeResponse> {
    return this.request({type: 'accept_suggestion', text, suggestion});
  }

  commandSchema(command: string): Promise<BridgeResponse> {
    return this.request({type: 'command_schema', command});
  }

  composeCommand(command: string, args: string[]): Promise<BridgeResponse> {
    return this.request({type: 'compose_command', command, args});
  }

  optionSuggestions(command: string, text: string): Promise<BridgeResponse> {
    return this.request({type: 'option_suggestions', command, text});
  }

  dispose(): void {
    this.child.kill();
  }

  private request(payload: Record<string, unknown>): Promise<BridgeResponse> {
    return new Promise((resolve, reject) => {
      this.pending.push({resolve, reject});
      this.child.stdin.write(`${JSON.stringify(payload)}\n`, error => {
        if (error) {
          this.rejectNext(error);
        }
      });
    });
  }

  private resolveLine(line: string): void {
    const pending = this.pending.shift();
    if (!pending) {
      return;
    }
    try {
      const response = JSON.parse(line) as BridgeResponse;
      if (!response.ok) {
        pending.reject(new Error(response.error ?? 'TUI bridge request failed.'));
        return;
      }
      pending.resolve(response);
    } catch (error) {
      pending.reject(error instanceof Error ? error : new Error(String(error)));
    }
  }

  private rejectNext(error: Error): void {
    const pending = this.pending.shift();
    if (pending) {
      pending.reject(error);
    }
  }

  private rejectAll(error: Error): void {
    while (this.pending.length > 0) {
      this.pending.shift()?.reject(error);
    }
  }
}
