# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

import os.path
from epmanager import entrypoint


"""Interface to determine where DSA is installed."""


def folder(filename):
    """Resolve a filename to the full path of its containing folder."""
    return os.path.realpath(os.path.join(filename, '..'))


_DSA_ROOT = folder(folder(__file__))


def get():
    return _DSA_ROOT


@entrypoint(
    name='whereisdsa',
    description='Data Structure Assembler - location of root folder'
)
def display():
    return f'DSA is installed in: {get()}'
