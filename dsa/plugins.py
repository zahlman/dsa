# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

from .errors import wrap as wrap_errors, UserError
from .ui.tracing import trace
from importlib.util import spec_from_file_location, module_from_spec
import os


# Common code for loading plugins.
class MISSING_ATTRIBUTE(UserError):
    """`{name}` doesn't define `{attr}`, or `{name}.{attr}` is not {desc}"""
    @classmethod
    def get(cls, obj, attr, name, desc):
        try:
            return getattr(obj, attr)
        except AttributeError:
            raise cls(name=name, desc=desc, attr=attr)


# predicates for use with testing routines.
def is_function_with(thing):
    """a function"""
    return callable(thing)


is_function = (is_function_with, {})


def is_method_with(thing):
    """a method"""
    return callable(thing)


is_method = (is_method_with, {})


def is_property_with(thing):
    """a property"""
    return isinstance(thing, property)


is_property = (is_property_with, {})


def is_integer_with(thing):
    """an integer"""
    return isinstance(thing, int)


is_integer = (is_integer_with, {})


def is_class_with(thing):
    """a class"""
    return isinstance(thing, type)


is_class = (is_class_with, {})


exists = (lambda thing: True, {})


def _test(parent, name, children):
    for (attribute_name, (predicate, grandchildren)) in children.items():
        result = MISSING_ATTRIBUTE.get(
            parent, attribute_name, name, predicate.__doc__
        )
        MISSING_ATTRIBUTE.require(
            predicate(result),
            name=name, attr=attribute_name, desc=predicate.__doc__
        )
        _test(result, f'{name}.{attribute_name}', grandchildren)


def _module_from_path(path):
    trace(f"Loading: File '{path}'")
    folder, filename = os.path.split(path)
    basename, extension = os.path.splitext(filename)
    spec = spec_from_file_location(basename, path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.__name__ == basename
    return module


def _load_plugin(path, checklist):
    module = _module_from_path(path)
    name = module.__name__
    _test(module, name, checklist)
    return name, module


def load_plugins(paths, checklist):
    return dict(
        wrap_errors(f'File `{path}`', _load_plugin, path, checklist)
        for path in paths
    )
