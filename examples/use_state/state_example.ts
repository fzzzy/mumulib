

import { onstate, set_state, state } from '../../src/state';

async function main() {
  console.log('Initial state:', state);

  await onstate(async (newState) => {
    console.log('State changed:', newState);
  });
  
  await set_state({ exampleKey: 'exampleValue' });
  
  console.log('Final state:', state);  
}

main().catch(console.error);
