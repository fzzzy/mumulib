

import { state } from '../../src';


state.onstate(async new_state => {
  const node = document.createElement("div");
  node.textContent = "Got state " + JSON.stringify(new_state);
  document.body.appendChild(node);
});
