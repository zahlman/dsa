# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

from functools import wraps
from time import time


"""A simple logging system with timing and indentation."""


def trace(message):
    if trace._tracing:
        print('    ' * trace._level + message)
trace._level = 0
trace._tracing = True


def tracing(setting):
    trace._tracing = setting


def _timed(action, description, *args, **kwargs):
    trace(description)
    trace._level += 1
    t = time()
    result = action(*args, **kwargs)
    elapsed = int((time() - t) * 1000)
    trace._level -= 1
    trace(f'Done ({elapsed} ms)')
    return result


def timed(description):
    def _wrapper(action):
        @wraps(action)
        def _wrapped(*args, **kwargs):
            return _timed(action, description, *args, **kwargs)
        return _wrapped
    return _wrapper
