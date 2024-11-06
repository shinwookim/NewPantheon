#!/usr/bin/env python


from signal import signal, SIGINT, SIGTERM

import os
import sys
from os import path
from subprocess import Popen, PIPE

# register SIGINT and SIGTERM events to clean up gracefully before quit
def stop_signal_handler(signum, frame):
    for tun_id in procs:
        utils.kill_proc_group(procs[tun_id])
    sys.exit('tunnel_manager: caught signal %s and cleaned up\n' % signum)


def main():
    prompt = None
    procs = {}

    signal(SIGINT, stop_signal_handler)
    signal(SIGTERM, stop_signal_handler)

    print('Tunnel Manager is Running...')

    while True:
        # Read input command
        input_command = sys.stdin.readline().strip()

        # print all the commands fed into tunnel manager
        if prompt:
            print(f"{prompt} {input_command}", file=sys.stderr)
        else:
            print(input_command, file=sys.stderr)
        command = input_command.split()

        # manage I/O of multiple tunnels
        if command[0] == 'tunnel':
            if len(command) < 3:
                sys.stderr.write('error: usage: tunnel ID CMD...\n')
                print("""error: not enough arguments
                usage: tunnel ID CMD...""", file=sys.stderr)
                continue

            try:
                tun_id = int(cmd[1])
            except ValueError:
                sys.stderr.write('error: usage: tunnel ID CMD...\n')
                continue

            cmd_to_run = ' '.join(cmd[2:])

            if cmd[2] == 'mm-tunnelclient' or cmd[2] == 'mm-tunnelserver':
                # expand env variables (e.g., MAHIMAHI_BASE)
                cmd_to_run = path.expandvars(cmd_to_run).split()

                # expand home directory
                for i in xrange(len(cmd_to_run)):
                    if ('--ingress-log' in cmd_to_run[i] or
                            '--egress-log' in cmd_to_run[i]):
                        t = cmd_to_run[i].split('=')
                        cmd_to_run[i] = t[0] + '=' + path.expanduser(t[1])

                procs[tun_id] = Popen(cmd_to_run, stdin=PIPE,
                                      stdout=PIPE, preexec_fn=os.setsid)
            elif cmd[2] == 'python':  # run python scripts inside tunnel
                if tun_id not in procs:
                    sys.stderr.write(
                        'error: run tunnel client or server first\n')

                procs[tun_id].stdin.write(cmd_to_run + '\n')
                procs[tun_id].stdin.flush()
            elif cmd[2] == 'readline':  # readline from stdout of tunnel
                if len(cmd) != 3:
                    sys.stderr.write('error: usage: tunnel ID readline\n')
                    continue

                if tun_id not in procs:
                    sys.stderr.write(
                        'error: run tunnel client or server first\n')

                sys.stdout.write(procs[tun_id].stdout.readline())
                sys.stdout.flush()
            else:
                sys.stderr.write('unknown command after "tunnel ID": %s\n'
                                 % cmd_to_run)
                continue
        elif cmd[0] == 'prompt':  # set prompt in front of commands to print
            if len(cmd) != 2:
                sys.stderr.write('error: usage: prompt PROMPT\n')
                continue

            prompt = cmd[1].strip()
        elif cmd[0] == 'halt':  # terminate all tunnel processes and quit
            if len(cmd) != 1:
                sys.stderr.write('error: usage: halt\n')
                continue

            for tun_id in procs:
                utils.kill_proc_group(procs[tun_id])

            sys.exit(0)
        else:
            sys.stderr.write('unknown command: %s\n' % input_cmd)
            continue


def start():
    raise NotImplemented


if __name__ == "__main__":
    start()
