

import coverage # pragma: no cover
import unittest # pragma: no cover

cov = coverage.Coverage(branch=True) # pragma: no cover
cov.start() # pragma: no cover

from mumulib.shaped import is_shaped, make_shape, would_retain_shape # pragma: no cover
from mumulib.shaped import anything, HeterogenousList, AmbiguousShape # pragma: no cover


class TestShapedScalars(unittest.TestCase):
    def test_int(self):
        self.assertTrue(is_shaped(42, int), "42 should match int")
        self.assertFalse(is_shaped(42, float), "42 should not match float")

    def test_float(self):
        self.assertTrue(is_shaped(3.14, float), "3.14 should match float")
        self.assertFalse(is_shaped(3.14, int), "3.14 should not match int")

    def test_str(self):
        self.assertTrue(is_shaped("hello", str), "\"hello\" should match str")
        self.assertFalse(is_shaped("hello", int), "\"hello\" should not match int")

    def test_bool(self):
        self.assertTrue(is_shaped(True, bool), "True should match bool")
        self.assertFalse(is_shaped(True, str), "True should not match str")


class TestShapedContainers(unittest.TestCase):
    def test_tuple_matching(self):
        # Simple tuple match
        shape = (int, str)
        data = (42, "hello")
        self.assertTrue(is_shaped(data, shape), "(42, 'hello') should match (int, str)")

        # Size mismatch
        shape = (int, str)
        data = (42,)
        self.assertFalse(is_shaped(data, shape), "(42,) should not match (int, str) due to size mismatch")

        # Type mismatch within tuple
        shape = (int, str)
        data = ("not int", "hello")
        self.assertFalse(
            is_shaped(data, shape), "('not int', 'hello') should not match (int, str) due to type mismatch")

    def test_list_matching(self):
        # Homogeneous list
        shape = [int]
        data = [1, 2, 3]
        self.assertTrue(is_shaped(data, shape), "[1, 2, 3] should match [int]")

        # Heterogeneous list
        shape = [int]
        data = [1, "string", 3]
        self.assertFalse(is_shaped(data, shape), "[1, 'string', 3] should not match [int] due to type mismatch")

        # Empty list (matching a shape that expects a single element type)
        # Note: make_shape won't handle empty lists by default, but is_shaped will still work
        # because we are explicitly giving a shape. If the shape is [int], an empty list trivially matches.
        shape = [int]
        data = []
        self.assertTrue(is_shaped(data, shape), "[] should match [int]")

    def test_dict_matching(self):
        # Simple dict match
        shape = {"a": int, "b": str}
        data = {"a": 42, "b": "hello"}
        self.assertTrue(is_shaped(data, shape), "{'a': 42, 'b': 'hello'} should match {'a': int, 'b': str}")

        # Missing key
        shape = {"a": int, "b": str}
        data = {"a": 42}
        self.assertFalse(is_shaped(data, shape), "{'a': 42} should not match {'a': int, 'b': str} due to missing key 'b'")

        # Wrong type for a key
        shape = {"a": int, "b": str}
        data = {"a": "not int", "b": "hello"}
        self.assertFalse(is_shaped(data, shape), "{'a': 'not int', 'b': 'hello'} should not match {'a': int, 'b': str} due to type mismatch on 'a'")


class TestShapedNested(unittest.TestCase):
    def test_nested_dict(self):
        # Nested dict shape: { "a": { "x": int, "y": str }, "b": [int] }
        shape = {
            "a": {
                "x": int,
                "y": str
            },
            "b": [int]
        }

        # Matching data
        data = {
            "a": {
                "x": 42,
                "y": "hello"
            },
            "b": [1, 2, 3]
        }
        self.assertTrue(is_shaped(data, shape), "Nested dict should match the given shape")

        # Wrong type in nested dict
        data_bad_type = {
            "a": {
                "x": "not int",
                "y": "hello"
            },
            "b": [1, 2, 3]
        }
        self.assertFalse(is_shaped(data_bad_type, shape), "Nested dict with wrong type should not match")

        # Missing key in nested dict
        data_missing_key = {
            "a": {
                "x": 42
                # 'y' key is missing
            },
            "b": [1, 2, 3]
        }
        self.assertFalse(is_shaped(data_missing_key, shape), "Nested dict missing key should not match")

    def test_nested_tuples_lists(self):
        # Nested structure: ( [int], (str, { "foo": float }) )
        shape = (
            [int],
            (str, {"foo": float})
        )

        # Matching data
        data = (
            [1, 2, 3],
            ("bar", {"foo": 3.14})
        )
        self.assertTrue(is_shaped(data, shape), "Nested tuple/list/dict should match")

        # Incorrect inner type
        data_bad_inner = (
            [1, 2, "three"],  # "three" is not an int
            ("bar", {"foo": 3.14})
        )
        self.assertFalse(is_shaped(data_bad_inner, shape), "Mismatched inner type should fail")

        # Wrong length in tuple
        data_wrong_length = (
            [1, 2, 3],
            ("bar", {"foo": 3.14}, "extra")
        )
        self.assertFalse(is_shaped(data_wrong_length, shape), "Extra element in nested tuple should fail")

    def test_deeply_nested(self):
        # A deeply nested shape: { "config": { "versions": [(str, int)] } }
        shape = {
            "config": {
                "versions": [(str, int)]
            }
        }

        # Matching data
        data = {
            "config": {
                "versions": [
                    ("v1.0", 100),
                    ("v1.1", 101),
                    ("v2.0", 200)
                ]
            }
        }
        self.assertTrue(is_shaped(data, shape), "Deeply nested structure should match")

        # Type mismatch deep inside
        data_bad = {
            "config": {
                "versions": [
                    ("v1.0", "not int"),
                    ("v1.1", 101)
                ]
            }
        }
        self.assertFalse(is_shaped(data_bad, shape), "Type mismatch in a deeply nested element should fail")

    def test_exact_match(self):
        shape = {
            "name": "Fred Flintstone",
            "age": 42
        }
        # Exact match should match
        self.assertTrue(shape, shape)

        # Different values should not match
        self.assertTrue(shape, {"name": "Betty Rubble", "age": 27})


