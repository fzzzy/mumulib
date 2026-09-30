"""The public API, written down: what each module's __all__ promises.

A name added to or dropped from an __all__ changes what mumulib promises to
keep working, so it has to change here too, on purpose.
"""

import builtins
import importlib
import unittest

PUBLIC = {
    "mumutypes": {
        "Message",
        "Scope",
        "Receive",
        "Send",
        "ASGIApp",
        "State",
        "Writer",
        "Chunk",
        "Consumer",
        "Producer",
        "SpecialResponse",
        "HTTPResponse",
        "BadRequestResponse",
        "NotFoundResponse",
        "MethodNotAllowedResponse",
        "CreatedResponse",
        "SeeOtherResponse",
        "CONTENT_TYPES",
        "content_type_for",
    },
    "server": {"consumers_app", "EventSource"},
    "consumers": {"consume", "add_consumer"},
    "producers": {"produce", "add_producer"},
    "shaped": {
        "is_shaped",
        "make_shape",
        "would_retain_shape",
        "anything",
        "ShapeMismatch",
        "TypeMismatch",
        "KeyMismatch",
        "SizeMismatch",
        "PredicateMismatch",
        "MalformedShape",
        "AmbiguousShape",
        "HeterogenousList",
    },
    "tags": {
        "Stan",
        "Template",
        "parse_template",
        "fill_slots",
        "clear_slots",
        "append_slots",
        "produce_html",
        "main_root",
        "document_metadata",
        "sectioning_root",
        "content_sectioning",
        "text_content",
        "inline_text_semantics",
        "image_and_multimedia",
        "embedded_content",
        "svg_and_mathml",
        "scripting",
        "demarcating_edits",
        "table_content",
        "forms",
        "interactive_elements",
        "web_components",
        "every",
    },
}


class TestPublicApi(unittest.TestCase):
    def test_each_module_declares_what_is_written_here(self):
        for name, expected in PUBLIC.items():
            module = importlib.import_module(f"mumulib.{name}")
            with self.subTest(module=name):
                self.assertEqual(set(module.__all__), expected)
                self.assertEqual(len(module.__all__), len(expected), "a duplicate")

    def test_every_declared_name_exists(self):
        for name in PUBLIC:
            module = importlib.import_module(f"mumulib.{name}")
            for attr in module.__all__:
                with self.subTest(name=f"{name}.{attr}"):
                    self.assertTrue(hasattr(module, attr))

    def test_import_star_shadows_no_builtin(self):
        for name in PUBLIC:
            module = importlib.import_module(f"mumulib.{name}")
            with self.subTest(module=name):
                self.assertEqual(set(module.__all__) & set(dir(builtins)), set())
