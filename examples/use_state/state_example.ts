

import { state } from 'mumulib';


state.onstate(async new_state => {
  const node = document.createElement("div");
  node.textContent = "Got state " + JSON.stringify(new_state);
  document.body.appendChild(node);
});

state.set_state({hello: "world"});

state.set_path("hello", "everybody");

