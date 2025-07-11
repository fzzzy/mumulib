

import { patslot } from 'mumulib';


window.onload = async () => {
  // Clone the pattern twice with different slot values
  let a = await patslot.clone_pat("cloneme", {"hello": "Hello World"});
  let b = await patslot.clone_pat("cloneme", {"hello": "Bonjour Monde"});
  console.log(a, b);
  
  // Fill the body with both cloned elements in the main slot
  await patslot.fill_body({"main": [a, b]});
}