

import { state, dialog } from 'mumulib';


class MyObject {
    my_method(args) {
        const node = document.createElement("div");
        node.textContent = "my_method was called " + args.name + " " + args.age;
        document.body.appendChild(node);
    }
}

state.onstate(async (new_state) => {
    if (!new_state.my_object) {
        state.set_state({my_object: new MyObject()});
    } else {
        dialog.do_dialog("my_dialog", "this.my_object", (el, _state) => el);
    }
});


