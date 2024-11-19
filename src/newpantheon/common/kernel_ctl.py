import sys
from .process_manager import call, check_output, check_call


def load_kernel_module(module: str) -> None:
    """Loads a kernel module, exists if it fails."""
    if call(f"sudo modprobe {module}", shell=True) != 0:
        sys.exit(f"Failed while loading kernel module {module}")


def enable_congestion_control(cc):
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
    curr_qdisc = check_output("sysctl net.core.default_qdisc", shell=True)
    curr_qdisc = curr_qdisc.split("=")[-1].strip()

    if qdisc != curr_qdisc:
        sys.exit("Error: current qdisc %s is not %s" % (curr_qdisc, qdisc))


def set_qdisc(qdisc):
    curr_qdisc = check_output("sysctl net.core.default_qdisc", shell=True)
    curr_qdisc = curr_qdisc.split("=")[-1].strip()

    if curr_qdisc != qdisc:
        check_call("sudo sysctl -w net.core.default_qdisc=%s" % qdisc, shell=True)
        sys.stderr.write("Changed default_qdisc from %s to %s\n" % (curr_qdisc, qdisc))


def enable_ip_forwarding():
    check_call("sudo sysctl -w net.ipv4.ip_forward=1", shell=True)


def disable_rp_filter(interface):
    rpf = "net.ipv4.conf.%s.rp_filter"

    check_call("sudo sysctl -w %s=0" % (rpf % interface), shell=True)
    check_call("sudo sysctl -w %s=0" % (rpf % "all"), shell=True)
