/**
 * A bound component: the field's own input is bound to its text, and its
 * text is the app's title, given it by data-prop -- so typing in it changes
 * the app's title, through the component, which changes nothing itself.
 */
import { App, mountApp, mumuElement } from 'mumulib'
import Field from './field.sfc.html'

// The page's component first: the app sets its properties as it draws.
customElements.define('my-field', mumuElement(Field))

class Titled extends App<{ title: string }> {
  static state = { title: 'Things to do' }

  get label(): string {
    return 'Title'
  }
}

mountApp(Titled)
