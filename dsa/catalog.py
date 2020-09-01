# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

import toml
from glob import glob
from pathlib import Path


_LIBRARY = Path(__file__).absolute().parent / 'library'
_DEFAULT_CATALOG = {
    'sys': {'path': '.', 'default': True, 'targets': {'*': ('**',)}}
}


def _read_catalog(lib_root):
    if lib_root is not None:
        lib_root = Path(lib_root).absolute()
        return toml.load(lib_root / 'catalog.toml'), lib_root
    catalog_path = _LIBRARY / 'catalog.toml'
    try:
        return toml.load(catalog_path), _LIBRARY
    except FileNotFoundError:
        with open(catalog_path, 'w') as f:
            toml.dump(_DEFAULT_CATALOG, f)
        return _DEFAULT_CATALOG, _LIBRARY


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


def get_search_paths(catalog_name, lib_names, target_name):
    target_names = ('*',) if target_name is None else ('*', target_name)
    catalog = _normalize(*_read_catalog(catalog_name))
    return [
        (root, path)
        for name, root, default, lib_targets in catalog
        if (name in lib_names) or default
        for name in target_names
        for path in lib_targets.get(name, ())
    ]


def get_paths(search_paths, kind):
    ext = {
        'codec_code': 'py', 'codec_data': 'txt', 'filters': 'py',
        'interpreters': 'py', 'structgroups': 'txt', 'types': 'txt'
    }[kind]
    for root, search_path in search_paths:
        glob_path = str(root / kind / search_path / f'*.{ext}')
        for path in glob(glob_path, recursive=True):
            yield Path(path)
