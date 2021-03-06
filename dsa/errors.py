# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

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


    @classmethod
    def convert(cls, exctype, action, *args, **kwargs):
        # N.B. kwargs are for the action, not the exception class!
        try:
            return action(*args, **kwargs)
        except exctype as e:
            raise cls(reason=str(e)) from e


class SequenceError(UserError):
    @classmethod
    def first_not_none(cls, candidates, **kwargs):
        try:
            return next(c for c in candidates if c is not None)
        except StopIteration:
            raise cls(**kwargs)


class MappingError(UserError):
    @classmethod
    def get(cls, mapping, key, **kwargs):
        try:
            return mapping[key]
        except KeyError:
            raise cls(key=key, **kwargs)


    @classmethod
    def add_unique(cls, mapping, key, value, **kwargs):
        if key in mapping:
            raise cls(key=key, **kwargs)
        mapping[key] = value


def wrap(tag, action, *args, **kwargs):
    try:
        return action(*args, **kwargs)
    except UserError as e:
        message = str(e).replace('{', '{{').replace('}', '}}')
        tag = tag.replace('{', '{{').replace('}', '}}')
        raise e.__class__(f'{tag}: {message}') from e
