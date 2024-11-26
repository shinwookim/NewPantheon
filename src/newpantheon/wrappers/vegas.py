#!/usr/bin/env python3
from typing import List

from cc_wraper import RunFirst, CCScheme, run_scheme
from newpantheon.common import kernel_ctl


def setup_vegas():
    # load tcp_vegas kernel module
    kernel_ctl.load_kernel_module("tcp_vegas")

    # add vegas to kernel-allowed congestion control list
    kernel_ctl.enable_congestion_control("vegas")
    pass


class CC(CCScheme):
    def get_deps(self) -> List[str]:
        return ["iperf"]

    def setup_first_time(self):
        pass

    def setup_on_reboot(self):
        setup_vegas()

    def get_receiver_command(self, args) -> List[str]:
        return ["iperf", "-Z", "vegas", "-s", "-p", args.port]

    def get_sender_command(self, args) -> List[str]:
        return ["iperf", "-Z", "vegas", "-c", args.ip, "-p", args.port, "-t", "75"]


if __name__ == "__main__":
    scheme = CC()
    run_scheme(scheme, RunFirst.receiver)
