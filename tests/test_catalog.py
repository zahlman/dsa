# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

# System under test.
from dsa.catalog import PathSearcher
# Standard library.
import shutil
# Third-party.
import pytest


def _verify(search, kind, *paths):
    assert set(search(kind)) == set(paths)


def _make_lib(target):
    return PathSearcher.create((), ('lib',), target)


def test_catalog_sys(environment):
    # When no library is specified, the system library is used.
    sys_lib = environment[2] / 'library'
    assert PathSearcher.create((), (), None).where == {(sys_lib, '**')}


def test_catalog_sys_dsd(environment, capsys):
    test_lib = environment[0] / 'lib'
    sys_lib = environment[2] / 'library'
    # If a library path is specified, and the system library is not
    # explicitly requested, it is not used.
    assert PathSearcher.create((), ('lib',), 'dsd').where == {(test_lib, 'dsd')}
    # Similarly if a library name is specified.
    assert PathSearcher.create(('bogus',), (), 'dsd').where == set()
    assert 'Skipping library `bogus`: unknown name' in capsys.readouterr().out
    # This is worked around with an explicit specification.
    assert PathSearcher.create(('sys',), ('lib',), 'dsd').where == {
        (sys_lib, '**'), (test_lib, 'dsd')
    }
    # TODO: test dsa-use/dsa-drop functionality, with proper cleanup.


def test_catalog_test1_default(environment):
    test_lib = environment[0] / 'lib'
    shutil.copy(test_lib / 'targets1.toml', test_lib / 'targets.toml')
    # The * target is always used.
    search = _make_lib(None)
    assert search.where == {(test_lib, '')}
    _verify(search, 'filters', test_lib / 'filters' / 'use.py')


def test_catalog_test1_A(environment):
    test_lib = environment[0] / 'lib'
    shutil.copy(test_lib / 'targets1.toml', test_lib / 'targets.toml')
    search = _make_lib('A')
    assert search.where == {(test_lib, ''), (test_lib, 'A/**')}
    _verify(search, 'filters',
        test_lib / 'filters' / 'use.py',
        test_lib / 'filters' / 'A' / 'use.py',
        test_lib / 'filters' / 'A' / 'outer' / 'use.py',
        test_lib / 'filters' / 'A' / 'outer' / 'inner' / 'use.py'
    )


def test_catalog_test2_default(environment):
    test_lib = environment[0] / 'lib'
    shutil.copy(test_lib / 'targets2.toml', test_lib / 'targets.toml')
    # Since there is no * target to use, there are no results.
    assert _make_lib(None).where == set()


def test_catalog_test2_A(environment):
    test_lib = environment[0] / 'lib'
    shutil.copy(test_lib / 'targets2.toml', test_lib / 'targets.toml')
    search = _make_lib('A')
    assert search.where == {(test_lib, 'A')}
    # The top level is not used, and subdirectories are not recursed into.
    _verify(search, 'types', test_lib / 'types' / 'A' / 'A.txt')


def test_catalog_test2_B(environment):
    test_lib = environment[0] / 'lib'
    shutil.copy(test_lib / 'targets2.toml', test_lib / 'targets.toml')
    search = _make_lib('B')
    assert search.where == {(test_lib, 'B/**')}
    _verify(search, 'types',
        # The top level is not used.
        test_lib / 'types' / 'B' / 'B.txt',
        # Subdirectories are recursed into.
        test_lib / 'types' / 'B' / 'nested' / 'B.txt'
    )
