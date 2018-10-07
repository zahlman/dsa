from parse_config import parts_of
import binascii
from functools import partial


def parameters(whitelist, tokens):
    result = {}
    specified = set()
    for token in tokens:
        name, item = parts_of(token, ':', 1, 2, True)
        if not item: # Shortcut for boolean flags
            item = ['True']
        if name in specified:
            raise ValueError(f"duplicate specification of parameter '{name}'")
        specified.add(name)
        try:
            converter = whitelist[name]
        except KeyError:
            raise ValueError(f"unrecognized parameter '{name}'")
        result[name] = converter(item)
    return result


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


def hexdump(items):
    text = string(items)
    try:
        return binascii.unhexlify(''.join(text.split()))
    except binascii.Error:
        raise ValueError(f'invalid terminator format')
