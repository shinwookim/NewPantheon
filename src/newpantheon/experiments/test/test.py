import os
import signal
import time
import uuid
from os import path
from subprocess import PIPE
from typing import List

from newpantheon.experiments.test import helpers
from newpantheon.experiments.test.flow import Flow
from newpantheon.common import context, utils
from newpantheon.common.logger import log_print
from newpantheon.common.process_manager import (
    Popen,
    write_stdin,
    read_stdout,
    call,
    kill_proc_group,
)


class Test:
    def __init__(self, args, run_id, cc):
        self.mode = args.mode
        self.run_id = run_id
        self.cc = cc
        self.data_dir: str = path.abspath(args.data_dir)

        # Shared (remote/local) arguments
        self.flows = args.flows  # number of flows
        self.runtime = args.runtime  # total runtime (sec)
        self.interval = args.interval  # interval between two flows (secs)
        self.run_times = args.run_times  # run-times of each scheme

        self.cc_src: str = ""
        self.tunnel_manager: str = ""
        self.run_first = None
        self.run_second = None
        self.run_first_setup_time = None
        self.run_first_setup_time = None
        self.datalink_name = None
        self.acklink_name = None
        self.datalink_log = None
        self.acklink_log = None
        self.datalink_ingress_logs = {}
        self.datalink_egress_logs = {}
        self.acklink_ingress_logs = {}
        self.acklink_egress_logs = {}

        # Used for cleanup
        self.first_process = None
        self.second_process = None
        self.ts_manager = None
        self.tc_manager = None

        self.test_start_time = None
        self.test_end_time = None

        if self.mode == "local":
            self.datalink_trace: str = args.uplink_trace
            self.acklink_trace: str = args.downlink_trace

            self.mm_cmd = []
            self.prepend_mm_cmds: str = args.prepend_mm_cmds
            self.append_mm_cmds: str = args.append_mm_cmds
            self.extra_mm_link_args: str = args.extra_mm_link_args
            self.mm_datalink_log: str = ""
            self.mm_acklink_log: str = ""

            # for convenience
            self.sender_side: str = "remote"
            self.server_side: str = "local"

            # remote mode
        if self.mode == "remote":
            self.sender_side = args.sender_side
            self.server_side = args.server_side
            self.local_addr = args.local_addr
            self.local_if = args.local_if
            self.remote_if = args.remote_if
            self.local_desc = args.local_desc
            self.remote_desc = args.remote_desc

            self.ntp_addr = args.ntp_addr
            self.local_offset = None
            self.remote_offset = None

            self.remote = utils.parse_remote_path(args.remote_path, self.cc)

        self.test_config = args.test_config if hasattr(args, "test_config") else None

        if self.test_config is not None:
            self.cc = self.test_config["test-name"]

            cc_src_remote_dir = self.remote["base_dir"] if self.mode == "remote" else ""

            self.flow_objs = {}
            tun_id = 1
            for flow in self.test_config["flows"]:
                cc = flow["scheme"]
                run_first, run_second = helpers.who_runs_first(cc)
                self.flow_objs[tun_id] = Flow(
                    cc=cc,
                    cc_src_local=str(context.src_dir / "wrappers" / f"{cc}.py"),
                    cc_src_remote=path.join(cc_src_remote_dir, "wrappers", f"{cc}.py"),
                    run_first=run_first,
                    run_second=run_second,
                )
                tun_id = tun_id + 1

    def setup_mm_cmd(self):
        """Setup commands for MahiMahi"""
        self.mm_datalink_log = path.join(
            self.data_dir, f"{self.cc}_mm_datalink_run{self.run_id}.log"
        )
        self.mm_acklink_log = path.join(
            self.data_dir, f"{self.cc}_mm_acklink_run{self.run_id}.log"
        )

        if self.run_first == "receiver" or self.flows > 0:
            # Receiver runs first OR test WITH Pantheon Tunnel
            uplink_log, downlink_log = self.mm_datalink_log, self.mm_acklink_log
            uplink_trace, downlink_trace = self.datalink_trace, self.acklink_trace
        else:
            # Sender runs first AND test runs WITHOUT Pantheon Tunnel
            uplink_log, downlink_log = self.mm_acklink_log, self.mm_datalink_log
            uplink_trace, downlink_trace = self.acklink_trace, self.datalink_trace

        if self.prepend_mm_cmds:
            self.mm_cmd = self.mm_cmd + self.prepend_mm_cmds.split()

        self.mm_cmd = self.mm_cmd + [
            "mm-link",
            uplink_trace,
            downlink_trace,
            f"--uplink-log={uplink_log}",
            f"--downlink-log={downlink_log}",
        ]

        if self.extra_mm_link_args:
            self.mm_cmd = self.mm_cmd + self.extra_mm_link_args.split()

        if self.append_mm_cmds:
            self.mm_cmd = self.mm_cmd + self.append_mm_cmds.split()

    def prepare_tunnel_log_paths(self):
        """Ensure logs have correct local and remote paths"""
        # TODO: Find a better location/ensure this directory exists
        local_temp_dir = context.base_dir / "tmp"
        local_temp_dir.mkdir(parents=False, exist_ok=True)

        for tun_id in range(1, self.flows + 1):
            uid = uuid.uuid4()
            datalink_ingress_log_name = (
                f"{self.datalink_name}_flow{tun_id}_uid{uid}.log.ingress"
            )
            datalink_egress_log_name = (
                f"{self.datalink_name}_flow{tun_id}_uid{uid}.log.egress"
            )
            acklink_ingress_log_name = (
                f"{self.acklink_name}_flow{tun_id}_uid{uid}.log.ingress"
            )
            acklink_egress_log_name = (
                f"{self.acklink_name}_flow{tun_id}_uid{uid}.log.egress"
            )
            self.datalink_ingress_logs[tun_id] = str(
                local_temp_dir / datalink_ingress_log_name
            )
            self.datalink_egress_logs[tun_id] = str(
                local_temp_dir / datalink_egress_log_name
            )
            self.acklink_ingress_logs[tun_id] = str(
                local_temp_dir / acklink_ingress_log_name
            )
            self.acklink_egress_logs[tun_id] = str(
                local_temp_dir / acklink_egress_log_name
            )

            if self.mode == "remote":
                remote_temp_dir = self.remote["temp_dir"]
                if self.sender_side == "local":
                    self.datalink_ingress_logs[tun_id] = path.join(
                        remote_temp_dir, datalink_ingress_log_name
                    )
                    self.acklink_egress_logs[tun_id] = path.join(
                        remote_temp_dir, acklink_egress_log_name
                    )
                else:
                    self.datalink_egress_logs[tun_id] = path.join(
                        remote_temp_dir, datalink_egress_log_name
                    )
                    self.acklink_ingress_logs[tun_id] = path.join(
                        remote_temp_dir, acklink_ingress_log_name
                    )

    def setup(self):
        # Setup commonly used paths
        self.cc_src = str(context.src_dir / "wrappers" / f"{self.cc}.py")
        self.tunnel_manager = str(context.src_dir / "experiments" / "tunnel_manager.py")

        # Record who runs first
        self.run_first, self.run_second = (
            helpers.who_runs_first(self.cc)
            if self.test_config is None
            else (None, None)
        )

        self.run_first_setup_time = 3  # Wait for 3 seconds until `run_first` is ready

        # Setup output logs
        self.datalink_name = f"{self.cc}_datalink_run{self.run_id}"
        self.acklink_name = f"{self.cc}_acklink_run{self.run_id}"

        self.datalink_log = path.join(self.data_dir, f"{self.datalink_name}.log")
        self.acklink_log = path.join(self.data_dir, f"{self.acklink_name}.log")

        if self.flows > 0:
            self.prepare_tunnel_log_paths()
        if self.mode == "local":
            self.setup_mm_cmd()
        else:
            if self.ntp_addr is not None:
                self.local_offset, self.remote_offset = helpers.query_clock_offset(
                    self.ntp_addr, self.remote["ssh_cmd"]
                )

    def run_without_tunnel(self) -> bool:
        """Test congestion control without running Pantheon Tunnel"""
        port = utils.get_open_port()

        # Run the `self.run_first` side first
        cmd = ["python", self.cc_src, self.run_first, port]
        log_print(f"Running {self.cc} {self.run_first}")
        self.first_process = Popen(cmd, preexec_fn=os.setsid)

        # Sleep just in case the process is not ready (listening) yet
        # TODO: Change to verifying that the socket is open
        time.sleep(self.run_first_setup_time)
        self.test_start_time = utils.utc_time()

        # Run the other side
        shell_command = f"{" ".join(self.mm_cmd)} -- sh -c python {self.cc_src} {self.run_second} $MAHIMAHI_BASE {port}"
        log_print(f"Running {self.cc} {self.run_second}")
        self.second_process = Popen(shell_command, shell=True, preexec_fn=os.setsid)
        signal.signal(signal.SIGALRM, utils.timeout_handler)
        signal.alarm(self.runtime)

        try:
            self.first_process.wait()
            self.second_process.wait()
        except utils.TimeoutError:
            pass
        else:
            signal.alarm(0)
            log_print("Warning: test exited before time limit")
        finally:
            self.test_end_time = utils.utc_time()
        return True

    def run_tunnel_managers(self):
        # Run tunnel SERVER manager
        if self.mode == "remote":
            ts_manager_cmd = (
                ["python", self.tunnel_manager]
                if self.server_side == "local"
                else self.remote["ssh_cmd"] + ["python", self.remote["tunnel_manager"]]
            )
        else:
            ts_manager_cmd = ["python", self.tunnel_manager]

        log_print("[tunnel server manager] (tsm)")
        self.ts_manager = Popen(
            ts_manager_cmd,
            stdin=PIPE,
            stdout=PIPE,
            preexec_fn=os.setsid,
        )
        ts_manager = self.ts_manager
        while True:
            running = read_stdout(ts_manager)
            if "tunnel manager is running" in running:
                break
        write_stdin(ts_manager, "prompt [tsm]\n")

        # Run tunnel CLIENT manager
        if self.mode == "remote":
            tc_manager_cmd = (
                self.remote["ssh_cmd"] + ["python", self.remote["tunnel_manager"]]
                if self.server_side == "local"
                else ["python", self.tunnel_manager]
            )
        else:
            tc_manager_cmd = self.mm_cmd + ["python", self.tunnel_manager]
        log_print("[tunnel client manager (tcm)]")
        self.tc_manager = Popen(
            tc_manager_cmd,
            stdin=PIPE,
            stdout=PIPE,
            preexec_fn=os.setsid,
        )
        tc_manager = self.tc_manager

        while True:
            running = read_stdout(tc_manager)
            if "tunnel manager is running" in running:
                break
        write_stdin(tc_manager, "prompt [tcm]\n")
        return ts_manager, tc_manager

    def run_tunnel_server(self, tun_id, ts_manager):
        ts_cmd = (
            f"mm-tunnelserver --ingress-log={self.acklink_ingress_logs[tun_id]} --egress-log={self.datalink_egress_logs[tun_id]}"
            if self.server_side == self.sender_side
            else f"mm-tunnelserver --ingress-log={self.datalink_ingress_logs[tun_id]} --egress-log={self.acklink_egress_logs[tun_id]}"
        )

        if self.mode == "remote":
            if self.server_side == "remote":
                if self.remote_if is not None:
                    ts_cmd = ts_cmd + " --interface=" + self.remote_if
            else:
                if self.local_if is not None:
                    ts_cmd = ts_cmd + " --interface=" + self.local_if
        write_stdin(ts_manager, f"tunnel {tun_id} {ts_cmd}\n")

        # Read the command to run tunnel client
        write_stdin(ts_manager, f"tunnel {tun_id} readline\n")
        return read_stdout(ts_manager).split()

    def run_tunnel_client(self, tun_id, tc_manager, cmd_to_run: List) -> bool:
        if self.mode == "local":
            cmd_to_run[1] = "$MAHIMAHI_BASE"
        else:
            if self.server_side == "remote":
                cmd_to_run[1] = self.remote["ip"]
            else:
                cmd_to_run[1] = self.local_addr

        cmd_to_run_str: str = " ".join(cmd_to_run)

        if self.server_side == self.sender_side:
            tc_cmd = f"{cmd_to_run_str} --ingress-log={self.datalink_ingress_logs[tun_id]} --egress-log={self.acklink_egress_logs[tun_id]}"
        else:
            tc_cmd = f"{cmd_to_run_str} --ingress-log={self.acklink_ingress_logs[tun_id]} --egress-log={self.datalink_egress_logs[tun_id]}"

        if self.mode == "remote":
            if self.server_side == "remote":
                if self.local_if is not None:
                    tc_cmd = tc_cmd + f" --interface={self.local_if}"
            else:
                if self.remote_if is not None:
                    tc_cmd = tc_cmd + f" --interface={self.remote_if}"

        tc_cmd = f"tunnel {tun_id} {tc_cmd}\n"
        readline_cmd = f"tunnel {tun_id} readline\n"

        # Re-run tunnel client after 20 sec timeout for at most 3 times
        max_run, curr_run = 3, 0
        got_connection = ""
        while "got connection" not in got_connection:
            curr_run = curr_run + 1
            if curr_run > max_run:
                log_print("Unable to establish tunnel")
                return False

            write_stdin(tc_manager, tc_cmd)
            while True:
                write_stdin(tc_manager, readline_cmd)
                signal.signal(signal.SIGALRM, utils.timeout_handler)
                signal.alarm(20)
                try:
                    got_connection = read_stdout(tc_manager)
                    log_print("Tunnel is connected")
                except utils.TimeoutError:
                    log_print("Tunnel connection timeout")
                    break
                except IOError:
                    log_print("Tunnel client failed to connect to tunnel server")
                    return False
                else:
                    signal.alarm(0)
                    if "got connection" in got_connection:
                        break
        return True

    def run_first_side(
        self, tun_id, send_manager, recv_manager, send_pri_ip, recv_pri_ip
    ):
        first_src, second_src = self.cc_src, self.cc_src
        first_cmd, second_cmd = "", ""
        if self.run_first == "receiver":
            if self.mode == "remote":
                if self.sender_side == "local":
                    first_src = self.remote["cc_src"]
                else:
                    second_src = self.remote["cc_src"]

            port = utils.get_open_port()

            first_cmd = f"tunnel {tun_id} python {first_src} receiver {port}\n"
            second_cmd = (
                f"tunnel {tun_id} python {second_src} sender {recv_pri_ip} {port}\n"
            )
            write_stdin(recv_manager, first_cmd)

        elif self.run_first == "sender":
            if self.mode == "remote":
                if self.sender_side == "local":
                    second_src = self.remote["cc_src"]
                else:
                    first_src = self.remote["cc_src"]

            port = utils.get_open_port()

            first_cmd = f"tunnel {tun_id} python {first_src} sender {port}\n"
            second_cmd = (
                f"tunnel {tun_id} python {second_src} receiver {send_pri_ip} {port}\n"
            )

            write_stdin(send_manager, first_cmd)

        # get run_first and run_second from the flow object
        else:
            assert hasattr(self, "flow_objs")
            flow = self.flow_objs[tun_id]

            first_src = flow.cc_src_local
            second_src = flow.cc_src_local

            if flow.run_first == "receiver":
                if self.mode == "remote":
                    if self.sender_side == "local":
                        first_src = flow.cc_src_remote
                    else:
                        second_src = flow.cc_src_remote

                port = utils.get_open_port()

                first_cmd = f"tunnel {tun_id} python {first_src} receiver {port}\n"
                second_cmd = (
                    f"tunnel {tun_id} python {second_src} sender {recv_pri_ip} {port}\n"
                )
                write_stdin(recv_manager, first_cmd)
            elif flow.run_first == "sender":
                if self.mode == "remote":
                    if self.sender_side == "local":
                        second_src = flow.cc_src_remote
                    else:
                        first_src = flow.cc_src_remote

                port = utils.get_open_port()

                first_cmd = f"tunnel {tun_id} python {first_src} sender {port}\n"
                second_cmd = f"tunnel {tun_id} python {second_src} receiver {send_pri_ip} {port}\n"
                write_stdin(send_manager, first_cmd)
        assert second_cmd != ""
        return second_cmd

    def run_second_side(self, send_manager, recv_manager, second_cmds):
        time.sleep(self.run_first_setup_time)

        start_time, self.test_start_time = time.time(), utils.utc_time()

        # start each flow, self.interval seconds after the previous one
        for i in range(len(second_cmds)):
            if i != 0:
                time.sleep(self.interval)
            second_cmd = second_cmds[i]

            if self.run_first == "receiver":
                write_stdin(send_manager, second_cmd)
            elif self.run_first == "sender":
                write_stdin(recv_manager, second_cmd)
            else:
                assert hasattr(self, "flow_objs")
                flow = self.flow_objs[i+1]
                if flow.run_first == "receiver":
                    write_stdin(send_manager, second_cmd)
                elif flow.run_first == "sender":
                    write_stdin(recv_manager, second_cmd)

        elapsed_time = time.time() - start_time
        if elapsed_time > self.runtime:
            log_print("Interval time between flows is too long")
            return False
        time.sleep(self.runtime - elapsed_time)
        self.test_end_time = utils.utc_time()
        return True

    def run_with_tunnel(self):
        """Test congestion control using tunnel client and tunnel server"""

        # run pantheon tunnel server and client managers
        ts_manager, tc_manager = self.run_tunnel_managers()

        # create alias for ts_manager and tc_manager using sender or receiver
        if self.sender_side == self.server_side:
            send_manager = ts_manager
            recv_manager = tc_manager
        else:
            send_manager = tc_manager
            recv_manager = ts_manager

        # run every flow
        second_cmds = []
        for tun_id in range(1, self.flows + 1):
            # run tunnel server for tunnel tun_id
            cmd_to_run_tc = self.run_tunnel_server(tun_id, ts_manager)
            # run tunnel client for tunnel tun_id
            if not self.run_tunnel_client(tun_id, tc_manager, cmd_to_run_tc):
                return False

            tunnel_client_private_ip = cmd_to_run_tc[3]
            tunnel_server_private_ip = cmd_to_run_tc[4]

            if self.sender_side == self.server_side:
                sender_private_ip = tunnel_server_private_ip
                recv_private_ip = tunnel_client_private_ip
            else:
                sender_private_ip = tunnel_client_private_ip
                recv_private_ip = tunnel_server_private_ip

            # run the side that runs first and get cmd to run the other side
            second_cmd = self.run_first_side(
                tun_id, send_manager, recv_manager, sender_private_ip, recv_private_ip
            )
            second_cmds.append(second_cmd)

        # run the side that runs second
        if not self.run_second_side(send_manager, recv_manager, second_cmds):
            return False

        # stop all the running flows and quit tunnel managers
        write_stdin(ts_manager, "halt\n")
        write_stdin(tc_manager, "halt\n")

        # process tunnel logs
        self.process_tunnel_logs()
        return True

    def download_tunnel_logs(self, tun_id):
        assert self.mode == "remote"

        # download logs from remote side
        cmd = f"scp -C {self.remote["host_addr"]}:%(remote_log)s %(local_log)s"

        # function to get a corresponding local path from a remote path
        def remote_path_to_local(p):
            return path.join(
                str(context.base_dir / "tmp"),
                path.basename(p),
            )

        if self.sender_side == "remote":
            local_log = remote_path_to_local(self.datalink_egress_logs[tun_id])
            call(
                cmd
                % {
                    "remote_log": self.datalink_egress_logs[tun_id],
                    "local_log": local_log,
                },
                shell=True,
            )
            self.datalink_egress_logs[tun_id] = local_log

            local_log = remote_path_to_local(self.acklink_ingress_logs[tun_id])
            call(
                cmd
                % {
                    "remote_log": self.acklink_ingress_logs[tun_id],
                    "local_log": local_log,
                },
                shell=True,
            )
            self.acklink_ingress_logs[tun_id] = local_log
        else:
            local_log = remote_path_to_local(self.datalink_ingress_logs[tun_id])
            call(
                cmd
                % {
                    "remote_log": self.datalink_ingress_logs[tun_id],
                    "local_log": local_log,
                },
                shell=True,
            )
            self.datalink_ingress_logs[tun_id] = local_log

            local_log = remote_path_to_local(self.acklink_egress_logs[tun_id])
            call(
                cmd
                % {
                    "remote_log": self.acklink_egress_logs[tun_id],
                    "local_log": local_log,
                },
                shell=True,
            )
            self.acklink_egress_logs[tun_id] = local_log

    def process_tunnel_logs(self):
        datalink_tun_logs = []
        acklink_tun_logs = []
        (
            data_egress_offset,
            ack_ingress_offset,
            data_ingress_offset,
            ack_egress_offset,
        ) = (
            None,
            None,
            None,
            None,
        )
        apply_offset = False
        if self.mode == "remote":
            if self.remote_offset is not None and self.local_offset is not None:
                apply_offset = True
                if self.sender_side == "remote":
                    data_egress_offset = self.remote_offset
                    ack_ingress_offset = self.remote_offset
                    data_ingress_offset = self.local_offset
                    ack_egress_offset = self.local_offset
                else:
                    data_ingress_offset = self.remote_offset
                    ack_egress_offset = self.remote_offset
                    data_egress_offset = self.local_offset
                    ack_ingress_offset = self.local_offset

        # TODO: is there a better way?
        log_merge_script = os.path.join(
            str(context.src_dir), "experiments", "merge_tunnel_logs.py"
        )

        for tun_id in range(1, self.flows + 1):
            if self.mode == "remote":
                self.download_tunnel_logs(tun_id)

            uid = uuid.uuid4()
            datalink_tun_log = os.path.join(
                str(context.base_dir / "tmp"),
                f"{self.datalink_name}_flow{tun_id}_uid{uid}.log.merged",
            )
            acklink_tun_log = os.path.join(
                str(context.base_dir / "tmp"),
                f"{self.acklink_name}_flow{tun_id}_uid{uid}.log.merged",
            )
            cmd = [
                "python",
                log_merge_script,
                "single",
                "-i",
                self.datalink_ingress_logs[tun_id],
                "-e",
                self.datalink_egress_logs[tun_id],
                "-o",
                datalink_tun_log,
            ]
            if apply_offset:
                cmd += [
                    "-i-clock-offset",
                    data_ingress_offset,
                    "-e-clock-offset",
                    data_egress_offset,
                ]
            call(cmd)
            cmd = [
                "python",
                log_merge_script,
                "single",
                "-i",
                self.acklink_ingress_logs[tun_id],
                "-e",
                self.acklink_egress_logs[tun_id],
                "-o",
                acklink_tun_log,
            ]
            if apply_offset:
                cmd += [
                    "-i-clock-offset",
                    ack_ingress_offset,
                    "-e-clock-offset",
                    ack_egress_offset,
                ]
            call(cmd)
            datalink_tun_logs.append(datalink_tun_log)
            acklink_tun_logs.append(acklink_tun_log)

        cmd = [log_merge_script, "multiple", "-o", self.datalink_log]
        if self.mode == "local":
            cmd += ["--link-log", self.mm_datalink_log]
        cmd += datalink_tun_logs
        call(cmd)

        cmd = [log_merge_script, "multiple", "-o", self.acklink_log]
        if self.mode == "local":
            cmd += ["--link-log", self.mm_acklink_log]
        cmd += acklink_tun_logs
        call(cmd)

    def run_congestion_control(self):
        if self.flows > 0:
            try:
                return self.run_with_tunnel()
            finally:
                kill_proc_group(self.ts_manager)
                kill_proc_group(self.tc_manager)
        else:
            # test without pantheon tunnel when self.flows = 0
            try:
                return self.run_without_tunnel()
            finally:
                kill_proc_group(self.first_process)
                kill_proc_group(self.second_process)

    def record_time_stats(self):
        stats_log = os.path.join(self.data_dir, f"{self.cc}_stats_run{self.run_id}.log")
        with open(stats_log, "w") as stats:
            # save start time and end time of test
            if self.test_start_time is not None and self.test_end_time is not None:
                test_run_duration = (
                    f"Start at: {self.test_start_time}\nEnd at: {self.test_end_time}\n"
                )
                log_print(test_run_duration)
                stats.write(test_run_duration)
            if self.mode == "remote":
                offset_info = ""
                if self.local_offset is not None:
                    offset_info += f"Local clock offset: {self.local_offset} ms\n"
                if self.remote_offset is not None:
                    offset_info += f"Remote clock offset: {self.remote_offset} ms\n"
                if offset_info:
                    log_print(offset_info)
                    stats.write(offset_info)

    def run(self):
        """Run congestion control test"""
        msg = f"Testing scheme {self.cc} for experiment run {self.run_id}/{self.run_times}..."
        log_print(msg)

        # setup before running tests
        self.setup()

        # run receiver and sender
        if not self.run_congestion_control():
            log_print(f"Error in testing scheme {self.cc} with run ID {self.run_id}")
            return

        # write runtimes and clock offsets to file
        self.record_time_stats()

        log_print(f"Done testing {self.cc}")
