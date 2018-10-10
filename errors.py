class UserError(ValueError):
    """For now, the __doc__ of a subclass provides the message template."""
    def __init__(self, message=None, **kwargs):
        if message is None:
            message = self.__doc__
        super().__init__(message.format_map(kwargs))


    @classmethod
    def require(cls, condition, **kwargs):
        if not condition:
            raise cls(**kwargs)


class SequenceError(UserError):
    @classmethod
    def first_not_none(cls, candidates, **kwargs):
        try:
            return next(c for c in candidates if c is not None)
        except StopIteration:
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


def parse_int(text, description=None):
    try:
        return int(text, 0)
    except ValueError:
        description = '' if description is None else (description + ' ')
        raise UserError(f'{description}must be integer (got `{text}`)')


def wrap(tag, action, *args, **kwargs):
    try:
        return action(*args, **kwargs)
    except UserError as e:
        raise e.__class__(f'{tag}: {e}') from e
