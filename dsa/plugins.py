from .errors import wrap as wrap_errors, UserError
from .ui.tracing import trace
from importlib.util import spec_from_file_location, module_from_spec
import os


# Common code for loading plugins.
class AttrError(UserError):
    @classmethod
    def get(cls, obj, attr):
        try:
            return getattr(obj, attr)
        except AttributeError:
            raise cls(name=obj.__name__, attr=attr)


class MISSING_CLASS(AttrError):
    """`{name}` module doesn't define a `{attr}` class"""


class MISSING_FUNCTION(AttrError):
    """`{name}` module doesn't define a `{attr}` function (or other callable)"""


class MISSING_METHOD(AttrError):
    """`{name}` class doesn't define a `{attr}` method"""


class MISSING_PROPERTY(AttrError):
    """`{name}` class doesn't define a `{attr}` property"""


def _module_from_path(path):
    trace(f"Loading: File '{path}'")
    folder, filename = os.path.split(path)
    basename, extension = os.path.splitext(filename)
    spec = spec_from_file_location(basename, path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.__name__ == basename
    return module


def _class_from(module, class_name, method_names, property_names):
    cls = MISSING_CLASS.get(module, class_name)
    MISSING_CLASS.require(
        isinstance(cls, type), name=module.__name__, attr=class_name
    )
    for method_name in method_names:
        method = MISSING_METHOD.get(cls, method_name)
        MISSING_METHOD.require(
            callable(method), name=class_name, attr=method_name
        )
    for property_name in property_names:
        method = MISSING_PROPERTY.get(cls, property_name)
        MISSING_PROPERTY.require(
            isinstance(method, property), name=class_name, attr=property_name
        )
    return cls


def _function_from(module, name):
    func = MISSING_FUNCTION.get(module, name)
    MISSING_FUNCTION.require(
        callable(func), name=module.__name__, attr=name
    )
    return func


def _load_plugin(path, function_names, class_specs):
    module = _module_from_path(path)
    return module.__name__, tuple(
        _function_from(module, name) for name in function_names
    ) + tuple(
        _class_from(module, *spec) for spec in class_specs
    )


def load_plugins(paths, *specs):
    function_names = tuple(spec for spec in specs if isinstance(spec, str))
    class_specs = tuple(spec for spec in specs if not isinstance(spec, str))
    return dict(
        wrap_errors(
            f'File `{path}`', _load_plugin, path, function_names, class_specs
        )
        for path in paths
    )