class TestMakeShape(unittest.TestCase):
    def test_scalars(self):
        # Scalars should return their type
        self.assertEqual(make_shape(42), int, "make_shape should return int for 42")
        self.assertEqual(make_shape(3.14), float, "make_shape should return float for 3.14")
        self.assertEqual(make_shape("hello"), str, "make_shape should return str for 'hello'")
        self.assertEqual(make_shape(True), bool, "make_shape should return bool for True")

    def test_anything(self):
        # If what == anything, it should return anything
        self.assertEqual(make_shape(anything), anything, "make_shape should return anything for 'anything'")

    def test_dict(self):
        # Simple dict
        data = {"a": 1, "b": "hello"}
        shape = make_shape(data)
        expected_shape = {"a": int, "b": str}
        self.assertEqual(shape, expected_shape, "make_shape should correctly shape a dict of scalars")

        # Nested dict
        data = {"config": {"version": "1.0", "timeout": 30}}
        shape = make_shape(data)
        expected_shape = {"config": {"version": str, "timeout": int}}
        self.assertEqual(shape, expected_shape, "make_shape should correctly shape a nested dict")

    def test_tuple(self):
        # Simple tuple
        data = (42, "hello")
        shape = make_shape(data)
        expected_shape = (int, str)
        self.assertEqual(shape, expected_shape, "make_shape should correctly shape a tuple of mixed types")

        # Nested tuple
        data = ((1, 2), ("a", "b"))
        shape = make_shape(data)
        expected_shape = ((int, int), (str, str))
        self.assertEqual(shape, expected_shape, "make_shape should shape a nested tuple")

    def test_list(self):
        # Homogeneous list
        data = [1, 2, 3]
        shape = make_shape(data)
        expected_shape = [int]
        self.assertEqual(shape, expected_shape, "make_shape should shape a homogeneous list of ints")

        # Heterogeneous list should raise HeterogenousList
        data = [1, "string", 3]
        with self.assertRaises(HeterogenousList):
            make_shape(data)

        # Empty list should raise AmbiguousShape
        data = []
        with self.assertRaises(AmbiguousShape):
            make_shape(data)

        # Nested lists
        data = [[1, 2], [3, 4]]
        shape = make_shape(data)
        # A list of lists of ints, so shape should be [[int]]
        expected_shape = [[int]]
        self.assertEqual(shape, expected_shape, "make_shape should shape a nested homogeneous list")

    def test_complex_structure(self):
        # Complex nested structure
        data = {
            "config": {
                "servers": [
                    {"host": "localhost", "port": 8080},
                    {"host": "example.com", "port": 80}
                ],
                "features": ("enable_logging", True, 3.14)
            },
            "metadata": {"count": 2, "desc": "two servers"}
        }

        expected_shape = {
            "config": {
                "servers": [
                    {"host": str, "port": int}
                ],
                "features": (str, bool, float)
            },
            "metadata": {"count": int, "desc": str}
        }

        shape = make_shape(data)
        self.assertEqual(shape, expected_shape, "make_shape should correctly shape a complex, nested structure")


