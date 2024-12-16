"""\
@file shaped.py
@author Donovan Preston

Copyright (c) 2007, Linden Research, Inc.
Copyright (c) 2024, Donovan Preston

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""


import traceback


CONTAINER_TYPES = [dict, list, tuple]
SCALAR_TYPES = [int, float, str, bool]


class ShapeMismatch(Exception):
    pass


class TypeMismatch(ShapeMismatch):
    pass


class KeyMismatch(ShapeMismatch):
    pass


class SizeMismatch(ShapeMismatch):
    pass


class PredicateMismatch(ShapeMismatch):
    pass


def is_shaped(thing, shape):
    """Check if `thing` matches the given `shape` without raising exceptions.

    This function validates that `thing` has the structure and types defined
    by `shape`. If `thing` is shaped correctly, it returns True. If not, it
    returns False.

    Returns:
        bool: True if `thing` conforms to `shape`, False otherwise.
    """
    try:
        _is_shaped_exc(thing, shape)
        return True
    except ShapeMismatch:
        return False


def _is_shaped_exc(thing, shape):
    if type(shape) in CONTAINER_TYPES:
        shape_type = type(shape)

        if shape_type is dict:
            for name in shape:
                if name not in thing:
                    raise KeyMismatch(
                        "key %r (for shape %s) was not in dict (%s)" % (
                            name, shape, thing))
                subitem = thing[name]
                subtype = shape[name]
                _is_shaped_exc(subitem, subtype)
        elif shape_type is list:
            subtype = shape[0]
            for subitem in thing:
                _is_shaped_exc(subitem, subtype)
        elif shape_type is tuple:
            if len(thing) != len(shape):
                raise SizeMismatch(
                    "wrong number of items in %s (for shape %s); "
                    "expected %s items" % (
                    thing, shape, len(shape)))

            subitem_iter = iter(thing)
            for subtype in shape:
                subitem = next(subitem_iter)
                _is_shaped_exc(subitem, subtype)
            return
        return # pragma: no cover
    elif shape in SCALAR_TYPES:
        if type(thing) is not shape:
            raise TypeMismatch(
                "wrong type for shape %s: %s" % (
                    shape, thing))
        return
    raise TypeMismatch( #TODO
        "wrong type for shape %s: %s" % (
            shape, thing))


class MalformedShape(Exception):
    pass


class AmbiguousShape(MalformedShape):
    pass


class HeterogenousList(MalformedShape):
    pass


def make_shape(what):
    """Infer a shape definition from the given object.

    This function inspects `what` and constructs a shape that represents
    its structure and types. For dictionaries, a shape is a dict of shapes
    for each value. For tuples, a shape is a tuple of shapes for each element.
    For lists, this function assumes homogeneity: all elements must be of the
    same type. If that assumption is violated, a HeterogenousList exception
    is raised. If the list is empty, an AmbiguousShape exception is raised.
    For any other object, the shape is simply its type.

    Args:
        what: The object from which to infer a shape.

    Returns:
        dict | list | tuple | type: A shape structure corresponding to `what`.
    """
    if what == anything:
        return anything
    what_type = type(what)
    if what_type is dict:
        shape = {}
        for key, value in what.items():
            shape[key] = make_shape(value)
        return shape
    elif what_type is list:
        if not len(what):
            raise AmbiguousShape(
                "Shape of item with list of zero elements "
                "cannot be determined")
        subtype = type(what[0])
        for subitem in what[1:]:
            if type(subitem) is not subtype:
                raise HeterogenousList(
                    "List items must be of homogenous type.")
        return [make_shape(what[0])]
    elif what_type is tuple:
        return tuple(map(make_shape, what))
    else:
        return type(what)


def anything(item):
    raise NotImplementedError # pragma: no cover


def _would_retain_shape_exc(shape, data, segs, leaf):
    # If no more segments, we should validate leaf against shape
    if not segs:
        _is_shaped_exc(leaf, shape)
        return

    seg = segs[0]

    # Navigate based on shape type
    if isinstance(shape, dict):
        # If seg matches a key in shape, use that subtype
        # If not, but str is a key in shape, treat it as a fallback wildcard
        if seg in shape:
            subshape = shape[seg]
        elif str in shape:
            subshape = shape[str]
        else:
            raise KeyMismatch(f"Segment '{seg}' not found in shape and no fallback available.")

        # Navigate data as a dict
        if isinstance(data, dict):
            subdata = data.get(seg, '')
        else:
            # The shape expects a dict-like structure, but data is not a dict
            raise ShapeMismatch(f"Expected dict-like data at segment '{seg}', got {type(data)}")

        _would_retain_shape_exc(subshape, subdata, segs[1:], leaf)

    elif isinstance(shape, list):
        # Expect a single-element shape list
        if len(shape) != 1:
            raise MalformedShape("List shape must have exactly one element.")
        subshape = shape[0]

        # seg should be an index
        try:
            index = int(seg)
        except ValueError:
            raise ShapeMismatch(f"Segment '{seg}' is not a valid list index.")

        if isinstance(data, list):
            if len(data) > index:
                subdata = data[index]
            else:
                raise ShapeMismatch(f"List index out of range: {index} ({data})")
        else:
            raise ShapeMismatch(f"Subdata is not a list: {data}")

        _would_retain_shape_exc(subshape, subdata, segs[1:], leaf)

    elif isinstance(shape, tuple):
        # seg should be an index
        try:
            index = int(seg)
        except ValueError:
            raise ShapeMismatch(f"Segment '{seg}' is not a valid tuple index.")

        if isinstance(data, tuple):
            if len(data) > index and index >= 0:
                subdata = data[index]
            else:
                raise SizeMismatch(f"Tuple index out of range: {index} ({data})")
        else:
            raise ShapeMismatch(f"Data is not a tuple: {data}")

        # The shape should have a corresponding subtype
        subshape = shape[index]

        _would_retain_shape_exc(subshape, subdata, segs[1:], leaf)
    else:
        # If we reached a scalar or exact-match shape but still have segments,
        # it means the data is deeper than the shape. This should fail.
        raise ShapeMismatch(f"Extra segments {segs} not supported by shape {shape}") # TODO

def would_retain_shape(shape, data, segs, leaf, debug=False):
    """
    Check if inserting `leaf` at the path described by `segs` in `data` would still
    produce a structure matching `shape`.

    This function navigates `data` following the path segments in `segs`. If `shape`
    is a dict, `str` keys in `shape` act as a wildcard fallback if the exact segment
    key is not found. If any mismatch occurs, it returns False. If `debug` is True,
    it prints a traceback before returning.

    Args:
        shape: The shape definition to validate against.
        data: The data structure to inspect.
        segs (list[str]): The path segments to navigate into `data`.
        leaf: The value to hypothetically insert at the end of that path.
        debug (bool): If True, prints a traceback on exception.

    Returns:
        bool: True if substituting `leaf` would preserve `shape`, False otherwise.
    """
    try:
        _would_retain_shape_exc(shape, data, segs, leaf)
    except Exception as e:
        if debug:
            traceback.print_exc() # pragma: no cover
        return False
    return True

