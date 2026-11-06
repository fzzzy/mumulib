# mumulib/node

In Node, import `mumulib/node`: the library, with a DOM made first by
[domino](https://github.com/fgnass/domino) -- `document`, and the element
classes mumulib needs, set on `globalThis`. A DOM already there, such as
jsdom's, is left alone.

```js
import { state, patslot } from 'mumulib/node'
// or
const { state, patslot } = require('mumulib/node')
```

`mumulib` itself sets nothing on import. Where you have a DOM of your own,
import it instead; with none, it cannot load, as it reads `document` as it
does.
