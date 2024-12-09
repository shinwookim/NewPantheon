"""
Wrapper around the standard subprocess module.
Prints command before calling subprocess equivalent.
"""

import os
import subprocess
import sys
from signal import SIGTERM
import select
import time
from .logger import log_print
import re


def print_cmd(cmd) -> None:
    """Prints command to standard error using log_print"""
    if isinstance(cmd, list):
        cmd_to_print = " ".join(cmd).strip()
    elif isinstance(cmd, str):
        cmd_to_print = cmd.strip()
    else:
        cmd_to_print = ""

    if cmd_to_print:
        log_print(f"$ {cmd_to_print}")


def Popen(cmd, **kwargs) -> subprocess.Popen:
    """subprocess.Popen equivalent"""
    print_cmd(cmd)
    return subprocess.Popen(cmd, **kwargs)


def call(cmd, **kwargs):
    """subprocess.call equivalent"""
    print_cmd(cmd)
    return subprocess.call(cmd, **kwargs)


def check_call(cmd, **kwargs):
    """subprocess.check_call equivalent"""
    print_cmd(cmd)
    return subprocess.check_call(cmd, **kwargs)


def check_output(cmd, **kwargs):
    """subprocess.check_output equivalent"""
    print_cmd(cmd)
    return subprocess.check_output(cmd, text=True, **kwargs)


def write_stdin(proc, msg) -> None:
    """Write to process proc's standard input and flush"""
    proc.stdin.write(msg.encode(sys.stdin.encoding))
    proc.stdin.flush()


def read_stdout(proc, nul_term=None) -> str:
    """Read from process proc's standard output"""
    read_line = proc.stdout.readline().decode(sys.stdout.encoding)
    stdout = [read_line]
    if nul_term is not None:
        while read_line[-2] != nul_term:
            read_line = proc.stdout.readline().decode(sys.stdout.encoding)
            stdout.append(re.sub(r"#", '', read_line))
        read_line = re.sub(r"#", '', read_line)
        return " ".join(stdout)
    else:
        return re.sub(r"#", '', read_line)

def kill_proc_group(proc, signum=SIGTERM) -> None:
    """Kill all processes in the same group as proc by sending a signal"""
    if not proc:
        return
    try:
        print(
            f"kill_proc_group: killed process group with pgid {os.getpgid(proc.pid)}",
            file=sys.stderr,
        )
        os.killpg(proc.pid, signum)
    except OSError as e:
        print(f"kill_proc_group: failed to kill process group {e}", file=sys.stderr)
