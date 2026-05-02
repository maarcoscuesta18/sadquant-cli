#!/usr/bin/env node
process.env.FORCE_COLOR = '1';
delete process.env.NO_COLOR;

const React = await import('react');
const {render} = await import('ink');
const {App} = await import('./App.js');

render(React.createElement(App));
