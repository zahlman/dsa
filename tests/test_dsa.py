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
    try:
        old_path = Path.cwd()
        os.chdir(tmp_path)
        # dirs_exist_ok requires Python 3.8.
        shutil.copytree(HERE / 'environment', '.', dirs_exist_ok=True)
        yield tmp_path
    finally:
        os.chdir(old_path)


def _important_lines(filename):
    with open(filename) as f:
        return [
            line for line in (line.strip() for line in f) 
            if line != '' and not line.startswith('#')
        ]


def _validate(base_name):
    # The generated file exactly matches a reference expectation file.
    actual = _important_lines(f'{base_name}.txt')
    expected = _important_lines(f'{base_name}_ref.txt')
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
