

import { patslot } from '../../src';

window.onload = async () => {
  // Returns an HTMLElement with the slots filled
  let node = await patslot.clone_pat("person", {
    name: "Jane Smith",
    age: 12,
    color: "color: blue"
  });

  document.body.appendChild(node);
}

