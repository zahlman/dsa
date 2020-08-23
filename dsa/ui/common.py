# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

from .tracing import my_tracer
from ..errors import UserError
from datetime import datetime
import sys, traceback
from epmanager import entrypoint, DefaultParser


"""Common loading routines for dsa and dsd."""


@my_tracer('Loading binary')
def get_data(source):
    with open(source, 'rb') as f:
        return f.read()


def _errmsg(e):
    print(e, file=sys.stderr)


def _crash(e, tb):
    now = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
    filename = f'dsalog-{now}.txt'
    _errmsg('DSA encountered an internal error and must abort:')
    _errmsg(e)
    try:
        with open(filename, 'w') as f:
            f.writelines(tb)
    except Exception as e:
        _errmsg('DSA tried but failed to produce an error report. Sorry. :(')
    else:
        _errmsg(f'A log was be saved to {filename}.')
        _errmsg(f'Please submit it when reporting errors.')


def _io_error(e):
    _errmsg('DSA encountered a problem with reading or writing a file:')
    _errmsg(e)
    _errmsg('Please make sure that the path is correct and nothing is')
    _errmsg('trying to use the file at the same time as DSA. Aborting.')


def _user_error(e):
    _errmsg('DSA encountered an error in the data:')
    _errmsg(f'{e.__class__.__name__}: {e}')
    _errmsg('Aborting.')


class _ReportingParser(DefaultParser):
    def setup(self, config):
        super().setup(config)
        self._message = config['message']


    @classmethod
    def config_keys(cls):
        return {'message'}


    def call_with(self, parsed_args):
        try:
            with my_tracer(self._message):
                self.raw_call(parsed_args)
        except Exception as e:
            _errmsg(' OOPS '.center(58, '-'))
            if isinstance(e, IOError):
                _io_error(e)
            elif isinstance(e, UserError):
                _user_error(e)
            else:
                _crash(e, traceback.format_exc())


def dsa_entrypoint(**kwargs):
    assert 'parser_class' not in kwargs
    kwargs['parser_class'] = _ReportingParser
    return entrypoint(**kwargs)
