

import { state } from 'mumulib';

let counter = 0;

function update() {
  state.set_state({"number": counter});
  counter++;
  setTimeout(update, 1000);
}

state.onstate(async new_state => {
  if (new_state.number === undefined) {
    update();
  }
  const node = document.createElement("div");
  node.textContent = "Got state " + JSON.stringify(new_state);
  document.body.appendChild(node);
});

