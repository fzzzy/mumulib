# XML

Status: design in progress. Started 2026-10-01.

An XML representation of the same objects, beside JSON and HTML, for
consumers that read it best -- language models among them.

## What the code does today

- `.xml` names `text/xml`, from Python's `mimetypes`.
- No type has an XML producer: a dict at `.xml` is not found.
- A string is text, at `.txt`, and JSON, and not found as anything else, so
  `/motto.xml` is not found.

## Decisions

### 1. XML is one more serializer

XML comes in as JSON and HTML did: a producer registered for `.xml`, chosen
by the URL's extension. Traversal, resources and persists do not change;
every object that can be JSON can be XML.

### 2. For the consumers that read it best

A language model reads XML more reliably than JSON: each value is named by
its tags at both ends, where JSON's structure is braces and commas that all
look alike, deep in a document. So an agent can ask for `.xml`, the
TypeScript client `.json` and a browser `.html`, all of the same object --
each asking by the URL's extension, as everything in mumulib does.

### 3. A convention of mumulib's own, and narrow

The XML serializer does not take on JSON-to-XML in general (JsonML,
BadgerFish, Parker, the W3C `json-to-xml` schema). It serializes the shapes
mumulib itself produces -- containers, scalars, and the tagged values links
are -- and mirrors the decisions already made for JSON: a link is a link,
not inlined.

### 4. Dictionaries only (tentative)

The XML serializer serializes dictionaries, and nothing else: a scalar at
`.xml` -- `/motto.xml` -- is not found, as anything with no producer for a
type is, as a string is at every type but `.txt` and `.json`. A serializer,
then, may take only some kinds of object.

Tentative: to be confirmed when the XML convention itself is settled.

### 5. Each key is an element's name

A dict's entry is an element named by its key, as the common JSON-to-XML
convention writes it (Python's `dicttoxml` and `xmltodict.unparse` among
others): `{"name": "Ada"}` is `<name>Ada</name>`. It is the shape a language
model reads most readily: what each value is, named at both of its ends,
rather than by a type with the name in an attribute, as the W3C XPath
`json-to-xml` form has it.

## Open questions

1. **How a link looks.** Its JSON is `{"@id": "/users/42"}`, in state sync's
   part two, which is deferred; in part one a link is a plain URL string,
   and so plain text in XML.
