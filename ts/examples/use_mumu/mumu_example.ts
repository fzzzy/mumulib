/**
 * Mumu components: each .sfc.html is a plain class that reads its state and
 * emits events, and mumuElement makes the element that stands in front of it.
 * The page owns the state: it sets the elements' properties, and changes
 * them when a component asks.
 */
import { Mumu, mumuElement, mumuView } from 'mumulib'
import Opener from './opener.sfc.html'
import Light from './light.sfc.html'
import Lights from './lights.sfc.html'
import Lines from './lines.sfc.html'
import Messages from './messages.sfc.html'
import Room from './room.sfc.html'

customElements.define('my-opener', mumuElement(Opener))
customElements.define('my-light', mumuElement(Light))
customElements.define('my-lights', mumuElement(Lights))
customElements.define('my-lines', mumuElement(Lines))
customElements.define('my-messages', mumuElement(Messages))
customElements.define('my-room', mumuElement(Room))

type Props = HTMLElement & Record<string, unknown>
const opener = document.querySelector('my-opener') as Props
const lights = document.querySelector('my-lights') as Props
lights.on = [true, false, true]
opener.addEventListener('toggle', () => {
  opener.open = !opener.open
  lights.connected = opener.open
})

// For the tests, which define components of their own.
Object.assign(window, { mumu: { Mumu, mumuElement, mumuView } })
