# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

from ..catalog import read_sys_catalog, write_sys_catalog
from ..errors import MappingError, UserError
from pathlib import Path
from epmanager import entrypoint


class MANDATORY_PATH(UserError):
    """The `sys` library may not be removed or changed"""


class NO_SUCH_LIBRARY(MappingError):
    """No library named `{key}` was registered"""


@entrypoint(
    name='dsa-use',
    description='Data Structure Assembler - add library path',
    library_name='symbolic name for library',
    path='path to use'
)
def use_files(library_name, path):
    MANDATORY_PATH.require(library_name != 'sys')
    catalog = read_sys_catalog()
    if library_name in catalog:
        print(f'Warning: overwriting existing path `{catalog[library_name]}`.')
    catalog[library_name] = str(Path(path).resolve())
    write_sys_catalog(catalog)


@entrypoint(
    name='dsa-drop',
    description='Data Structure Assembler - remove library path',
    library_name='name of library no longer being used'
)
def drop_files(library_name):
    MANDATORY_PATH.require(library_name != 'sys')
    catalog = read_sys_catalog()
    NO_SUCH_LIBRARY.get(catalog, library_name)
    del catalog[library_name]
    write_sys_catalog(catalog)
