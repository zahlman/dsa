# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

import dsa
from os import chdir
from pathlib import Path
from shutil import rmtree, copytree
import pytest


@pytest.fixture(scope='session', autouse=True)
def session(tmp_path_factory):
    try:
        yield
    finally:
        rmtree(str(tmp_path_factory.getbasetemp()))


@pytest.fixture
def environment(tmp_path):
    # Create a temp directory for the test, where output files will be
    # written. Some test binary data is copied here to be analysed, and the
    # results will be compared to reference files in expected/.
    try:
        old_path = Path.cwd()
        chdir(tmp_path)
        environment.path = Path(tmp_path)
        src = Path(__file__).absolute().parent
        environment.reference = src / 'expected'
        with open('test.bin', 'wb') as data:
            data.write(bytes(range(256)))
        copytree(src / 'lib', 'lib')
        yield (
            Path(tmp_path).absolute(), # location for testing
            src / 'expected', # location of stored reference results
            Path(dsa.__file__).absolute().parent # location of installed code
        )
    finally:
        chdir(old_path)
