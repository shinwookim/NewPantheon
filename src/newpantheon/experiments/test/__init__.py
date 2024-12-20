from pathlib import Path
from os import path
from random import shuffle

from newpantheon.experiments.test.helpers import parse_config_file, setup_metadata
from newpantheon.common.utils import parse_remote_path
from newpantheon.common import context
from newpantheon.common.logger import log_print
from newpantheon.common.process_manager import call
from .test import Test
from newpantheon.common.context import default_config_location


def run_test(args):
    # check and get git summary
    if args.config_file is not None:
        config = parse_config_file(args.config_file)
        cc_schemes = [flow['scheme'] for flow in config['flows']]
    elif args.all:
        config = parse_config_file(default_config_location)
        cc_schemes = list(config["schemes"].keys())
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


def pkill(args):
    log_print("Cleaning up using pkill...(enabled by --pkill-cleanup)")
    if args.mode == "remote":
        r = parse_remote_path(args.remote_path)
        remote_pkill_src = path.join(r["base_dir"], "tools", "pkill.py")

        cmd = r["ssh_cmd"] + ["python", remote_pkill_src, "--kill-dir", r["base_dir"]]
        call(cmd)

    pkill_src = path.join(context.base_dir, "tools", "pkill.py")
    cmd = ["python", pkill_src, "--kill-dir", context.src_dir]
    call(cmd)
