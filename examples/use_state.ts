import { onstate, set_state, state } from '../src/state';

onstate((newState) => {
  console.log('State changed:', newState);
});

set_state({ exampleKey: 'exampleValue' });

console.log('Initial state:', state);
