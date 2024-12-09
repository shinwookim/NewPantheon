import ast
import json
from os import path

from newpantheon.common import context

from newpantheon.analysis import plot, plot_over_time, report, tunnel_graph
# from report import run
# import report

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
        default=path.join(context.src_dir, 'experiments', 'data'),
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
    # parse_analyze_shared(subparser)
    # parse_plot(subparser)
    # parse_over_time(subparser)
    # parse_tunnel_graph(subparser)
    subparser.add_argument('--include-acklink', action='store_true',
                        help='include acklink analysis')
    # subparser.add_argument('tunnel_log', metavar='tunnel-log',
                        # help='tunnel log file')
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
        default=path.join(context.src_dir, 'experiments', 'data'),
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
    
    # Define nested subcommands for 'analysis'
    # analysis_subparsers = parser_analysis.add_subparsers(
    #     dest="analysis_command", required=True
    # )

    # parse_tunnel_graph(analysis_subparsers.add_parser(
    #     'tunnel-graph', help='Evaluate throughput and delay of a tunnel log and generate graphs'))
    # parse_plot(analysis_subparsers.add_parser('plot', help='Plot throughput and delay graphs for schemes in tests'))
    # parse_report(analysis_subparsers.add_parser('report', help='Generate a PDF report summarizing test results'))
    # parse_over_time(analysis_subparsers.add_parser('over-time', help='Plot throughput-time graph for schemes in tests'))
    parse_report(parser_analysis)

def run(args):
    print(args)
    plot_cmd = ['python', plot]
    report_cmd = ['python', report]

    for cmd in [plot_cmd, report_cmd]:
        if args.data_dir:
            cmd += ['--data-dir', args.data_dir]
        if args.schemes:
            cmd += ['--schemes', args.schemes]
        if args.include_acklink:
            cmd += ['--include-acklink']

    
    if args.schemes is None:
        file_path = args.data_dir + "/pantheon_metadata.json"
        with open(file_path, 'r') as f:
            # Load the JSON data into a Python dictionary
            data = json.load(f)
        # print(type(dict_keys(data["cc_schemes"])), list(data["cc_schemes"]))
        schemes_str = data["cc_schemes"]
        schemes_str = schemes_str[schemes_str.find("[")+1:schemes_str.find("]")]
        args.schemes = " ".join(ast.literal_eval(schemes_str))
        
    print("Schemes", args.schemes)

    plot.run(args)
    plot_over_time.run(args)
    # tunnel_graph.run(args)
    report.run(args)
    # match args.analysis_command:
    #     case "report":
    #         report.run(args)
    #     case "plot":
    #         plot.run(args)
    #     case "over-time":
    #         plot_over_time.run()
    #     case "tunnel-graph":
    #         tunnel_graph.run()
    #     case "default":
    #         print("[Pantheon Analysis] Unknown command.")
