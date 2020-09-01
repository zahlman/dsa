# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

# System under test.
from dsa.catalog import get_search_paths, get_paths
# Standard library.
from os import chdir
import shutil
from pathlib import Path
# Third-party.
import pytest


HERE = Path(__file__).absolute().parent


@pytest.fixture(scope='session', autouse=True)
def session(tmp_path_factory):
    try:
        yield
    finally:
        shutil.rmtree(str(tmp_path_factory.getbasetemp()))


@pytest.fixture
def environment(tmp_path):
    global TEST_DIR
    # Create a temp directory for the test, where output files will be
    # written. Some test binary data is copied here to be analysed, and the
    # results will be compared to reference files in expected/.
    try:
        old_path = Path.cwd()
        chdir(tmp_path)
        TEST_DIR = Path(tmp_path)
        with open('test.bin', 'wb') as data:
            data.write(bytes(range(256)))
        shutil.copytree(HERE / 'lib', 'lib')
        yield tmp_path
    finally:
        chdir(old_path)


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
    # The * target is always used.
    paths = get_search_paths('lib', ('test1',), None)
    assert paths == [(TEST_DIR / 'lib', '')]
    assert set(get_paths(paths, 'filters')) == {
        TEST_DIR / 'lib' / 'filters' / 'use.py'
    }


def test_catalog_test1_A(environment):
    paths = get_search_paths('lib', ('test1',), 'A')
    assert set(paths) == {(TEST_DIR / 'lib', ''), (TEST_DIR / 'lib', 'A/**')}
    assert set(get_paths(paths, 'filters')) == {
        TEST_DIR / 'lib' / 'filters' / 'use.py',
        TEST_DIR / 'lib' / 'filters' / 'A' / 'use.py',
        TEST_DIR / 'lib' / 'filters' / 'A' / 'outer' / 'use.py',
        TEST_DIR / 'lib' / 'filters' / 'A' / 'outer' / 'inner' / 'use.py'
    }


def test_catalog_test2_default(environment):
    # Since there is no * target to use, there are no results.
    paths = get_search_paths('lib', ('test2',), None)
    assert len(paths) == 0


def test_catalog_test2_A(environment):
    paths = get_search_paths('lib', ('test2',), 'A')
    assert set(paths) == {(TEST_DIR / 'lib', 'A')}
    assert set(get_paths(paths, 'types')) == {
        # The top level is not used.
        TEST_DIR / 'lib' / 'types' / 'A' / 'A.txt'
        # Subdirectories are not recursed into.
    }


def test_catalog_test2_B(environment):
    paths = get_search_paths('lib', ('test2',), 'B')
    assert set(paths) == {(TEST_DIR / 'lib', 'B/**')}
    assert set(get_paths(paths, 'types')) == {
        # The top level is not used.
        TEST_DIR / 'lib' / 'types' / 'B' / 'B.txt',
        # Subdirectories are recursed into.
        TEST_DIR / 'lib' / 'types' / 'B' / 'nested' / 'B.txt'
    }
