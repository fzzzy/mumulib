import Tally from './tally.sfc.html'

customElements.define('a-tally', Tally)
const tally = document.createElement('a-tally') as InstanceType<typeof Tally>
tally.count = 'many'
