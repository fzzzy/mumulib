# A typed request

Status: open. Deferred to this doc from a code review, 2026-10-03.

The review asked for a typed `Request` to be passed instead of
`dict[str, Any]`. It has been resisted for a long time over one question:
whether there is a common request object that could be reused, without
dragging in a lot of dependencies.

## What the code does now

Consumers, producers, functions in the tree and a `Resource`'s handlers are
all given `mumutypes.State`, which is `dict[str, Any]`. A handler calls it
`request`; the rest of the code calls it `state`. It holds two kinds of
thing.

What the request said, as `consumers_app` reads it:

- `"method"` -- a `HEAD` is `"GET"` here, as it is answered as one;
- `"url"` -- the path, as the server decoded it;
- `"extension"`, `"content_type"` and `"accept"` -- the type the URL names;
- `"parsed_body"` -- the body, by its `Content-Type`: JSON, a form, or
  multipart, its files as `mumutypes.Upload`.

What mumulib works out while answering, and passes along in the same dict:

- `"segments"` -- the path's segments, from which what was walked to reach
  an object is worked out, and its URL;
- `"container"` -- the nearest resource written to, for the change stream;
- `"data"`, `"vite"` and `"development"` -- the app's own settings;
- `"etag_file"` and `"fragment"` -- set on the way down, for a producer
  further on.

The ASGI scope itself, its headers among them, is not in it.

## Candidates for reuse

What each would bring, as of 2026-10-03:

- **Starlette's `Request`** (1.7.0) -- an object over an ASGI scope and
  `receive`: headers, query, cookies, the body. It depends on `anyio`.
- **`asgiref.typing`** (3.12.1) -- `TypedDict`s for the ASGI scope and
  messages, `HTTPScope` among them; types, not a request object. No
  dependencies on Python 3.14.
- **Werkzeug's `Request`** (3.1.9) -- a WSGI request, made from a WSGI
  environ rather than an ASGI scope. It depends on `markupsafe`.
- **None** -- a `TypedDict` or a dataclass of mumulib's own, which costs no
  dependency.

## To decide

- Whether to type the request at all.
- If so, whether to reuse one of these or write mumulib's own.
