"""The TypeScript library in a page, served by Python: no bundler, no npm.

    make dist, then make server SERVER=browser

Every app serves the library's browser build at /mumulib/browser/: ES
modules, copied into the Python package by make dist and shipped in its
wheel, so the client is always of the server's own version. A page imports
it as any module, by URL, from a script of its own:

    GET    /                                  the page
    GET    /mumulib/browser/mumulib.mjs       App, mountApp, and the rest
    GET    /mumulib/browser/app.mjs           ...and the modules it imports

The page is the binding example: an App whose state is the input's, named
this.name, and whose getter fills the greeting's slot.
"""

from mumulib import consumers, server, tags

PAGE = tags.Markup("""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>No bundler</title>
<script type="module">
import { App, mountApp } from "/mumulib/browser/mumulib.mjs";

class Page extends App {
  static state = { name: "" };

  get greeting() {
    return this.state.name || "world";
  }
}

mountApp(Page);
</script>
</head>
<body>
<input name="this.name" placeholder="Your name" />
<p>Hello, <span data-slot="greeting">world</span></p>
</body>
</html>
""")

app = server.consumers_app(consumers.GetOnly({"index": PAGE}))
