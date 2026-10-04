import { test, expect } from '@playwright/test'
import { parseSfc } from './sfc.mjs'

// What the component's template and script came out as
function split(source: string) {
  const { code, script } = parseSfc(source, 'x.sfc.html')
  const inner = /template\.innerHTML = (".*");/.exec(code)
  return {
    template: inner ? JSON.parse(inner[1]) : null,
    script: script
      ? source.slice(script.start, script.start + script.length)
      : null,
  }
}

// Node alone: the parser as HTML reads a .sfc.html, its top level only
test.describe('Mumulib single-file component parsing', () => {
  test('a template inside the template is part of it', () => {
    expect(
      split(
        '<template><template id="row"><li></li></template><p>after</p></template>' +
          '<script>export default 1</script>'
      )
    ).toEqual({
      template: '<template id="row"><li></li></template><p>after</p>',
      script: 'export default 1',
    })
  })

  test("a script inside the template is the template's, not the component's", () => {
    expect(
      split(
        '<template><script>alert(1)</script><p>x</p></template><script>real()</script>'
      )
    ).toEqual({
      template: '<script>alert(1)</script><p>x</p>',
      script: 'real()',
    })
  })

  test('a comment mentioning <script> or </template> is passed over', () => {
    expect(
      split(
        '<!-- a <script> here, and a </template> --><template>' +
          '<!-- </template> --><p>x</p></template><script>real()</script>'
      )
    ).toEqual({ template: '<!-- </template> --><p>x</p>', script: 'real()' })
  })

  test('what looks like a tag in a script or an attribute is not one', () => {
    expect(
      split(
        '<template><p title="a>b</template>">x</p><style>/* </template> */</style></template>' +
          '<script lang="ts">const end = "</template>"</script>'
      )
    ).toEqual({
      template:
        '<p title="a>b</template>">x</p><style>/* </template> */</style>',
      script: 'const end = "</template>"',
    })
  })

  test('the script is found at its own place, to map back to', () => {
    const source =
      '<template>\n  <p>x</p>\n</template>\n\n<script>\nrun()\n</script>\n'
    expect(split(source).script).toBe('\nrun()\n')
  })

  test('anything else at the top level is an err, with its place', () => {
    for (const [source, message] of [
      ['<template></template>\nstray', '2:1: text outside'],
      ['<div></div>', '1:1: only a <template> and a <script>'],
      ['<script>a</script><script>b</script>', '1:19: a second <script>'],
      ['<template><template></template>', '1:11: <template> is not closed'],
      ['<script>never ends', '<script> is not closed'],
      ['<!-- never ends', 'a comment is not closed'],
      ['', 'needs a <template> or a <script>'],
    ]) {
      expect(() => parseSfc(source, 'x.sfc.html'), source).toThrow(message)
    }
  })
})
