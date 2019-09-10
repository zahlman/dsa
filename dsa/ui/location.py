from .entrypoint import entry_point
import os.path


"""Interface to determine where DSA is installed."""


def folder(filename):
    """Resolve a filename to the full path of its containing folder."""
    return os.path.realpath(os.path.join(filename, '..'))


_DSA_ROOT = folder(folder(__file__))


def get():
    return _DSA_ROOT


@entry_point('Data Structure Assembler - location of root folder')
def display():
    # The trace system is not used because this function is not intended
    # to be used except as an entry point. The standard API is get().
    print(f'DSA is installed in: {get()}')
