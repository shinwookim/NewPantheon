import sys
from pathlib import Path
from uuid import uuid4

from ..common import context, utils


class Test:
    def __init__(self, args, run_id, cc):
        self.remote_offset = None
        self.ntp_addr = None
        self.local_offset = None
        self.mm_cmd = None
        self.mm_datalink_log = None
        self.mm_acklink_log = None
        self.mode = args.mode  # remote or local
        self.run_id = run_id
        self.cc = cc
        self.data_dir = str(Path(args.data_dir).resolve().absolute)

        # Shared arguments - used both for local and remote
        self.flows = args.flows  # number of flows
        self.runtime = args.runtime  # total runtime (sec)
        self.interval = args.interval  # interval between two flows (secs)
        self.run_times = args.run_times  # run-times of each scheme

        # Used for cleanup
        self.proc_first = None
        self.proc_second = None
        self.ts_manager = None
        self.tc_manager = None

        self.test_start_time = None
        self.test_end_time = None

        self.cc_src = None
        self.tunnel_manager = None
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
        self.r = {}

        # local mode
        if self.mode == 'local':
            self.datalink_trace = args.uplink_trace
            self.acklink_trace = args.downlink_trace
            self.prepend_mm_cmds = args.prepend_mm_cmds
            self.append_mm_cmds = args.append_mm_cmds
            self.extra_mm_link_args = args.extra_mm_link_args

            # for convenience
            self.sender_side = 'remote'
            self.server_side = 'local'

        # remote mode
        if self.mode == 'remote':
            raise NotImplementedError

        self.test_config = args.test_config if hasattr(args, 'test_config') else None
        if self.test_config is not None:
            # TODO
            raise NotImplementedError

    def run(self):
        print(f"Testing scheme {self.cc} for experiment run {self.run_id}/{self.run_times}")
        self.setup()

        if not self.run_congestion_control():
            print(f"Error while testing scheme {self.cc} with run ID = {self.run_id}")
            return
        self.record_time_statistics()
        print(f"Done testing {self.cc}")

    def setup(self):
        self.cc_src = Path(context.src_dir) / 'wrappers' / (self.cc + '.py')
        self.tunnel_manager = Path(context.src_dir) / 'experiments' / 'tunnel_manager.py'

        self.run_first, self.run_second = utils.who_runs_first(self.cc) if self.test_config is None else (None, None)

        # wait for 3 seconds until run_first is ready
        self.run_first_setup_time = 3

        # setup output logs
        self.datalink_name = f"{self.cc}_datalink_run{self.run_id}"
        self.acklink_name = f"{self.cc}_acklink_run%{self.run_id}"

        self.datalink_log = Path(self.data_dir) / f"{self.datalink_name}.log"
        self.acklink_log = Path(self.data_dir) / f"{self.acklink_name}.log"

        if self.flows > 0:
            self.prepare_tunnel_log_paths()

        if self.mode == 'local':
            self.setup_mm_cmd()
        else:
            # record local and remote clock offset
            if self.ntp_addr is not None:
                self.local_offset, self.remote_offset = utils.query_clock_offset(self.ntp_addr, self.r['ssh_cmd'])

    def prepare_tunnel_log_paths(self):
        """Ensures logs have correct paths on local and remote"""
        local_tmp = Path(context.base_dir) / 'tmp'

        for tun_id in range(1, self.flows + 1):
            uid = uuid4()
            datalink_ingress_log_name = f"{self.datalink_name}_flow{tun_id}_uid{uid}.log.ingress"
            self.datalink_ingress_logs[tun_id] = local_tmp / datalink_ingress_log_name

            datalink_egress_log_name = f"{self.datalink_name}_flow{tun_id}_uid{uid}.log.egress"
            self.datalink_egress_logs[tun_id] = local_tmp / datalink_egress_log_name

            acklink_ingress_log_name = f"{self.acklink_name}_flow{tun_id}_uid{uid}.log.ingress"
            self.acklink_ingress_logs[tun_id] = local_tmp / acklink_ingress_log_name

            acklink_egress_log_name = f"{self.acklink_name}_flow{tun_id}_uid{uid}.log.egress"
            self.acklink_egress_logs[tun_id] = local_tmp / acklink_egress_log_name

            if self.mode == 'remote':
                remote_tmp = Path(self.r['tmp_dir'])
                if self.sender_side == 'local':
                    self.datalink_ingress_logs[tun_id] = remote_tmp / datalink_ingress_log_name
                    self.acklink_egress_logs[tun_id] = remote_tmp / acklink_egress_log_name
                else:
                    self.datalink_egress_logs[tun_id] = remote_tmp / datalink_egress_log_name
                    self.acklink_ingress_logs[tun_id] = remote_tmp / acklink_ingress_log_name

    def setup_mm_cmd(self):
        self.mm_datalink_log = Path(self.data_dir) / f"{self.cc}_mm_datalink_run{self.run_id}.log"
        self.mm_acklink_log = Path(self.data_dir) / f"{self.cc}_mm_acklink_run{self.run_id}.log"

        if self.run_first == 'receiver' or self.flows > 0:
            # if receiver runs first OR if test inside pantheon tunnel
            uplink_log = self.mm_datalink_log
            downlink_log = self.mm_acklink_log
            uplink_trace = self.datalink_trace
            downlink_trace = self.acklink_trace
        else:
            # if sender runs first AND test without pantheon tunnel
            uplink_log = self.mm_acklink_log
            downlink_log = self.mm_datalink_log
            uplink_trace = self.acklink_trace
            downlink_trace = self.datalink_trace

        self.mm_cmd = []

        if self.prepend_mm_cmds:
            self.mm_cmd += self.prepend_mm_cmds.split()

        self.mm_cmd += ['mm-link', uplink_trace, downlink_trace, '--uplink-log=' + str(uplink_log),
                        '--downlink-log=' + str(downlink_log)]

        if self.extra_mm_link_args:
            self.mm_cmd += self.extra_mm_link_args.split()

        if self.append_mm_cmds:
            self.mm_cmd += self.append_mm_cmds.split()

    def run_congestion_control(self):
        if self.flows > 0:
            try:
                return self.run_with_tunnel()
            finally:
                utils.kill_proc_group(self.ts_manager)
                utils.kill_proc_group(self.tc_manager)
        else:
            # test without pantheon tunnel when self.flows = 0
            try:
                return self.run_without_tunnel()
            finally:
                utils.kill_proc_group(self.proc_first)
                utils.kill_proc_group(self.proc_second)



    def record_time_statistics(self):
        with open(str(Path(self.data_dir) / f"{self.cc}_stats_run{self.run_id}.log"), 'w') as stats:

            # save start time and end time of test
            if self.test_start_time is not None and self.test_end_time is not None:
                test_run_duration = f"'Start at: {self.test_start_time}\nEnd at: {self.test_end_time}\n"
                print(test_run_duration, file=sys.stderr)
                stats.write(test_run_duration)

            if self.mode == 'remote':
                offset_info = ''
                if self.local_offset is not None:
                    offset_info += f"Local clock offset: {self.local_offset} ms\n"

                if self.remote_offset is not None:
                    offset_info += f"Remote clock offset: {self.remote_offset} ms\n"
                if offset_info:
                    print(offset_info, file=sys.stderr)
                    stats.write(offset_info)

    def run_with_tunnel(self):
        pass

    def run_without_tunnel(self):
        pass
