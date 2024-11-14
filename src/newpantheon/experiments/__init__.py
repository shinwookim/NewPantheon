from pathlib import Path

from .test import run_test
from ..common import context


def parse_test_shared(parser):
    parser.add_argument(
        "-f", "--flows", type=int, default=1, help="number of flows (default 1)"
    )
    parser.add_argument(
        "-t",
        "--runtime",
        type=int,
        default=30,
        help="total runtime in seconds (default 30)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=0,
        help="interval in seconds between two flows (default 0)",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--all",
        action="store_true",
        help="test all schemes specified in src/config.yml",
    )
    group.add_argument(
        "--schemes",
        metavar='"SCHEME1 SCHEME2..."',
        help="test a space-separated list of schemes",
    )

    parser.add_argument(
        "--run-times",
        metavar="TIMES",
        type=int,
        default=1,
        help="run times of each scheme (default 1)",
    )
    parser.add_argument(
        "--start-run-id", metavar="ID", type=int, default=1, help="run ID to start with"
    )
    parser.add_argument(
        "--random-order", action="store_true", help="test schemes in random order"
    )
    parser.add_argument(
        "--data-dir",
        metavar="DIR",
        default=Path(context.src_dir) / "experiments" / "data",  # TODO: Change
        help="directory to save all test logs, graphs, "
        "metadata, and report (default pantheon/src/experiments/data)",
    )
    parser.add_argument(
        "--pkill-cleanup",
        action="store_true",
        help="clean up using pkill (send SIGKILL when necessary) if there were errors during tests",
    )


def parse_test_local(parser):
    parser.add_argument(
        "--uplink-trace",
        metavar="TRACE",
        default=Path(context.src_dir) / "experiments" / "12mbps.trace",
        help="uplink trace (from sender to receiver) to pass to mm-link "
        "(default pantheon/test/12mbps.trace)",
    )
    parser.add_argument(
        "--downlink-trace",
        metavar="TRACE",
        default=Path(context.src_dir) / "experiments" / "12mbps.trace",
        help="downlink trace (from receiver to sender) to pass to mm-link "
        "(default pantheon/test/12mbps.trace)",
    )
    parser.add_argument(
        "--prepend-mm-cmds",
        metavar='"CMD1 CMD2..."',
        help="mahimahi shells to run outside of mm-link",
    )
    parser.add_argument(
        "--append-mm-cmds",
        metavar='"CMD1 CMD2..."',
        help="mahimahi shells to run inside of mm-link",
    )
    parser.add_argument(
        "--extra-mm-link-args",
        metavar='"ARG1 ARG2..."',
        help="extra arguments to pass to mm-link when running locally. Note "
        "that uplink (downlink) always represents the link from sender to "
        "receiver (from receiver to sender)",
    )


def parse_test_remote(parser):
    parser.add_argument(
        "--sender",
        choices=["local", "remote"],
        default="local",
        action="store",
        dest="sender_side",
        help="the side to be data sender (default local)",
    )
    parser.add_argument(
        "--tunnel-server",
        choices=["local", "remote"],
        default="remote",
        action="store",
        dest="server_side",
        help="the side to run pantheon tunnel server on (default remote)",
    )
    parser.add_argument(
        "--local-addr",
        metavar="IP",
        help="local IP address that can be reached from remote host, "
        'required if "--tunnel-server local" is given',
    )
    parser.add_argument(
        "--local-if",
        metavar="INTERFACE",
        help="local interface to run pantheon tunnel on",
    )
    parser.add_argument(
        "--remote-if",
        metavar="INTERFACE",
        help="remote interface to run pantheon tunnel on",
    )
    parser.add_argument(
        "--ntp-addr",
        metavar="HOST",
        help="address of an NTP server to query clock offset",
    )
    parser.add_argument(
        "--local-desc", metavar="DESC", help="extra description of the local side"
    )
    parser.add_argument(
        "--remote-desc", metavar="DESC", help="extra description of the remote side"
    )


def setup_args(subparsers):
    parser_experiment = subparsers.add_parser("experiment", help="Run experiment")

    # Define nested subcommands for 'experiment'
    experiment_subparsers = parser_experiment.add_subparsers(
        dest="experiment_command", required=True
    )

    # experiment setup
    parser_setup = experiment_subparsers.add_parser(
        "setup", help="Setup the experiment"
    )
    # Add specific arguments for 'experiment setup' if needed

    # experiment test
    parser_test = experiment_subparsers.add_parser(
        "test", help="Run test for the experiment"
    )
    parser_test.add_argument(
        "-c",
        "--config_file",
        metavar="CONFIG",
        help="path to configuration file (note: command line arguments override options in the configuration file",
    )

    # Add specific arguments for 'experiment test' if needed
    test_subparsers = parser_test.add_subparsers(dest="mode", required=True)
    parser_local_test = test_subparsers.add_parser(
        "local", help="test schemes locally in mahimahi emulated networks"
    )

    parser_remote_test = test_subparsers.add_parser(
        "remote", help="test schemes between local and remote in real-life networks"
    )
    parser_remote_test.add_argument(
        "remote_path",
        metavar="HOST:PANTHEON-DIR",
        help="HOST ([user@]IP) and PANTHEON-DIR (remote pantheon directory)",
    )

    parse_test_shared(parser_local_test), parse_test_shared(parser_remote_test)
    parse_test_local(parser_local_test)
    parse_test_remote(parser_remote_test)


def run(args):
    if args.experiment_command == "test":
        run_test(args)
