from abc import ABC, abstractmethod
from enum import StrEnum, auto
from typing import List
import sys

from ..common.process_manager import check_call
from . import arg_parser


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

    match run_first:
        case RunFirst.sender:
            args = arg_parser.parse_wrapper_args("sender")
        case RunFirst.receiver:
            args = arg_parser.parse_wrapper_args("receiver")
        case _:
            sys.exit("Must specify sender or receiver")

    if args.option == "deps":
        print(cc.get_deps())
        return

    if args.option == "receiver":
        cmd = cc.get_receiver_command(args)
        check_call(cmd)
        return

    if args.option == "sender":
        cmd = cc.get_sender_command(args)
        check_call(cmd)
        return
