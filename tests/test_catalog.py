# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

# System under test.
from dsa.catalog import get_search_paths, get_paths
# Third-party.
import pytest


def test_catalog_sys(environment):
    paths = get_search_paths(None, (), None)
    # Don't directly check the root value because it should have an
    # absolute path to the system library, which is nontrivial to deduce.
    assert len(paths) == 1
    root, path = paths[0]
    assert path == '**'


def test_catalog_no_library(environment):
    paths = get_search_paths('lib', (), None)
    assert len(paths) == 0


def test_catalog_test1_default(environment):
    lib = environment[0] / 'lib'
    # The * target is always used.
    paths = get_search_paths('lib', ('test1',), None)
    assert paths == [(lib, '')]
    assert set(get_paths(paths, 'filters')) == {
        lib / 'filters' / 'use.py'
    }


def test_catalog_test1_A(environment):
    lib = environment[0] / 'lib'
    paths = get_search_paths('lib', ('test1',), 'A')
    assert set(paths) == {(lib, ''), (lib, 'A/**')}
    assert set(get_paths(paths, 'filters')) == {
        lib / 'filters' / 'use.py',
        lib / 'filters' / 'A' / 'use.py',
        lib / 'filters' / 'A' / 'outer' / 'use.py',
        lib / 'filters' / 'A' / 'outer' / 'inner' / 'use.py'
    }


def test_catalog_test2_default(environment):
    # Since there is no * target to use, there are no results.
    paths = get_search_paths('lib', ('test2',), None)
    assert len(paths) == 0


def test_catalog_test2_A(environment):
    lib = environment[0] / 'lib'
    paths = get_search_paths('lib', ('test2',), 'A')
    assert set(paths) == {(lib, 'A')}
    assert set(get_paths(paths, 'types')) == {
        # The top level is not used.
        lib / 'types' / 'A' / 'A.txt'
        # Subdirectories are not recursed into.
    }


def test_catalog_test2_B(environment):
    lib = environment[0] / 'lib'
    paths = get_search_paths('lib', ('test2',), 'B')
    assert set(paths) == {(lib, 'B/**')}
    assert set(get_paths(paths, 'types')) == {
        # The top level is not used.
        lib / 'types' / 'B' / 'B.txt',
        # Subdirectories are recursed into.
        lib / 'types' / 'B' / 'nested' / 'B.txt'
    }
