#!/usr/bin/env python3

"""Main Entry Point for Pantheon"""

import argparse
from newpantheon import experiments, analysis


def parse_app_args():
    """Parse Arguments"""
    parser = argparse.ArgumentParser(
        description="Program for analysis and experiments using Pantheon"
    )

    # Define top-level subcommands
    subparsers = parser.add_subparsers(
        dest="command", required=True, help="Main commands"
    )

    experiments.setup_args(subparsers)

    analysis.setup_args(subparsers)

    args = experiments.setup_args(subparsers, parser)

    # Parse arguments
    # args = parser.parse_args()
    return args


def main():
    """Main Entrypoint for Pantheon"""
    parsed_args = parse_app_args()
    command_map = {
        "experiment": experiments.run,
        "analysis": analysis.run,
    }
    command_map[parsed_args.command](parsed_args)


if __name__ == "__main__":
    main()
