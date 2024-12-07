from pathlib import Path

from newpantheon.common import context

def setup_args(subparsers):
    parser_analysis = subparsers.add_parser("analysis", help="Run Analysis")

def run(args):
    print(args)
    