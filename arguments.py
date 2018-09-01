from collections import namedtuple


# "types" for flag values.
def integer(text):
    return int(text, 0)


def boolean(text):
    if text.lower() == 'true':
        return True
    if text.lower() == 'false':
        return False
    return bool(int(text, 0))


def base(text):
    try:
        return {'2': bin, '8': oct, '10': str, '16': hex}[text]
    except KeyError:
        raise ValueError(
            "invalid base setting (must be one of '2', '8', '10' or '16')"
        )
    

def normalize_flag(token):
    name, *items = [x.strip() for x in token.split(':')]
    if len(items) > 1:
        raise ValueError(f"invalid flag format for flag '{name}'")
    if not items: # Shortcut for boolean flags.
        return name, 'True'
    return name, items[0]


def set_unique(d, key, value, msg):
    if key not in d:
        d[key] = value
    elif d[key] != value:
        raise ValueError(msg)


class Arguments:
    def __init__(self, types, defaults):
        # N.B. default values do *not* have to be of the type specified for
        # explicitly-provided values!
        self.types = types
        self.specified = set()
        self.values = defaults
        self.deferred = {}
        assert self.present <= self.required


    @property
    def required(self):
        return set(self.types.keys())


    @property
    def present(self):
        return set(self.values.keys())


    @property
    def available(self):
        return self.present | set(self.deferred.keys())


    def _mark_specified(self, name):
        if name in self.specified:
            raise ValueError(f"duplicate specification of flag '{name}'")
        if name not in self.types:
            raise ValueError(f"unrecognized flag '{name}'")
        self.specified.add(name)


    def _specify_deferred(self, name, item):
        if not item.endswith('>'):
            raise ValueError(f"invalid flag format for flag '{name}'")
        parameter, equals, default = item[1:-1].partition('=')
        if equals: # Override original default, if any.
            self.values[name] = default
        self.deferred[parameter] = name


    def _specify_one(self, token):
        name, item = normalize_flag(token)
        self._mark_specified(name)
        if item.startswith('<'):
            self._specify_deferred(name, item)
        else:
            self.values[name] = self.types[name](item)


    def specify(self, tokens, deferral):
        for token in tokens:
            self._specify_one(token)
        available, required = self.available, self.required
        assert available <= required
        if available < required:
            missing = required - available
            raise ValueError(f"missing mandatory flags {missing}")
        if deferral is not None:
            for parameter, name in self.deferred.items():
                set_unique(
                    deferral.types, parameter, self.types[name],
                    f"conflicting uses for '{parameter}' parameter"
                )
                set_unique(
                    deferral.values, parameter, self.values[name],
                    f"conflicting values for '{parameter}' parameter default"
                )
        elif self.deferred:
            raise ValueError(f"can't use a template parameter here")


    def evaluate(self, parameters):
        for parameter, value in parameters.items():
            # value should have already been parsed.
            try:
                name = self.deferred[parameter]
            except KeyError: # meant to be used elsewhere
                continue
            self.values[name] = value
        present, required = self.present, self.required
        assert present <= required
        if present < required:
            missing = required - present
            raise ValueError(f"missing mandatory flags {missing}")
        return self.values.copy()
