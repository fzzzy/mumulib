/**
 * mumulib in Node: the library, with domino's DOM installed first.
 *
 *   import { state, patslot } from 'mumulib/node'
 *
 * The library reads document as it loads, so the DOM comes first: an import
 * is run before the next, and these are two modules, not one. Where there is
 * a DOM already -- jsdom -- import 'mumulib' instead, which sets nothing.
 */

import './dom.js'

export * from './index.js'
