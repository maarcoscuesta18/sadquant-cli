import assert from 'node:assert/strict';
import {SADQUANT_TUI_EVENT, parseCommandOutputLine} from './runner.js';

function runTests(): void {
  parsesMarkdownEvent();
  parsesStatusEvent();
  parsesChartEvent();
  preservesAnsiTextOutput();
  preservesTextOutputOrdering();
  console.log('runner tests passed');
}

function parsesMarkdownEvent(): void {
  const event = parseCommandOutputLine(JSON.stringify({[SADQUANT_TUI_EVENT]: 'markdown', text: '# Title\n\n- One'}));

  assert.deepEqual(event, {kind: 'markdown', text: '# Title\n\n- One'});
}

function parsesStatusEvent(): void {
  const event = parseCommandOutputLine(JSON.stringify({[SADQUANT_TUI_EVENT]: 'status', label: 'Calling openai:gpt-5.5'}));

  assert.deepEqual(event, {kind: 'status', text: 'Calling openai:gpt-5.5'});
}

function parsesChartEvent(): void {
  const event = parseCommandOutputLine(JSON.stringify({[SADQUANT_TUI_EVENT]: 'chart', text: '[green]#[/green]'}));

  assert.deepEqual(event, {kind: 'chart', text: '[green]#[/green]'});
}

function preservesAnsiTextOutput(): void {
  const event = parseCommandOutputLine('\u001B[31mError\u001B[0m');

  assert.deepEqual(event, {kind: 'text', text: '\u001B[31mError\u001B[0m'});
}

function preservesTextOutputOrdering(): void {
  const lines = ['Preparing research...', 'SadQuant Research Agent', 'Tools Used'];
  const events = lines.map(line => parseCommandOutputLine(line));

  assert.deepEqual(events, [
    {kind: 'text', text: 'Preparing research...'},
    {kind: 'text', text: 'SadQuant Research Agent'},
    {kind: 'text', text: 'Tools Used'}
  ]);
}

runTests();
