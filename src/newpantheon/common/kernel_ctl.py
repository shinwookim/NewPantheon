"""
Helper functions for dealing with OS modules and changing settings.
Mostly used by each congestion control algorithm wrapper.
"""

import sys
from .process_manager import call, check_output, check_call
from .logger import log_print


def load_kernel_module(module: str) -> None:
    """Loads a kernel module, exists if it fails."""
    if call(f"sudo modprobe {module}", shell=True) != 0:
        sys.exit(f"Failed while loading kernel module {module}")


def enable_congestion_control(cc) -> None:
    """Adds a congestion control algorithm to allowed list"""
    cc_list = check_output("sysctl net.ipv4.tcp_allowed_congestion_control", shell=True)
    cc_list = cc_list.split("=")[-1].split()

    # return if cc is already in the allowed congestion control list
    if cc in cc_list:
        return

    cc_list.append(cc)
    check_call(
        f'sudo sysctl -w net.ipv4.tcp_allowed_congestion_control="{" ".join(cc_list)}"',
        shell=True,
    )


def check_qdisc(qdisc):
    """Checks that a queuing discipline is set to default"""
    curr_qdisc = check_output("sysctl net.core.default_qdisc", shell=True)
    curr_qdisc = curr_qdisc.split("=")[-1].strip()

    if qdisc != curr_qdisc:
        sys.exit(f"Error: current qdisc {curr_qdisc} is not {qdisc}")


def set_qdisc(qdisc):
    """Sets a queuing discipline to default"""
    curr_qdisc = check_output("sysctl net.core.default_qdisc", shell=True)
    curr_qdisc = curr_qdisc.split("=")[-1].strip()

    if curr_qdisc != qdisc:
        check_call(f"sudo sysctl -w net.core.default_qdisc={qdisc}", shell=True)
        log_print(f"Changed default_qdisc from {curr_qdisc} to {qdisc}")


def enable_ip_forwarding():
    """Enables IPV4 IP Forwarding"""
    check_call("sudo sysctl -w net.ipv4.ip_forward=1", shell=True)


def disable_rp_filter(interface):
    """
    Disables reverse path filtering
    See: https://sysctl-explorer.net/net/ipv4/rp_filter/
    """
    rpf = "net.ipv4.conf.%s.'rp_filter'"

    check_call(f"sudo sysctl -w {rpf % interface}=0", shell=True)
    check_call(f"sudo sysctl -w {rpf % "all"}=0", shell=True)
