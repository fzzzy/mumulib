

import { state } from 'mumulib';


let counter = 0;

function update() {
  let selected = state.state[state.state["selected"]];
  selected["number"] = counter;
  state.set_state(null);
  counter++;
  setTimeout(update, 1000);
}

state.onstate(async new_state => {
  if (Object.keys(new_state).length === 0) {
    state.set_state({"selected": "person1", "person1": {}, "person2": {}});
    console.log(state.state);
    update();
  }
  const node = document.createElement("div");
  node.textContent = "Got state " + JSON.stringify(new_state);
  document.body.appendChild(node);
});

