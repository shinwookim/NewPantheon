import json
import random
from pathlib import Path

import yaml

from .experiment_old import Test
from ..common import utils, context


def parse_config_file(cfg_file):
    raise NotImplementedError


def run_test(args):
    if args.config_file is not None:  # TODO
        parse_config_file(args.config_file)
    elif args.all:
        with open(Path(context.src_dir) / 'experiments' / 'config.yml') as cfg:
            config = yaml.load(cfg, Loader=yaml.CLoader)
        cc_schemes = config['schemes'].keys()
    elif args.schemes is not None:
        cc_schemes = args.schemes.split()

    if args.random_order:
        random.shuffle(cc_schemes)

    meta = vars(args).copy()
    meta['cc_schemes'] = str(cc_schemes)
    meta['git_summary'] = utils.get_git_summary(args.mode, getattr(args, 'remote_path', None))
    metadata_path = Path(args.data_dir) / 'pantheon_metadata.json'
    for key in list(meta.keys()):
        if meta[key] is None or key in ['all', 'schemes', 'data_dir', 'pkill_cleanup']:
            meta.pop(key)

    if 'uplink_trace' in meta:
        meta['uplink_trace'] = str(Path(meta['uplink_trace']).name)
    if 'downlink_trace' in meta:
        meta['downlink_trace'] = str(Path(meta['downlink_trace']).name)

    print(meta)
    with open(metadata_path, 'w') as f:
        json.dump(meta, f)


    # run tests
    for run_id in range(args.start_run_id, args.start_run_id + args.run_times):
        if not hasattr(args, 'test_config') or args.test_config is None:
            for cc in cc_schemes:
                Test(args, run_id, cc).run()
        else:
            raise NotImplementedError
