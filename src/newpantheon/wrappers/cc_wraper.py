from abc import ABC, abstractmethod

from enum import StrEnum, auto
from typing import List


class RunFirst(StrEnum):
    receiver = auto()
    sender = auto()


class CCScheme(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def get_deps(self) -> str:
        pass

    @abstractmethod
    def setup_first_time(self):
        pass

    @abstractmethod
    def setup_on_reboot(self):
        pass

    @abstractmethod
    def get_receiver_command(self, args) -> List[str]:
        pass

    @abstractmethod
    def get_sender_command(self, args) -> List[str]:
        pass


def run_scheme(cc: CCScheme, run_first: RunFirst):
    from subprocess import check_call
    import arg_parser

    match run_first:
        case RunFirst.sender:
            pass
        case RunFirst.receiver:
            pass

    args = arg_parser.receiver_first()

    if args.option == 'deps':
        print(cc.get_deps())
        return

    if args.option == 'receiver':
        cmd = cc.get_receiver_command(args)
        check_call(cmd)
        return

    if args.option == 'sender':
        cmd = cc.get_sender_command(args)
        check_call(cmd)
        return
