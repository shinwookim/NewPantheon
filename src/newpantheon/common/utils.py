import os
import sys
from signal import SIGTERM


def kill_proc_group(proc, signum=SIGTERM):
    if not proc:
        return
    try:
        print(f"kill_proc_group: killed process group with pgid {os.getpgid(proc.pid)}", file=sys.stderr)
        os.killpg(proc.pid, signum)
    except OSError as e:
        print(f"kill_proc_group: failed to kill process group {e}", file=sys.stderr)
