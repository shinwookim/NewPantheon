#!/usr/bin/env python3
import os
import sys

from signal import signal, SIGINT, SIGTERM
from os import path, setsid
from subprocess import Popen, PIPE

import newpantheon.common.process_manager

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
print(SCRIPT_DIR)

sys.path.append(os.path.dirname(SCRIPT_DIR))


def start():
    prompt = None
    procs = {}

    # register SIGINT and SIGTERM events to clean up gracefully before quit
    def stop_signal_handler(signum, frame):
        for tun_id in procs:
            newpantheon.common.process_manager.kill_proc_group(procs[tun_id])

        sys.exit("tunnel_manager: caught signal %s and cleaned up\n" % signum)

    signal(SIGINT, stop_signal_handler)
    signal(SIGTERM, stop_signal_handler)

    sys.stdout.write("tunnel manager is running\n")
    sys.stdout.flush()

    while True:
        input_command = sys.stdin.readline().strip()

        # Log all the commands fed into tunnel manager
        if prompt:
            print(f"{prompt} {input_command}", file=sys.stderr)
        else:
            print(f"{input_command}", file=sys.stderr)

        commands = input_command.split()

        # Manage I/O of multiple tunnels
        if len(commands) == 0:
            continue
        elif commands[0] == "tunnel":
            if len(commands) < 3:
                print("error: not enough arguments\n\tusage: ID CMD...")
                continue
            try:
                tun_id = int(commands[1])
            except ValueError:
                print("error: invalid argument\n\tusage: ID CMD...")
                continue

            commands_to_run = " ".join(commands[2:])

            if commands[2] in {"mm-tunnelclient", "mm-tunnelserver"}:
                commands_to_run = path.expandvars(commands_to_run).split()

                # Expand environment variables and home directory
                commands_to_run = [
                    (
                        path.expanduser(part)
                        if "--ingress-log" in part or "--egress-log" in part
                        else part
                    )
                    for part in commands_to_run
                ]

                procs[tun_id] = Popen(
                    commands_to_run, stdin=PIPE, stdout=PIPE, preexec_fn=setsid
                )
            elif commands[2] == "python":  # Run Python scripts inside tunnel
                if tun_id not in procs:
                    print("error: run tunnel client or server first", file=sys.stderr)
                procs[tun_id].stdin.write(
                    commands_to_run.encode(encoding=sys.stdin.encoding) + b"\n"
                )
                procs[tun_id].stdin.flush()
            elif commands[2] == "readline":  # Run readline from standard out of tunnel
                if len(commands) != 3:
                    print("error: usage: tunnel ID readline\n", file=sys.stderr)
                    continue
                if tun_id not in procs:
                    print("error: run tunnel client or server first\n", file=sys.stderr)
                print(
                    procs[tun_id].stdout.readline().decode(sys.stdout.encoding),
                    flush=True,
                )
            else:
                print(
                    f'unknown command after "tunnel ID": {commands_to_run}\n',
                    file=sys.stderr,
                )
                continue
        elif commands[0] == "prompt":  # Set prompt in front of commands to print
            if len(commands) != 2:
                print("error: usage: prompt PROMPT\n", file=sys.stderr)
                continue
            prompt = commands[1].strip()
        elif commands[0] == "halt":  # Terminate all tunnel processes and quit
            if len(commands) != 1:
                print("error: usage: halt\n", file=sys.stderr)
                continue
            for tun_id in procs:
                newpantheon.common.process_manager.kill_proc_group(procs[tun_id])
            sys.exit(0)
        else:
            print(f"unknown command: {input_command}\n", file=sys.stderr)
            continue


if __name__ == "__main__":
    start()
