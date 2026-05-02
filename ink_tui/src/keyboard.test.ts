import assert from 'node:assert/strict';
import {normalizeKeypress, printableInput} from './keyboard.js';

function runTests(): void {
  normalizesArrowEscapeSequences();
  handlesMissingEscapeInput();
  dropsUnknownEscapeSequences();
  filtersControlCharactersFromPrintableInput();
  console.log('keyboard tests passed');
}

function normalizesArrowEscapeSequences(): void {
  const normalized = normalizeKeypress('\u001b[A', {name: 'escape'});

  assert.equal(normalized.input, '');
  assert.equal(normalized.key.name, 'up');
}

function handlesMissingEscapeInput(): void {
  const normalized = normalizeKeypress(undefined, {name: 'escape'});

  assert.equal(normalized.input, '');
  assert.equal(normalized.key.name, 'escape');
}

function dropsUnknownEscapeSequences(): void {
  const normalized = normalizeKeypress('\u001b[999~', {});

  assert.equal(normalized.input, '');
  assert.equal(normalized.key.name, undefined);
}

function filtersControlCharactersFromPrintableInput(): void {
  assert.equal(printableInput('A\u0001B\u001b[C'), 'AB[C');
}

runTests();
