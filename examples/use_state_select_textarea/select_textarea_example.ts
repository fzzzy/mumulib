

import { state } from 'mumulib';


state.onstate(async new_state => {
  const node = document.createElement("div");
  node.className = "output";
  node.textContent = "Got state " + JSON.stringify(new_state);
  document.body.appendChild(node);
});
