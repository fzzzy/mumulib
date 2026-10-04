// domino ships no types: what src/dom.ts uses of it
declare module 'domino' {
  const domino: {
    createWindow(html?: string, address?: string): Window & typeof globalThis
  }
  export default domino
}
