

import { state } from 'mumulib';


state.onstate(async new_state => {
  if (Object.keys(new_state).length === 0) {
    state.set_state({"person1": {}, "person2": {}})
  }
  const node = document.createElement("div");
  node.textContent = "Got state " + JSON.stringify(new_state);
  document.body.appendChild(node);
});

