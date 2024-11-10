

import { patslot } from '../../src';

window.onload = async () => {
  await patslot.fill_body({
    name: "Jane Smith",
    age: 12,
    color: "color: blue"
  });
  setTimeout(() => {
    patslot.fill_slots(
      document.getElementById("fill-element") as HTMLElement,
      "fill_me",
      "now been filled."
    );
  }, 2000);
}


