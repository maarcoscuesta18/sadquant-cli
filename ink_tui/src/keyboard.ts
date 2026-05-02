export type ReadlineKey = {
  name?: string;
  sequence?: string;
  ctrl?: boolean;
  meta?: boolean;
  shift?: boolean;
};

export type NormalizedKeypress = {
  input: string;
  key: ReadlineKey;
};

const ESCAPE_SEQUENCE_NAMES = new Map<string, string>([
  ['\u001b[A', 'up'],
  ['\u001bOA', 'up'],
  ['\u001b[B', 'down'],
  ['\u001bOB', 'down'],
  ['\u001b[C', 'right'],
  ['\u001bOC', 'right'],
  ['\u001b[D', 'left'],
  ['\u001bOD', 'left'],
  ['\u001b[H', 'home'],
  ['\u001bOH', 'home'],
  ['\u001b[F', 'end'],
  ['\u001bOF', 'end'],
  ['\u001b[3~', 'delete'],
  ['\u001b[5~', 'pageup'],
  ['\u001b[6~', 'pagedown']
]);

export function normalizeKeypress(input: string | undefined, key: ReadlineKey | undefined): NormalizedKeypress {
  const safeInput = input ?? '';
  const safeKey = key ?? {};
  const sequence = safeKey.sequence ?? safeInput;
  const sequenceName = ESCAPE_SEQUENCE_NAMES.get(sequence);
  if (sequenceName) {
    return {input: '', key: {...safeKey, name: sequenceName, sequence}};
  }
  if (safeInput.includes('\u001b')) {
    return {input: '', key: safeKey};
  }
  return {input: safeInput, key: safeKey};
}

export function printableInput(input: string): string {
  return [...input].filter(character => character >= ' ' && character !== '\u007f').join('');
}
