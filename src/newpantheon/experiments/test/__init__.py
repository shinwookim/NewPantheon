from pathlib import Path
from ...common import context
from .helpers import parse_config_file, setup_metadata
from random import shuffle
from .test import Test

default_config_location: Path = context.src_dir / "experiments" / "default_config.yml"

def run_test(args):
    if args.config_file is not None:
        config = parse_config_file(args.config_file)
        cc_schemes = config["schemes"].keys()
    elif args.all:
        config = parse_config_file(default_config_location)
        cc_schemes = config["schemes"].keys()
    elif args.schemes is not None:
        cc_schemes = args.schemes.split()
    else:
        raise Exception("Must specify either --schemes or --all")

    if args.random_order:
        shuffle(cc_schemes)

    # Create metadata JSON and write to data_dir / pantheon_metadata.json
    setup_metadata(args, cc_schemes)

    # run tests
    for run_id in range(args.start_run_id, args.start_run_id + args.run_times):
        if not hasattr(args, "test_config") or args.test_config is None:
            for cc in cc_schemes:
                Test(args, run_id, cc).run()
        else:
            Test(args, run_id, None).run()
