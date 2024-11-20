"""Various utility functions used throughout Pantheon"""

from datetime import datetime, timezone
import subprocess
import sys
import socket
from os import path
from tempfile import NamedTemporaryFile
from pathlib import Path

from . import context


def get_git_summary(mode="local", remote_path=None):
    git_summary_shell_script = b"""#!/bin/sh
echo -n 'branch: '
git rev-parse --abbrev-ref @ | head -c -1
echo -n ' @ '
git rev-parse @
git submodule foreach --quiet 'echo $path @ `git rev-parse @`; git status -s --untracked-files=no --porcelain'
"""
    with NamedTemporaryFile(delete=True) as temp_file:
        temp_file.write(git_summary_shell_script)
        temp_file.flush()
        temp_file.seek(0)
        git_summary_src = Path(temp_file.name)
        subprocess.run(
            ["chmod", "+x", git_summary_src], check=False
        )  # Make the file executable
        try:
            local_git_summary = subprocess.run(
                ["sh", git_summary_src],
                capture_output=True,
                text=True,
                cwd=context.base_dir,
                check=True,
            ).stdout
        except subprocess.SubprocessError as e:
            print(f"An error occurred while executing the script: {e}", file=sys.stderr)

        if mode == "remote":
            parsed_path = parse_remote_path(remote_path)
            ssh_cmd = f"{' '.join(parsed_path['ssh_cmd'])} cd {parsed_path['base_dir']}; {git_summary_src}"
            remote_git_summary = subprocess.run(
                ssh_cmd, capture_output=True, text=True, check=True
            ).stdout
            if local_git_summary != remote_git_summary:
                print(
                    f"""
                --- LOCAL GIT SUMMARY ---
                {local_git_summary}

                --- REMOTE GIT SUMMARY ---
                {remote_git_summary}
                """,
                    file=sys.stderr,
                )
                sys.exit("Repository differs between local and remote")
        return local_git_summary


def get_open_port():
    sock = socket.socket(socket.AF_INET)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    sock.bind(("", 0))
    port = sock.getsockname()[1]
    sock.close()
    return str(port)


class TimeoutError(Exception):
    pass


def timeout_handler(signum, frame):
    raise TimeoutError()


def utc_time():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def parse_remote_path(remote_path, cc=None):
    ret = {
        "host_addr": (remote_path.rsplit(":", 1))[0],
        "base_dir": (remote_path.rsplit(":", 1))[1],
    }
    ret["src_dir"] = path.join(ret["base_dir"], "src")
    ret["tmp_dir"] = path.join(ret["base_dir"], "tmp")
    ret["ip"] = ret["host_addr"].split("@")[-1]
    ret["ssh_cmd"] = ["ssh", ret["host_addr"]]
    ret["tunnel_manager"] = path.join(
        ret["src_dir"], "experiments", "tunnel_manager.py"
    )
    if cc is not None:
        ret["cc_src"] = path.join(ret["src_dir"], "newpantheon", "wrappers", f"{cc}.py")
    return ret
