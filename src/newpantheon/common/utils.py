from datetime import datetime
import os
import subprocess
import sys
from signal import SIGTERM
import socket
from tempfile import NamedTemporaryFile
from pathlib import Path

import yaml

from . import context

tmp_dir = os.path.join(context.base_dir, 'tmp')

def kill_proc_group(proc, signum=SIGTERM):
    if not proc:
        return
    try:
        print(f"kill_proc_group: killed process group with pgid {os.getpgid(proc.pid)}", file=sys.stderr)
        os.killpg(proc.pid, signum)
    except OSError as e:
        print(f"kill_proc_group: failed to kill process group {e}", file=sys.stderr)


def parse_remote_path(remote_path, cc=None):
    ret = {'host_addr': (remote_path.rsplit(':', 1))[0], 'base_dir': (remote_path.rsplit(':', 1))[1]}

    ret['src_dir'] = Path(ret['base_dir']) / 'src'
    ret['tmp_dir'] = Path(ret['base_dir']) / 'tmp'
    ret['ip'] = ret['host_addr'].split('@')[-1]
    ret['ssh_cmd'] = ['ssh', ret['host_addr']]
    ret['tunnel_manager'] = Path(ret['src_dir']) / 'experiments' / 'tunnel_manager.py'
    if cc is not None:
        ret['cc_src'] = Path(ret['src_dir']) / 'newpantheon' / 'wrappers' / (cc + ".py")
    return ret


def get_git_summary(mode='local', remote_path=None):
    GIT_SUMMARY_SHELL_SCRIPT = b"""#!/bin/sh

echo -n 'branch: '
git rev-parse --abbrev-ref @ | head -c -1
echo -n ' @ '
git rev-parse @
git submodule foreach --quiet 'echo $path @ `git rev-parse @`; git status -s --untracked-files=no --porcelain'
"""
    with NamedTemporaryFile(delete=True) as temp_file:
        temp_file.write(GIT_SUMMARY_SHELL_SCRIPT)
        temp_file.flush()
        temp_file.seek(0)

        git_summary_src = Path(temp_file.name)

        # Make the file executable
        subprocess.run(["chmod", "+x", git_summary_src])

        try:
            local_git_summary = subprocess.run(["sh", git_summary_src], capture_output=True, text=True,
                                               cwd=context.base_dir).stdout
        except subprocess.SubprocessError as e:
            print(f"An error occurred while executing the script: {e}", file=sys.stderr)

        if mode == 'remote':
            parsed_path = parse_remote_path(remote_path)
            ssh_cmd = f"{' '.join(parsed_path['ssh_cmd'])} cd {parsed_path['base_dir']}; {git_summary_src}"
            remote_git_summary = subprocess.run(ssh_cmd, capture_output=True, text=True).stdout

            if local_git_summary != remote_git_summary:
                print(f"""
                --- LOCAL GIT SUMMARY ---
                {local_git_summary}
                
                --- REMOTE GIT SUMMARY ---
                {remote_git_summary}
                """, file=sys.stderr)
                sys.exit("Repository differs between local and remote")
        return local_git_summary


def who_runs_first(cc):
    cc_src = Path(context.src_dir) / 'wrappers' / (cc + '.py')

    cmd = [cc_src, 'run_first']
    run_first = subprocess.check_output(cmd).decode(sys.stdout.encoding).strip()
    if run_first == 'receiver':
        run_second = 'sender'
    elif run_first == 'sender':
        run_second = 'receiver'
    else:
        sys.exit('Must specify "receiver" or "sender" runs first')

    return run_first, run_second


def get_open_port():
    sock = socket.socket(socket.AF_INET)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    sock.bind(('', 0))
    port = sock.getsockname()[1]
    sock.close()
    return str(port)


class TimeoutError(Exception):
    pass


def timeout_handler(signum, frame):
    raise TimeoutError()
def utc_time():
    return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')