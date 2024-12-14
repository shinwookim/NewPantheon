"""Various utility functions used throughout Pantheon"""

from datetime import datetime, timezone
import json
import platform
import subprocess
import sys
import socket
import os
import errno
from os import path
from tempfile import NamedTemporaryFile
from pathlib import Path

import yaml

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


def make_sure_dir_exists(d):
    try:
        os.makedirs(d)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise


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

def load_test_metadata(metadata_path):
    with open(metadata_path) as metadata:
        return json.load(metadata)
    
def parse_config():
    with open(path.join(context.src_dir, 'config.yml')) as config:
        return yaml.load(config, Loader=yaml.Loader)
    
def verify_schemes_with_meta(schemes, meta):
    schemes_config = parse_config()['schemes']

    all_schemes = meta['cc_schemes']
    if schemes is None:
        cc_schemes = all_schemes
    else:
        cc_schemes = schemes.split()

    for cc in cc_schemes:
        if cc not in all_schemes:
            sys.exit('%s is not a scheme included in '
                     'pantheon_metadata.json' % cc)
        if cc not in schemes_config:
            sys.exit('%s is not a scheme included in src/config.yml' % cc)

    return cc_schemes

def get_sys_info():
    sys_info = ''

    # Check the system type
    if platform.system() == 'Darwin':  # macOS
        sys_info += subprocess.check_output(['uname', '-sr']).decode("utf-8")
        sys_info += "macOS does not support 'net.core.default_qdisc'\n"
    else:  # Linux
        try:
            sys_info += subprocess.check_output(['sysctl', 'net.core.default_qdisc']).decode("utf-8")
            sys_info += subprocess.check_output(['sysctl', 'net.core.rmem_default']).decode("utf-8")
            sys_info += subprocess.check_output(['sysctl', 'net.core.rmem_max']).decode("utf-8")
            sys_info += subprocess.check_output(['sysctl', 'net.core.wmem_default']).decode("utf-8")
            sys_info += subprocess.check_output(['sysctl', 'net.core.wmem_max']).decode("utf-8")
            sys_info += subprocess.check_output(['sysctl', 'net.ipv4.tcp_rmem']).decode("utf-8")
            sys_info += subprocess.check_output(['sysctl', 'net.ipv4.tcp_wmem']).decode("utf-8")
        except subprocess.CalledProcessError as e:
            print(f"Error running sysctl command: {e}")
            sys_info += "Error: Unable to retrieve sysctl information\n"

    return sys_info