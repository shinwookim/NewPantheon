import ast
import json
from os import path

from newpantheon.common import context

from newpantheon.analysis import plot, plot_over_time, report

def parse_tunnel_graph(subparser):
    subparser.add_argument('tunnel_log', metavar='tunnel-log',
                        help='tunnel log file')
    subparser.add_argument(
        '--throughput', metavar='OUTPUT-GRAPH',
        action='store', dest='throughput_graph',
        help='throughput graph to save as (default None)')
    subparser.add_argument(
        '--delay', metavar='OUTPUT-GRAPH',
        action='store', dest='delay_graph',
        help='delay graph to save as (default None)')
    subparser.add_argument(
        '--ms-per-bin', metavar='MS-PER-BIN', type=int, default=500,
        help='bin size in ms (default 500)')   


def parse_analyze_shared(parser):
    parser.add_argument(
        '--schemes', metavar='"SCHEME1 SCHEME2..."',
        help='analyze a space-separated list of schemes '
        '(default: "cc_schemes" in pantheon_metadata.json)')
    parser.add_argument(
        '--data-dir', metavar='DIR',
        default=path.join(context.src_dir, 'src', 'tmp'),
        help='directory that contains logs and metadata '
        'of pantheon tests (default pantheon/experiments/data)')


def parse_plot(subparser):
    parse_analyze_shared(subparser)
    subparser.add_argument('--include-acklink', action='store_true',
                        help='include acklink analysis')
    subparser.add_argument(
        '--no-graphs', action='store_true', help='only append datalink '
        'statistics to stats files with no graphs generated')
 


def parse_report(subparser):
    subparser.add_argument('--include-acklink', action='store_true',
                        help='include acklink analysis')
    subparser.add_argument(
        '--interactions', action='store_true', 
        help='analyze the interactions between ccs')
    subparser.add_argument(
        '--throughput', metavar='OUTPUT-GRAPH',
        action='store', dest='throughput_graph',
        help='throughput graph to save as (default None)')
    subparser.add_argument(
        '--delay', metavar='OUTPUT-GRAPH',
        action='store', dest='delay_graph',
        help='delay graph to save as (default None)') 
    subparser.add_argument(
        '--schemes', metavar='"SCHEME1 SCHEME2..."', default=None, 
        help='analyze a space-separated list of schemes '
        '(default: "cc_schemes" in pantheon_metadata.json)')
    subparser.add_argument(
        '--data-dir', metavar='DIR',
        default=path.abspath(path.join(path.dirname( __file__ ), '..', '..', 'tmp')),
        help='directory that contains logs and metadata '
        'of pantheon tests (default pantheon/experiments/data)')
    subparser.add_argument(
        '--no-graphs', action='store_true', help='only append datalink '
        'statistics to stats files with no graphs generated')
    subparser.add_argument(
        '--ms-per-bin', metavar='MS-PER-BIN', type=int, default=500,
        help='bin size in ms (default 500)')
    subparser.add_argument(
        '--amplify', metavar='FACTOR', type=float, default=1.0,
        help='amplication factor of output graph\'s x-axis scale ')


def parse_over_time(subparser):
    parse_analyze_shared(subparser)
    subparser.add_argument(
        '--ms-per-bin', metavar='MS-PER-BIN', type=int, default=500,
        help='bin size in ms (default 500)')
    subparser.add_argument(
        '--amplify', metavar='FACTOR', type=float, default=1.0,
        help='amplication factor of output graph\'s x-axis scale ')
  

def parse_analyze(subparser):
    parse_analyze_shared(subparser)
    subparser.add_argument('--include-acklink', action='store_true',
                        help='include acklink analysis')
    
def setup_args(subparsers):
    parser_analysis = subparsers.add_parser("analysis", help="Run Analysis")
    parse_report(parser_analysis)

def run(args):
    if args.schemes is None:
        file_path = args.data_dir + "/pantheon_metadata.json"
        with open(file_path, 'r') as f:
            # Load the JSON data into a Python dictionary
            data = json.load(f)
        schemes_str = ast.literal_eval(data["cc_schemes"])
        args.schemes = " ".join(schemes_str)
        if "test-name" in data:
            args.test_name = data["test-name"]

    plot.run(args)
    plot_over_time.run(args)
    report.run(args)
