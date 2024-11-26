#!/usr/bin/env python3
from typing import List

from cc_wraper import RunFirst, CCScheme, run_scheme


class CC(CCScheme):
    def get_deps(self) -> List[str]:
        return ["iperf"]

    def setup_first_time(self):
        pass

    def setup_on_reboot(self):
        pass

    def get_receiver_command(self, args) -> List[str]:
        return ["iperf", "-Z", "cubic", "-s", "-p", args.port]

    def get_sender_command(self, args) -> List[str]:
        return ["iperf", "-Z", "cubic", "-c", args.ip, "-p", args.port, "-t", "75"]


if __name__ == "__main__":
    scheme = CC()
    run_scheme(scheme, RunFirst.receiver)
