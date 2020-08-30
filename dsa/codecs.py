# Copyright (C) 2018-2020 Karl Knechtel
# Licensed under the Open Software License version 3.0

from .plugins import is_class_with, is_method, load_plugins
from .parsing.file_parsing import load_files
from .parsing.codec_loader import CodecLoader
from .ui.tracing import my_tracer


def make_codec_library(code_paths, data_paths):
    with my_tracer('Setting up codec loaders'):
        loader_spec = (is_class_with, {'line': is_method, 'result': is_method})
        subloaders = load_plugins(code_paths, {'Loader': loader_spec})
    with my_tracer('Creating codecs from config data'):
        return load_files(data_paths, CodecLoader, subloaders)
