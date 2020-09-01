# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

import toml
from functools import partial
from glob import glob
from pathlib import Path


_LIBRARY = Path(__file__).absolute().parent / 'library'
_DEFAULT_CATALOG = {
    'sys': {'path': '.', 'default': True, 'targets': {'*': ('**',)}}
}


def _read_catalog(lib_root):
    if lib_root is not None:
        lib_root = Path(lib_root).absolute()
        return toml.load(lib_root / 'catalog_legacy.toml'), lib_root
    catalog_path = _LIBRARY / 'catalog_legacy.toml'
    try:
        return toml.load(catalog_path), _LIBRARY
    except FileNotFoundError:
        with open(catalog_path, 'w') as f:
            toml.dump(_DEFAULT_CATALOG, f)
        return _DEFAULT_CATALOG, _LIBRARY


def read_sys_catalog():
    path = Path(__file__).absolute().parent / 'library'
    try:
        return toml.load(path / 'catalog.toml')
    except FileNotFoundError:
        data = {'sys': str(path)}
        write_sys_catalog(data)
        return data


def write_sys_catalog(lookup):
    path = Path(__file__).absolute().parent / 'library'
    with open(path / 'catalog.toml', 'w') as f:
        toml.dump(lookup, f)


def _normalize(catalog, catalog_root):
    return (
        (
            name,
            catalog_root / library.get('path', '.'),
            library.get('default', False),
            library.get('targets', {})
        )
        for name, library in catalog.items()
    )


def _path_info(library_root, target):
    try:
        with open(library_root / 'targets.toml') as f:
            targets = toml.load(f)
    except FileNotFoundError:
        targets = {}
        my_tracer.trace(
            f'Skipping library root `{library_root}`: no targets.toml found'
        )
    if '*' in targets:
        yield from targets['*']
    if target not in {None, '*'} and target in targets:
        yield from targets[target]


class PathSearcher:
    # Writing this as a class seems a bit more convenient for testing.
    def __init__(self, *where):
        self.where = where


    @property
    def where(self):
        return self._where


    @where.setter
    def where(self, value):
        self._where = set(value)


    @staticmethod
    def create(libraries, paths, target):
        if not libraries:
            libraries = {'sys'}
        library_roots = {Path(p).resolve() for p in paths}
        lookup = {k: Path(v).resolve() for k, v in read_sys_catalog().items()}
        for library in libraries:
            try:
                library_roots.add(lookup[library])
            except KeyError:
                my_tracer.trace(f'Skipping library `{library}`: unknown name')
        result = PathSearcher(*(
            (library_root, fragment)
            for library_root in library_roots
            for fragment in _path_info(library_root, target)
        ))
        return result


    @staticmethod
    def from_catalog(catalog_name, library_names, target_name):
        target_names = ('*',) if target_name is None else ('*', target_name)
        catalog = _normalize(*_read_catalog(catalog_name))
        return PathSearcher(*(
            (root, fragment)
            for library_name, root, default, library_targets in catalog
            if (library_name in library_names) or default
            for target_name in target_names
            for fragment in library_targets.get(target_name, ())
        ))


    def __call__(self, kind):
        ext = {
            'codec_code': 'py', 'codec_data': 'txt', 'filters': 'py',
            'interpreters': 'py', 'structgroups': 'txt', 'types': 'txt'
        }[kind]
        for root, fragment in self.where:
            glob_path = str(root / kind / fragment / f'*.{ext}')
            for path in glob(glob_path, recursive=True):
                yield Path(path)
