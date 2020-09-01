# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

# System under test.
import dsa.catalog
# Third-party.
import pytest


from_catalog = dsa.catalog.PathSearcher.from_catalog


def _verify(search, kind, *paths):
    assert set(search(kind)) == set(paths)


def test_catalog_sys(environment):
    sys_lib = environment[2] / 'library'
    assert from_catalog(None, (), None).where == {(sys_lib, '**')}


def test_catalog_no_library(environment):
    assert from_catalog('lib', (), None).where == set()


def test_catalog_test1_default(environment):
    test_lib = environment[0] / 'lib'
    # The * target is always used.
    search = from_catalog('lib', ('test1',), None)
    assert search.where == {(test_lib, '')}
    _verify(search, 'filters', test_lib / 'filters' / 'use.py')


def test_catalog_test1_A(environment):
    test_lib = environment[0] / 'lib'
    search = from_catalog('lib', ('test1',), 'A')
    assert search.where == {(test_lib, ''), (test_lib, 'A/**')}
    _verify(search, 'filters',
        test_lib / 'filters' / 'use.py',
        test_lib / 'filters' / 'A' / 'use.py',
        test_lib / 'filters' / 'A' / 'outer' / 'use.py',
        test_lib / 'filters' / 'A' / 'outer' / 'inner' / 'use.py'
    )


def test_catalog_test2_default(environment):
    # Since there is no * target to use, there are no results.
    assert from_catalog('lib', ('test2',), None).where == set()


def test_catalog_test2_A(environment):
    test_lib = environment[0] / 'lib'
    search = from_catalog('lib', ('test2',), 'A')
    assert search.where == {(test_lib, 'A')}
    # The top level is not used, and subdirectories are not recursed into.
    _verify(search, 'types', test_lib / 'types' / 'A' / 'A.txt')


def test_catalog_test2_B(environment):
    test_lib = environment[0] / 'lib'
    search = from_catalog('lib', ('test2',), 'B')
    assert search.where == {(test_lib, 'B/**')}
    _verify(search, 'types',
        # The top level is not used.
        test_lib / 'types' / 'B' / 'B.txt',
        # Subdirectories are recursed into.
        test_lib / 'types' / 'B' / 'nested' / 'B.txt'
    )
