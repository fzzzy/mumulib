// A character, party and deploy editor: each object shown in a table, and
// edited in a dialog. The data is the Python server's, py/examples/editors.py,
// which Vite passes /editors on to.
//
// The state holds each object as an instance of its class below, keyed by
// its id: state.characters.c1, say. A dialog's form names the object by its
// path and the method to call, save, which PUTs the form's values to the
// object's own URL. The server then says what changed on /editors/changes.sse,
// and every page open loads it again -- this one included.
import { state, patslot, dialog } from 'mumulib'
import type { FormArgs, RenderFunc } from 'mumulib'
import MemberSelect from './member-select.sfc.html'

customElements.define('member-select', MemberSelect)

// The component's own class, which the checker gives the import
type MemberSelectElement = InstanceType<typeof MemberSelect>

const API = '/editors'

async function put(url: string, body: object) {
  const response = await fetch(url, {
    method: 'PUT',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    alert(await response.text())
  }
}

class Character {
  constructor(
    readonly id: string,
    public name: string,
    public prompt: string,
    public agent_args: string
  ) {}

  get path() {
    return `this.characters.${this.id}`
  }

  async save(args: FormArgs) {
    await put(`${API}/characters/${this.id}.json`, {
      name: args.name,
      prompt: args.prompt,
      agent_args: args.agent_args,
    })
  }
}

class Party {
  constructor(
    readonly id: string,
    public name: string,
    public members: string[]
  ) {}

  get path() {
    return `this.parties.${this.id}`
  }

  async save(args: FormArgs) {
    // members[] is always a list, and absent when none is chosen
    await put(`${API}/parties/${this.id}.json`, {
      name: args.name,
      members: args.members ?? [],
    })
  }
}

class Deploy {
  constructor(
    readonly id: string,
    public name: string,
    public party: string,
    public status: string
  ) {}

  get path() {
    return `this.deploys.${this.id}`
  }

  async save(args: FormArgs) {
    // Its status is the server's: only these two may change
    await put(`${API}/deploys/${this.id}.json`, {
      name: args.name,
      party: args.party,
    })
  }
}

type Records = { [id: string]: object }

// Each kind of object: its URL, and how a record becomes one
const KINDS = {
  characters: (id: string, r: Record<string, string>) =>
    new Character(id, r.name, r.prompt, r.agent_args),
  parties: (id: string, r: Record<string, string | string[]>) =>
    new Party(id, r.name as string, r.members as string[]),
  deploys: (id: string, r: Record<string, string>) =>
    new Deploy(id, r.name, r.party, r.status),
}
type Kind = keyof typeof KINDS

async function load(kind: Kind) {
  const records = (await (await fetch(`${API}/${kind}.json`)).json()) as Records
  const make = KINDS[kind] as (id: string, r: object) => object
  const objects = Object.fromEntries(
    Object.entries(records).map(([id, record]) => [id, make(id, record)])
  )
  await state.set_state({ [kind]: objects })
}

// state is the module; state.state the tree it keeps
const tree = state.state
const characters = () => Object.values(tree.characters ?? {}) as Character[]
const parties = () => Object.values(tree.parties ?? {}) as Party[]
const deploys = () => Object.values(tree.deploys ?? {}) as Deploy[]

const name_of = (kind: 'characters' | 'parties', id: string) =>
  (tree[kind]?.[id] as Character | Party | undefined)?.name ?? id

// The tables, from the state: each row a copy of its pattern
state.onstate(async () => {
  const table = (id: string) => document.getElementById(id) as HTMLElement
  await patslot.fill(table('characters'), {
    rows: characters().map((c) =>
      patslot.clone_pat('character_row', {
        path: c.path,
        name: c.name,
        prompt: c.prompt,
        agent_args: c.agent_args,
      })
    ),
  })
  await patslot.fill(table('parties'), {
    rows: parties().map((p) =>
      patslot.clone_pat('party_row', {
        path: p.path,
        name: p.name,
        members: p.members.map((id) => name_of('characters', id)).join(', '),
      })
    ),
  })
  await patslot.fill(table('deploys'), {
    rows: deploys().map((d) =>
      patslot.clone_pat('deploy_row', {
        path: d.path,
        name: d.name,
        party: name_of('parties', d.party),
        status: d.status,
      })
    ),
  })
})

// The dialogs, each shown with the object's values in its form. Each is
// filled in place: reset first, so nothing from the last one is left.
function form_of(el: HTMLElement, path: string) {
  const form = el.querySelector('form') as HTMLFormElement
  form.reset()
  ;(form.elements.namedItem('path') as HTMLInputElement).value = path
  return form
}

function set(form: HTMLFormElement, name: string, value: string) {
  ;(form.elements.namedItem(name) as HTMLInputElement).value = value
}

const RENDER: { [kind: string]: RenderFunc } = {
  characters(el, object) {
    const c = object as Character
    const form = form_of(el, c.path)
    set(form, 'name', c.name)
    set(form, 'prompt', c.prompt)
    set(form, 'agent_args', c.agent_args)
    return el
  },
  parties(el, object) {
    const p = object as Party
    const form = form_of(el, p.path)
    set(form, 'name', p.name)
    const members = el.querySelector('member-select') as MemberSelectElement
    members.options = characters().map((c) => ({ value: c.id, label: c.name }))
    members.value = p.members
    return el
  },
  async deploys(el, object) {
    const d = object as Deploy
    // The party choices from the party_option pattern, before any is chosen
    await patslot.fill(el, {
      party_options: parties().map((p) =>
        patslot.clone_pat('party_option', { id: p.id, label: p.name })
      ),
      status: d.status,
    })
    const form = form_of(el, d.path)
    set(form, 'name', d.name)
    set(form, 'party', d.party)
    return el
  },
}

const DIALOG: { [kind: string]: string } = {
  characters: 'character_dialog',
  parties: 'party_dialog',
  deploys: 'deploy_dialog',
}

document.addEventListener('click', (event) => {
  const target = event.target as HTMLElement
  const edit = target.closest('[data-edit]')
  if (edit) {
    event.preventDefault()
    const path = edit.getAttribute('data-edit') as string
    const kind = path.split('.')[1]
    dialog.do_dialog(DIALOG[kind], path, RENDER[kind])
  } else if (target.closest('.cancel')) {
    target.closest('dialog')?.close('cancel')
  }
})

// Whatever anyone changes, here or in another page: the server says its
// URL, /editors/characters/c1, and the kind it is of is loaded again
new EventSource(`${API}/changes.sse`).onmessage = (event) => {
  const kind = (JSON.parse(event.data) as string).split('/')[2]
  if (kind in KINDS) {
    load(kind as Kind)
  }
}

for (const kind of Object.keys(KINDS) as Kind[]) {
  load(kind)
}
