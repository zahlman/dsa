from .common import extfile, roots
from .entrypoint import entry_point, param
from .location import get as root
import os


@param('path', 'path to use (should be absolute)')
@entry_point('Data Structure Assembler - add library path')
def use_files(path):
    r = roots()
    if path not in r:
        with open(extfile(), 'a') as f:
            f.write(path + '\n')


@param('path', 'path to stop using (should be absolute)')
@entry_point('Data Structure Assembler - remove library path')
def drop_files(path):
    result = roots()
    result.remove(path)
    with open(extfile(), 'w') as f:
        for line in result:
            f.write(line + '\n') # ensure trailing newline



