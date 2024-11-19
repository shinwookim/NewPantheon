import os
import subprocess
import sys
from signal import SIGTERM

from .logger import log_print


def print_cmd(cmd):
    if isinstance(cmd, list):
        cmd_to_print = " ".join(cmd).strip()
    elif isinstance(cmd, str):
        cmd_to_print = cmd.strip()
    else:
        cmd_to_print = ""

    if cmd_to_print:
        log_print(f"$ {cmd_to_print}")


def Popen(cmd, **kwargs) -> subprocess.Popen:
    print_cmd(cmd)
    return subprocess.Popen(cmd, **kwargs)


def call(cmd, **kwargs):
    print_cmd(cmd)
    return subprocess.call(cmd, **kwargs)


def check_call(cmd, **kwargs):
    print_cmd(cmd)
    return subprocess.check_call(cmd, **kwargs)


def check_output(cmd, **kwargs):
    print_cmd(cmd)
    return subprocess.check_output(cmd, **kwargs)


def write_stdin(proc, msg):
    proc.stdin.write(msg.encode("ascii"))
    proc.stdin.flush()


def read_stdout(proc) -> str:
    return proc.stdout.readline().decode("ascii")


def kill_proc_group(proc, signum=SIGTERM):
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
