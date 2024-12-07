#!/usr/bin/env python3
import os.path
import os
import sys
from enum import Enum, auto
from pathlib import Path
from signal import signal, SIGINT, SIGTERM
from subprocess import Popen, PIPE
from dataclasses import dataclass
from typing import List, Optional, Dict

from newpantheon.common.logger import log_print
from newpantheon.common.process_manager import kill_proc_group, write_stdin, read_stdout


class CommandType(Enum):
    TUNNEL = auto()
    PROMPT = auto()
    HALT = auto()
    UNKNOWN = auto()


@dataclass
class Command:
    type: CommandType
    args: List[str]


class TunnelManager:
    def __init__(self):
        self.prompt: Optional[str] = None
        self.processes: Dict[int, Popen] = {}

    def signal_cleanup(self, signum):
        for t_id, proc in self.processes.items():
            kill_proc_group(proc)
        sys.exit(f"[Tunnel Manager]: Caught signal {signum} and cleaned up\n")

    def log(self, message: str) -> None:
        """Log a message with the current prompt if set."""
        if self.prompt:
            log_print(f"{self.prompt} {message}")

    def parse_command(self, input_line: str) -> Command:
        """Parse input line into a Command object."""
        parts = input_line.strip().split()
        if not parts:
            return Command(CommandType.UNKNOWN, [])
        command_type = {
            "tunnel": CommandType.TUNNEL,
            "prompt": CommandType.PROMPT,
            "halt": CommandType.HALT,
        }.get(parts[0], CommandType.UNKNOWN)
        return Command(command_type, parts[1:])

    def handle_tunnel_command(self, args: List[str]):
        """Handle tunnel-related commands."""
        if len(args) < 2:
            log_print("error: not enough arguments\n\tUsage: ID CMD...")
            return
        try:
            tunnel_id = int(args[0])
        except ValueError:
            log_print("error: invalid argument\n\tUsage: ID CMD...")
            return
        command = " ".join(args[1:])
        if args[1] in {"mm-tunnelclient", "mm-tunnelserver"}:
            self._handle_tunnel_process(tunnel_id, command)
        elif args[1] == "python":
            self._handle_python_command(tunnel_id, command)
        elif args[1] == "readline":
            self._handle_readline_command(tunnel_id)

    def _handle_tunnel_process(self, tunnel_id: int, command: str):
        """Starts a new process in the tunnel."""
        command_parts = os.path.expandvars(command).split()
        for i, part in enumerate(command_parts):
            if any(flag in part for flag in ("--ingress-log", "--egress-log")):
                name, value = part.split("=", 1)
                command_parts[i] = f"{name}={str(Path(value).expanduser())}"
        self.processes[tunnel_id] = Popen(
            command_parts, stdin=PIPE, stdout=PIPE, preexec_fn=os.setsid
        )

    def _handle_python_command(self, tunnel_id: int, command: str):
        """Execute python command in the tunnel."""
        if tunnel_id not in self.processes:
            log_print("error: run tunnel client or server first")
            return
        write_stdin(self.processes[tunnel_id], f"{command}\n")

    def _handle_readline_command(self, tunnel_id: int):
        """Read output from tunnel."""
        if tunnel_id not in self.processes:
            log_print("error: run tunnel client or server first")
            return
        print(read_stdout(self.processes[tunnel_id]), flush=True)

    def handle_prompt_command(self, args: List[str]) -> None:
        if len(args) != 1:
            log_print("error: usage: prompt PROMPT")
            return
        self.prompt = args[0].strip()

    def handle_halt_command(self, args: List[str]) -> None:
        if args:
            log_print("error: usage: halt")
            return
        for process in self.processes.values():
            kill_proc_group(process)
        sys.exit(0)

    def run(self) -> None:
        """Main Event Loop."""
        while True:
            try:
                input_line = sys.stdin.readline().strip()
                log_print(f"[Tunnel Manager {self.prompt}] Got Input: {input_line}")
                command = self.parse_command(input_line)
                handlers = {
                    CommandType.TUNNEL: lambda: self.handle_tunnel_command(
                        command.args
                    ),
                    CommandType.PROMPT: lambda: self.handle_prompt_command(
                        command.args
                    ),
                    CommandType.HALT: lambda: self.handle_halt_command(command.args),
                    CommandType.UNKNOWN: lambda: print(
                        f"unknown command: {input_line}", file=sys.stderr
                    ),
                }
                handlers[command.type]()
            except Exception as e:
                log_print(f"error: {str(e)}")


manager = TunnelManager()


def stop_signal_handler(signum, frame):
    manager.signal_cleanup(signum)


def main():
    signal(SIGINT, stop_signal_handler)
    signal(SIGTERM, stop_signal_handler)
    print("tunnel manager is running", flush=True)
    manager.run()


if __name__ == "__main__":
    main()
