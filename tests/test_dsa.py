# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

# System under test.
from dsa.ui.dsd import dsd
# Standard library.
import os, shutil
from pathlib import Path
# Third-party.
import pytest


HERE = Path(os.path.abspath(__file__)).parent


@pytest.fixture(scope='session', autouse=True)
def session(tmp_path_factory):
    try:
        yield
    finally:
        shutil.rmtree(str(tmp_path_factory.getbasetemp()))


@pytest.fixture
def environment(tmp_path):
    # Create a temp directory for the test, where output files will be
    # written. Some test binary data is copied here to be analysed, and the
    # results will be compared to reference files in expected/.
    try:
        old_path = Path.cwd()
        os.chdir(tmp_path)
        with open('test.bin', 'wb') as data:
            data.write(bytes(range(256)))
        yield tmp_path
    finally:
        os.chdir(old_path)


def _important_lines(filename):
    with open(filename) as f:
        return [
            line for line in (line.rstrip() for line in f) 
            if line != '' and not line.startswith('#')
        ]


def _validate(base_name):
    # The generated file exactly matches a reference expectation file.
    actual = _important_lines(f'{base_name}.txt')
    expected = _important_lines(HERE / 'expected' / f'{base_name}.txt')
    assert actual == expected


def test_input(environment):
    with open('test.bin', 'rb') as f:
        data = f.read()
    assert list(data) == list(range(256))


def test_disassemble_hexdump(environment):
    dsd('test.bin', 'hex:0', 'test_hex.txt', None)
    _validate('test_hex')


def test_disassemble_partial(environment):
    dsd('test.bin', 'hex:0x81', 'test_hex_partial.txt', None)
    _validate('test_hex_partial')
