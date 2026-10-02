// The state tree itself, the state and dialog modules' own and nobody else's:
// index.ts exports neither this module nor the tree. A page reads the state
// as onstate gives it, as it changes, never by reaching in.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const tree: { [key: string]: any } = {}
