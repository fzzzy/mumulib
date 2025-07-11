



if (typeof document === 'undefined') {
  const domino = require('domino');
  global.document = domino.createWindow('').document;
}

export * as patslot from './patslot';
export type { Pattern, Template } from './patslot';
export * as state from './state';
export type { State, OnStateChange } from './state';
export * as dialog from './dialog';
export type { RenderFunc } from './dialog';









