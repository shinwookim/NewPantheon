def setup_args(subparsers):
    parser_experiment = subparsers.add_parser('experiment', help="Run experiment")

    # Define nested subcommands for 'experiment'
    experiment_subparsers = parser_experiment.add_subparsers(dest='experiment_command', required=True)

    # experiment setup
    parser_setup = experiment_subparsers.add_parser('setup', help="Setup the experiment")
    # Add specific arguments for 'experiment setup' if needed

    # experiment test
    parser_test = experiment_subparsers.add_parser('test', help="Run test for the experiment")
    # Add specific arguments for 'experiment test' if needed


def run(args):
    print("Hello World!")


