import { onstate, set_state, state } from '../src/state';

await onstate((newState) => {
  console.log('State changed:', newState);
});

await set_state({ exampleKey: 'exampleValue' });

console.log('Initial state:', state);
