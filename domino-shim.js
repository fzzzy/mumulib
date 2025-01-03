if (typeof document === 'undefined') {
  const domino = require('domino');
  global.document = domino.createWindow('').document;
}
require('./dist/src/index.js');

