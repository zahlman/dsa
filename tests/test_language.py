# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

# System under test.
import dsa.language
# Third-party.
import pytest


def _dummy_search(kind):
    # No search is repeated.
    assert kind not in _dummy_search.called_with
    _dummy_search.called_with.add(kind)
    return ()


def _dummy_setup(x, y, z):
    # The arguments were forwarded.
    assert (x, y, z) == (1, 2, 3)
    _dummy_search.called_with = set()
    return _dummy_search


def test_uses_catalog(environment, monkeypatch):
    monkeypatch.setattr(dsa.language.PathSearcher, 'from_catalog', _dummy_setup)
    language = dsa.language.Language.from_catalog(1, 2, 3)
    # Every search is performed.
    assert _dummy_search.called_with == {
        'codec_code', 'codec_data', 'filters',
        'interpreters', 'structgroups', 'types'
    }
