from collections import namedtuple
from functools import partial


# "types" for flag values.
def string(items):
    if len(items) > 1:
        raise ValueError(f'invalid flag format')
    return items[0]


def integer(items):
    return int(string(items), 0)


def whitelisted_string(whitelist, items):
    result = string(items)
    if result not in whitelist:
        raise ValueError(f'value must be one of {whitelist}')
    return result


def one_of(*values):
    return partial(whitelisted_string, values)


def positive_integer(items):
    result = integer(items)
    if result < 1:
        raise ValueError(f'value cannot be negative or zero')
    return result


def boolean(items):
    text = string(items)
    if text.lower() == 'true':
        return True
    if text.lower() == 'false':
        return False
    return bool(int(text, 0))


def base(items):
    text = string(items)
    try:
        return {'2': bin, '8': oct, '10': str, '16': hex}[text]
    except KeyError:
        raise ValueError(
            "invalid base setting (must be one of '2', '8', '10' or '16')"
        )


def normalize_flag(token):
    name, *items = [x.strip() for x in token.split(':')]
    if not items: # Shortcut for boolean flags.
        return name, ['True']
    return name, items


def set_unique(d, key, value, msg):
    if key not in d:
        d[key] = value
    elif d[key] != value:
        raise ValueError(msg)


def parameters(whitelist, tokens):
    result = {}
    specified = set()
    for token in tokens:
        name, item = normalize_flag(token)
        if name in specified:
            raise ValueError(f"duplicate specification of parameter '{name}'")
        specified.add(name)
        try:
            converter = whitelist[name]
        except KeyError:
            raise ValueError(f"unrecognized parameter '{name}'")
        result[name] = converter(item)
    return result


class Arguments:
    """Represents flag arguments with potentially deferred values."""
    def __init__(self, types, defaults, tokens):
        """Constructor.
        types -> mapping of (option name)->(type checker). Acts as a whitelist.
        defaults -> mapping of (option name)->(default value).
        tokens -> raw line tokens; specify values and template deferrals.
        The `defaults` keys must be a subset of `types` keys, as must be the
        option names specified in the `tokens`. The union of `tokens` names
        and `defaults` keys must match the `types` keys.

        N.B. default values do *not* have to be of the type specified for
        explicitly-provided values!"""
        self.types = types
        self.known = defaults
        self.deferred = {}
        self._parse_flags(tokens)
        self._consistency_check()


    def _consistency_check(self):
        requested = set(self.deferred.keys()) | set(self.known.keys())
        whitelist = set(self.types.keys())
        missing = whitelist - requested
        extra = requested - whitelist
        msg = []
        if missing:
            msg.append(f'missing arguments: {missing}')
        if extra:
            msg.append(f'unrecognized arguments: {extra}')
        if msg:
            raise ValueError(' '.join(msg))


    def _parse_flags(self, tokens):
        specified = set()
        for token in tokens:
            name, items = normalize_flag(token)
            if name in specified:
                raise ValueError(
                    f"duplicate specification of argument '{name}'"
                )
            assert items
            if len(items) > 1:
                raise ValueError(
                    f"argument '{name}' can't be multiple-valued"
                )
            specified.add(name)
            item = items[0]
            if item.startswith('<'):
                self._add_parameter(name, item)
            else:
                self.known[name] = self.types[name](items)


    def _add_parameter(self, name, item):
        if not item.endswith('>'):
            raise ValueError(f"invalid flag format for argument '{name}'")
        parameter, equals, default = item[1:-1].partition('=')
        if equals: # Override original default, if any.
            self.known[name] = default
        self.deferred[name] = parameter


    def add_requests(self, deferral):
        """Add to `deferral` all the expected parameter template names
        for this Arguments object (even if there is a default value).
        This will be used later to build a parameters dict."""
        for name, deferred_name in self.deferred.items():
            if deferred_name not in deferral:
                deferral[deferred_name] = self.types[name]
            elif deferral[deferred_name] != self.types[name]:
                raise ValueError(
                    f"conflicting types for '{parameter}' parameter"
                )


    def evaluate(self, parameters):
        result = self.known.copy()
        missing = set()
        for name, parameter in self.deferred.items():
            try:
                # The Parameters object will apply type conversion.
                result[name] = parameters[parameter]
            except KeyError:
                if name not in result:
                    missing.add(parameter)
        if missing:
            raise ValueError(f'missing parameters: {missing}')
        assert set(result.keys()) == set(self.types.keys())
        return result
