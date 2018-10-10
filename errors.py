class UserError(ValueError):
    """For now, the __doc__ of a subclass provides the message template."""
    def __init__(self, **kwargs):
        super().__init__(self.__doc__.format_map(kwargs))


    @classmethod
    def require(cls, condition, **kwargs):
        if not condition:
            raise cls(**kwargs)


class MappingError(UserError):
    @classmethod
    def get(cls, mapping, key):
        try:
            return mapping[key]
        except KeyError:
            raise cls(key=key)

    
    @classmethod
    def add_unique(cls, mapping, key, value):
        if key in mapping:
            raise cls(key=key)
        mapping[key] = value


def parse_int(text):
    try:
        return int(text, 0)
    except ValueError as e:
        raise UserError(e) from e


def wrap(label, value, action, *args, **kwargs):
    try:
        return action(*args, **kwargs)
    except UserError as e:
        raise e.__class__(f'{label} {value}: {e}') from e
