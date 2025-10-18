from _typeshed import Incomplete
from mumulib import producers as producers
from typing import Any, AsyncIterator, IO

VOID_ELEMENTS: list[str]
VOID_ELEMENTS_SET: set[str]
MAIN_ROOT: list[str]
DOCUMENT_METADATA: list[str]
SECTIONING_ROOT: list[str]
CONTENT_SECTIONING: list[str]
TEXT_CONTENT: list[str]
INLINE_TEXT_SEMANTICS: list[str]
IMAGE_AND_MULTIMEDIA: list[str]
EMBEDDED_CONTENT: list[str]
SVG_AND_MATHML: list[str]
SCRIPTING: list[str]
DEMARCATING_EDITS: list[str]
TABLE_CONTENT: list[str]
FORMS: list[str]
INTERACTIVE_ELEMENTS: list[str]
WEB_COMPONENTS: list[str]
ALL_ELEMENTS: list[str]

def reindent_tree(node: Stan, indent: int) -> None: ...

class Stan:
    clone: bool
    tagname: str
    indent: int
    attributes: dict[str, Any]
    children: list[Any]
    def __init__(self, tagname: str, indent: int, *args: Any, **kwargs: Any) -> None: ...
    def __call__(self, **kwargs: Any) -> Stan: ...
    def __getitem__(self, item: Any) -> Stan: ...
    def copy(self) -> Stan: ...
    def clone_pat(self, patname: str, **slots: Any) -> Stan | None: ...
    def clear_slots(self, slotname: str) -> None: ...
    def fill_slots(self, slotname: str, value: Any) -> None: ...
    def append_slots(self, slotname: str, value: Any) -> None: ...

class TagGroup:
    def __init__(self, *tags: str) -> None: ...

main_root: Incomplete
document_metadata: Incomplete
sectioning_root: Incomplete
content_sectioning: Incomplete
text_content: Incomplete
inline_text_semantics: Incomplete
image_and_multimedia: Incomplete
embedded_content: Incomplete
svg_and_mathml: Incomplete
scripting: Incomplete
demarcating_edits: Incomplete
table_content: Incomplete
forms: Incomplete
interactive_elements: Incomplete
web_components: Incomplete
all: Incomplete

def parse_template(source: IO[bytes]) -> Stan | None: ...

class Template:
    filename: str
    loaded: bool
    template: Stan | None
    root: Stan | None
    def __init__(self, filename: str) -> None: ...
    def load(self) -> Template: ...
    def clone_pat(self, patname: str, **slots: Any) -> Stan: ...
    def fill_slots(self, slotname: str, value: Any) -> None: ...
    def clear_slots(self, slotname: str) -> None: ...
    def append_slots(self, slotname: str, value: Any) -> None: ...

def clear_slots(node: Stan, slotname: str) -> None: ...
def fill_slots(node: Stan, slotname: str, value: Any) -> None: ...
def append_slots(node: Stan, slotname: str, value: Any) -> None: ...
async def produce_html(thing: Stan, state: Any) -> AsyncIterator[str]: ...
