from os import path
import sys
from typing import List

from newpantheon.common import process_manager
from newpantheon.common.logger import log_print
from newpantheon.experiments.test import parse_config_file
from newpantheon.wrappers.cc_wraper import CCScheme
from newpantheon.common import context


def install_dependencies(cc_src) -> None:
    """Install dependencies as specified in congestion control wrapper"""
    dependencies = (
        process_manager.check_output([cc_src, "deps"])
        .decode(sys.stdout.encoding)
        .strip()
    )
    if dependencies:
        if (
            process_manager.call(f"sudo apt-get -y install {dependencies}", shell=True)
        ) != 0:
            log_print(
                "Some dependencies failed to install. We're going to assume things are okay."
            )


def run_setup(args) -> None:
    # update submodules
    cc_schemes: List = []

    if args.all:
        cc_schemes = parse_config_file(context.default_config_location)[
            "schemes"
        ].keys()
    elif args.schemes is not None:
        cc_schemes = args.schemes.split()
    else:
        return

    for cc in cc_schemes:
        cc_src = path.join(context.src_dir, "wrappers", f"{cc}.py")
        if args.install_deps:
            install_dependencies(cc_src)
        else:
            if args.setup:
                process_manager.check_call([cc_src, "setup"])

            # setup required every time after reboot
            if process_manager.call([cc_src, "setup_after_reboot"]) != 0:
                log_print(
                    f"Warning: {cc}.py setup_after_reboot failed."
                    "We're going to assume things are okay."
                )
