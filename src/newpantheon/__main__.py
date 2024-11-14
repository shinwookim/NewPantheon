#!/usr/bin/env python3

import argparse
from . import experiments

def parse_app_args():
    parser = argparse.ArgumentParser(description="Program for analysis and experiments using Pantheon")

    # Define top-level subcommands
    subparsers = parser.add_subparsers(dest='command', required=True, help="Main commands")

    experiments.setup_args(subparsers)

    parser_analysis = subparsers.add_parser('analysis', help="Run analysis")

    # Parse arguments
    args = parser.parse_args()
    return args

def main():
    parsed_args = parse_app_args()
    command_map = {
        "experiment": experiments.run,
    }
    command_map[parsed_args.command](parsed_args)


if __name__ == "__main__":
    main()
