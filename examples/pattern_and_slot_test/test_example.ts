import { patslot } from 'mumulib';

window.onload = async () => {
  try {
    // Clone the pattern twice with different slot values
    let a = await patslot.clone_pat("cloneme", {"hello": "Hello World"});
    let b = await patslot.clone_pat("cloneme", {"hello": "Bonjour Monde"});
    
    console.log("Cloned pattern a:", a);
    console.log("Cloned pattern b:", b);
    
    // Fill the body with both cloned elements in the main slot
    await patslot.fill_body({"main": [a, b]});
    
    // Show result
    const result = document.getElementById("result");
    if (result) {
      result.innerHTML = "<p>✅ Test completed! Check the main div above for the results.</p>";
    }
    
  } catch (error) {
    console.error("Error:", error);
    const result = document.getElementById("result");
    if (result) {
      result.innerHTML = `<p>❌ Error: ${error.message}</p>`;
    }
  }
}
