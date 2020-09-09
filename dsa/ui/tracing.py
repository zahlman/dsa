# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

from functools import wraps
from time import time
import sys


"""A simple logging system with timing and indentation."""


class _Helper:
    # An implementation class that can be used as either a decorator
    # or a context manager.
    def __init__(self, owner, message):
        self._owner = owner
        self._message = message


    def __enter__(self):
        return self._owner.start(self._message)


    def __exit__(self, exc_type, exc, traceback):
        self._owner.stop('Aborted' if exc else 'Done')


    def __call__(self, func):
        @wraps(func)
        def _wrapped(*args, **kwargs):
            with self:
                return func(*args, **kwargs)
        return _wrapped


class TimingTracer:
    def __init__(self):
        self._timestamps = []


    def trace(self, message):
        print('    ' * len(self._timestamps), message, sep='')


    def start(self, message):
        self.trace(f'{message}...')
        self._timestamps.append(time())
        return self


    def stop(self, tag):
        elapsed = int((time() - self._timestamps.pop()) * 1000)
        self.trace(f'{tag} ({elapsed} ms)')
        sys.stdout.flush()


    def __call__(self, message):
        return _Helper(self, message)


my_tracer = TimingTracer()
