// Whether state.debug() has been turned on, which the state and dialog
// modules both ask. Neither index.ts nor anything else exports it.

let on = false

function set_debugging(mode: boolean) {
  on = mode
}

function debugging(): boolean {
  return on
}

// A line in the console, only in debug: a page's console is its own
function log(...args: unknown[]) {
  if (on) {
    console.log(...args)
  }
}

export { set_debugging, debugging, log }