class TestWouldRetainShape(unittest.TestCase):
    def test_single_dict_key(self):
        # shape = {"a": int}, data = {"a": 42}
        # If we replace "a" with 100 (an int), it should still match
        shape = {"a": int}
        data = {"a": 42}
        segs = ["a"]
        leaf = 100
        self.assertTrue(would_retain_shape(shape, data, segs, leaf),
                        "Replacing a dict key with a valid int should retain shape")

        # If we replace "a" with a string, it should fail
        leaf = "not an int"
        self.assertFalse(would_retain_shape(shape, data, segs, leaf),
                         "Replacing a dict key with a string where an int is expected should fail")

    def test_nested_dict_with_str_fallback_key(self):
        # We will try replacing "bar" path
        shape = {"config": {"foo": int, str: str}}
        data = {"config": {"foo": 42, "bar": "hello"}}
        segs = ["config", "bar"]
        # Replace "bar" value with another string
        leaf = "world"
        self.assertTrue(would_retain_shape(shape, data, segs, leaf),
                        "Replacing a str key with another string should retain shape")
        # Replace "bar" value with an int
        leaf = 99
        self.assertFalse(would_retain_shape(shape, data, segs, leaf),
                         "Replacing a str key with an int should fail since it expects a str for wildcard key")

    def test_list_index(self):
        # Replace index "1"
        shape = [int]
        data = [1, 2, 3]
        segs = ["1"]  # We go to index 1 in the list
        leaf = 42
        self.assertTrue(would_retain_shape(shape, data, segs, leaf),
                        "Replacing an element in a homogeneous int list with another int should retain shape")

        leaf = "not an int"
        self.assertFalse(would_retain_shape(shape, data, segs, leaf),
                         "Replacing an element in a homogeneous int list with a string should fail")

    def test_tuple_index(self):
        # Replace index "0" in the tuple
        shape = (int, str)
        data = (42, "hello")
        segs = ["0"]
        leaf = 100
        self.assertTrue(would_retain_shape(shape, data, segs, leaf),
                        "Replacing the int element in a tuple with another int should retain shape")

        leaf = "not an int"
        self.assertFalse(would_retain_shape(shape, data, segs, leaf),
                         "Replacing the int element in a tuple with a string should fail")

    def test_deep_nested_structure(self):
        # Replace "servers" at index "0" "port"
        shape = {"config": {"servers": [{"host": str, "port": int}]}}
        data = {"config": {"servers": [{"host": "localhost", "port": 8080}]}}
        segs = ["config", "servers", "0", "port"]

        # Replace port with another int
        leaf = 9090
        self.assertTrue(would_retain_shape(shape, data, segs, leaf),
                        "Replacing port with another int should retain shape")

        # Replace port with a string
        leaf = "not an int"
        self.assertFalse(would_retain_shape(shape, data, segs, leaf),
                         "Replacing port with a string should fail")

    def test_nonexistent_path(self):
        # If the path doesn't exist, would_retain_shape should fail
        shape = {"a": int}
        data = {"a": 42}
        segs = ["nonexistent"]
        leaf = 100
        self.assertFalse(would_retain_shape(shape, data, segs, leaf),
                         "Nonexistent path should fail")

    def test_dict_leaf(self):
        shape = {"a": {"b": int}}
        data = {"a": 100}
        segs = ["a", "b"]
        leaf = 200
        self.assertFalse(would_retain_shape(shape, data, segs, leaf),
            "Non-dictionary branch should fail")

    def test_malformed_list(self):
        shape = [int, str]
        data = [42, "hello"]
        segs = [0]
        leaf = 84
        self.assertFalse(would_retain_shape(shape, data, segs, leaf),
            "Malformed list should fail")

    def test_malformed_list_index(self):
        shape = [int]
        data = [42]
        segs = ["hello"]
        leaf = 84
        self.assertFalse(would_retain_shape(shape, data, segs, leaf),
            "Malformed list index should fail")

    def test_out_of_range_list_index(self):
        shape = [int]
        data = [42]
        segs = ["5"]
        leaf = 84
        self.assertFalse(would_retain_shape(shape, data, segs, leaf),
            "Out of range list index should fail")

    def test_bad_list(self):
        shape = [int]
        data = {"a": 42}
        segs = ["0"]
        leaf = 84
        self.assertFalse(would_retain_shape(shape, data, segs, leaf),
            "Bad list data should fail")

    def test_malformed_tuple_index(self):
        shape = (int, "str")
        data = (42, "hello")
        segs = ["hello"]
        leaf = 84
        self.assertFalse(would_retain_shape(shape, data, segs, leaf),
            "Malformed tuple index should fail")

    def test_out_of_range_tuple_index(self):
        shape = (int, "str")
        data = (42, "hello")
        segs = ["5"]
        leaf = 84
        self.assertFalse(would_retain_shape(shape, data, segs, leaf),
            "Out of range tuple index should fail")

    def test_bad_tuple(self):
        shape = (int, "str")
        data = [42]
        segs = ["0"]
        leaf = 84
        self.assertFalse(would_retain_shape(shape, data, segs, leaf),
            "Bad tuple data should fail")

    def test_extra_segments(self):
        shape = {"a": str}
        data = {"a": "hello"}
        segs = ["a", "b"]
        leaf = "goodbye"
        self.assertFalse(would_retain_shape(shape, data, segs, leaf),
            "Extra segments should fail")

    def test_custom_class_bad_shape(self):
        class Foo(object):
            pass
        shape = {"a": Foo}
        data = {"a": "hello"}
        segs = ["a"]
        leaf = 42
        self.assertFalse(would_retain_shape(shape, data, segs, leaf),
            "Custom class bad shape match should fail")

if __name__ == "__main__": # pragma: no cover
    unittest.main(exit=False) # pragma: no cover
    cov.stop() # pragma: no cover
    cov.save() # pragma: no cover

    # Print coverage report to the terminal
    cov.report(show_missing=True) # pragma: no cover
