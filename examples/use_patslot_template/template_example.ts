import { patslot } from 'mumulib'

window.onload = async () => {
  const template = new patslot.Template('template.html')
  const node = await template.clone_pat('person', {
    name: 'Jane Smith',
    age: 12,
    color: 'color: blue',
  })

  document.body.appendChild(node)
}
