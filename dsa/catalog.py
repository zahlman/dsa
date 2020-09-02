# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

import toml
from glob import glob
from pathlib import Path


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
        if not (libraries or paths):
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


    def __call__(self, kind):
        ext = {
            'codec_code': 'py', 'codec_data': 'txt', 'filters': 'py',
            'interpreters': 'py', 'structgroups': 'txt', 'types': 'txt'
        }[kind]
        for root, fragment in self.where:
            glob_path = str(root / kind / fragment / f'*.{ext}')
            for path in glob(glob_path, recursive=True):
                yield Path(path)
