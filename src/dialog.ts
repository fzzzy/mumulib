/**
 * Dialog
 *
 * This module provides functions for handling dialog interactions.
 *
 * Functions:
 * - do_dialog(dialog_name: string, path: string, render: (el: HTMLElement, state: object) => HTMLElement): void
 *   Opens a dialog, renders its content, and handles form submissions.
 *
 *   Parameters:
 *   - dialog_name: The ID of the dialog element to be opened.
 *   - path: The path to the state object to be used for rendering the dialog.
 *   - render: A function that takes an HTMLElement and a state object, and returns an HTMLElement representing the rendered dialog content.
 *
 *   Return value:
 *   - void
 */

import { set, get } from "object-path";
import morphdom from "morphdom";
import { set_state, state } from "./state";

type RenderFunc = (el: HTMLElement, state: object) => HTMLElement;


async function do_dialog(
  dialog_name: string,
  path: string,
  render: RenderFunc
) {
  set_state(
      {'selected': path}
  );
  const substate = get(state, path.substring(5));
  console.log("SUBSTATE", state, path, substate);

  const dialog = document.getElementById(dialog_name);
  if (dialog && dialog instanceof HTMLDialogElement) {
      const clone = await render(dialog, substate);
      console.log("cloned", dialog, clone);
      morphdom(dialog, clone);
      for (const d of Array.from(dialog.querySelectorAll('form'))) {
        d.onsubmit = (event) => {
            event.preventDefault();
            if (event.target) {
                let target = event.target as HTMLElement;
                while (!(target instanceof HTMLDialogElement)) {
                    if (target.parentNode) {
                        target = target.parentNode as HTMLElement;
                    } else {
                        console.error("Dialog target not found");
                        return;
                    }
                }
                target.close();
            }
        }
      }
      (dialog as HTMLDialogElement).showModal();
      dialog.onclose = async (ev) => {
          console.log("closing", ev.target);
          if (!ev.target) {
              return;
          }
          let form;
          const returnValue = (ev.target as HTMLDialogElement).returnValue;
          if (returnValue) {
              if (returnValue === "cancel") {
                  set_state({ 'selected': undefined });
                  return;
              }
              form = (ev.target as HTMLElement).querySelector(`form[name=${returnValue}]`);
              if (!form) {
                  form = (ev.target as HTMLElement).querySelector('form');
              }
          } else {
              form = (ev.target as HTMLElement).querySelector('form');
          }
          if (form) {
              const method = form.querySelector('input[name="method"]') as HTMLFormElement;
              if (method) {
                  const args: { [key: string]: string } = {};
                  for (const inp of Array.from(
                    form.querySelectorAll('input'))) {
                      args[inp.name] = inp.value;
                  }
                  console.log("calling method", method.value, args);
                  const got = get(state, args["path"].substring(5));
                  console.log("got", got);
                  delete args["method"];
                  delete args["path"];
                  const result = got[method.value].call(got, args);
                  if (result instanceof Promise) {
                      await result;
                  }
              } else {
                  for (const inp of Array.from(form.querySelectorAll('input'))) {
                      if (inp.name.substring(0, 9) === 'selected.') {
                          const fullname = `${state['selected']}.${inp.name.substring(9)}`;
                          console.log("setting", fullname, inp.value);
                          set(
                              state,
                              fullname.substring(5),
                              inp.value);
                      }
                  }
              }
              set_state({ 'selected': undefined });
          }
      }
  } else {
    console.error(`Dialog ${dialog_name} not found.`);
  }
}


export { do_dialog };
export type { RenderFunc };

