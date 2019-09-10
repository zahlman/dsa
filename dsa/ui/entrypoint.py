from argparse import ArgumentParser
from functools import partial


"""System for creating entry points."""


def _invoke(func):
    # Use command-line arguments to call a function that was decorated
    # with `entry_point`, and possibly one or more `params`.
    func(**vars(func._parser.parse_args()))


def _setup(description, func):
    # implementation for `entry_point`.
    func._parser = ArgumentParser(
        prog=func.__name__, description=description
    )
    func.invoke = partial(_invoke, func)
    return func


def _add_param(args, kwargs, func):
    *args, helptext = args
    func._parser.add_argument(*args, help=helptext, **kwargs)
    return func


def entry_point(description):
    """Set up a function for use as a CLI entry point by calling .invoke().
    This decorator must come after `param` decorators, but before anything
    that replaces the underlying function.
    The function will be called by parsing the command-line arguments into a
    Namespace, converting to a dict and splatting it out as kwargs."""
    return partial(_setup, description)


def param(*args, **kwargs):
    """Add an argument to the parser for an entry_point function.
    The parameters are the same as for `argparse.ArgumentParser.add_argument`,
    except that the last positional argument is turned into a `help` keyword
    argument.
    Decorators that add positional arguments should appear in the reverse
    order of how they will be input on the command line.
    """
    return partial(_add_param, args, kwargs)
