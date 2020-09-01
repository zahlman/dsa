# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

import toml
from glob import glob
from pathlib import Path


_LIBRARY = Path(__file__).absolute().parent / 'library'
_CATALOG_PATH = _LIBRARY / 'catalog.toml'
_DEFAULT_CATALOG = {
    'sys': {'path': '.', 'default': True, 'targets': {'*': ('**',)}}
}


def _read_catalog(name):
    if name is not None:
        return toml.load(name), Path(name).parent
    try:
        return toml.load(_CATALOG_PATH), _LIBRARY
    except FileNotFoundError:
        with open(_CATALOG_PATH, 'w') as f:
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
        yield from glob(glob_path, recursive=True)
