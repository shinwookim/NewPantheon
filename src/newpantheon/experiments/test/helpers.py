import json
import yaml
import sys
from pathlib import Path
from newpantheon.common import utils, context
import subprocess


def parse_config_file(cfg_file) -> dict:
    with open(cfg_file, "r") as f:
        config = yaml.load(f, Loader=yaml.CLoader)
        return config


def setup_metadata(args, cc_schemes):
    meta = vars(args).copy()
    meta["cc_schemes"] = str(cc_schemes)
    meta["git_summary"] = utils.get_git_summary(
        args.mode, getattr(args, "remote_path", None)
    )
    metadata_path = Path(args.data_dir) / "pantheon_metadata.json"
    for key in list(meta.keys()):
        if meta[key] is None or key in ["all", "schemes", "data_dir", "pkill_cleanup"]:
            meta.pop(key)
    if "uplink_trace" in meta:
        meta["uplink_trace"] = str(Path(meta["uplink_trace"]).name)
    if "downlink_trace" in meta:
        meta["downlink_trace"] = str(Path(meta["downlink_trace"]).name)
    print(meta)
    with open(metadata_path, "w") as f:
        json.dump(meta, f)


def query_clock_offset(ntp_addr, ssh_cmd):
    local_clock_offset = None
    remote_clock_offset = None

    ntp_cmds = {}
    ntpdate_cmd = ["ntpdate", "-t", "5", "-quv", ntp_addr]

    ntp_cmds["local"] = ntpdate_cmd
    ntp_cmds["remote"] = ssh_cmd + ntpdate_cmd

    for side in ["local", "remote"]:
        cmd = ntp_cmds[side]

        fail = True
        for _ in range(3):
            try:
                offset = subprocess.check_output(cmd).decode("utf-8")
                print(offset, file=sys.stderr)
                offset = offset.rsplit(" ", 2)[-2]
                offset = str(float(offset) * 1000)
            except subprocess.CalledProcessError:
                print("Failed to get clock offset", file=sys.stderr)
            except ValueError:
                print("Cannot convert clock offset to float", file=sys.stderr)
            else:
                if side == "local":
                    local_clock_offset = offset
                else:
                    remote_clock_offset = offset
                fail = False
                break
        if fail:
            print("Failed after 3 queries to NTP server", file=sys.stderr)

    return local_clock_offset, remote_clock_offset


def who_runs_first(cc):
    cc_src = Path(context.src_dir) / "wrappers" / f"{cc}.py"
    cmd = [cc_src, "run_first"]
    run_first = subprocess.check_output(cmd).decode(sys.stdout.encoding).strip()
    if run_first == "receiver":
        run_second = "sender"
    elif run_first == "sender":
        run_second = "receiver"
    else:
        sys.exit('Must specify "receiver" or "sender" runs first')
    return run_first, run_second
