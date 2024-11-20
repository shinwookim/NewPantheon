"""Helper function for logging output to standard error"""

import sys


def log_print(msg: str):
    """Helper function for logging output to standard error"""
    print(msg, file=sys.stderr, flush=True)
