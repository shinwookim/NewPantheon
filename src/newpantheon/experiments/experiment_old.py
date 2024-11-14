import signal
import sys
import uuid
from collections import namedtuple
from pathlib import Path
from os import path
import os
from subprocess import Popen, PIPE, call
from ..common import utils, context
import time
Flow = namedtuple('Flow', ['cc',  # replace self.cc
                           'cc_src_local',  # replace self.cc_src
                           'cc_src_remote',  # replace self.r[cc_src]
                           'run_first',  # replace self.run_first
                           'run_second'])  # replace self.run_second



    # test congestion control without running pantheon tunnel
    def run_without_tunnel(self):
        port = utils.get_open_port()

        # run the side specified by self.run_first
        cmd = ['python', self.cc_src, self.run_first, port]
        sys.stderr.write('Running %s %s...\n' % (self.cc, self.run_first))
        self.proc_first = Popen(cmd, preexec_fn=os.setsid)

        # sleep just in case the process isn't quite listening yet
        # the cleaner approach might be to try to verify the socket is open
        time.sleep(self.run_first_setup_time)

        self.test_start_time = utils.utc_time()
        # run the other side specified by self.run_second
        sh_cmd = 'python %s %s $MAHIMAHI_BASE %s' % (self.cc_src, self.run_second, port)
        sh_cmd = ' '.join(self.mm_cmd) + " -- sh -c '%s'" % sh_cmd
        sys.stderr.write('Running %s %s...\n' % (self.cc, self.run_second))
        self.proc_second = Popen(sh_cmd, shell=True, preexec_fn=os.setsid)

        signal.signal(signal.SIGALRM, utils.timeout_handler)
        signal.alarm(self.runtime)

        try:
            self.proc_first.wait()
            self.proc_second.wait()
        except utils.TimeoutError:
            pass
        else:
            signal.alarm(0)
            sys.stderr.write('Warning: test exited before time limit\n')
        finally:
            self.test_end_time = utils.utc_time()

        return True

    def run_tunnel_managers(self):
        # run tunnel server manager
        if self.mode == 'remote':
            if self.server_side == 'local':
                ts_manager_cmd = ['python', self.tunnel_manager]
            else:
                ts_manager_cmd = self.r['ssh_cmd'] + ['python', self.r['tunnel_manager']]
        else:
            ts_manager_cmd = ['python', self.tunnel_manager]

        sys.stderr.write('[tunnel server manager (tsm)] ')
        self.ts_manager = Popen(ts_manager_cmd, stdin=PIPE, stdout=PIPE, preexec_fn=os.setsid)
        ts_manager = self.ts_manager

        while True:
            running = ts_manager.stdout.readline().decode(sys.stdout.encoding)
            if 'tunnel manager is running' in running:
                sys.stderr.write(running)
                break

        ts_manager.stdin.write(b'prompt [tsm]\n')
        ts_manager.stdin.flush()

        # run tunnel client manager
        if self.mode == 'remote':
            if self.server_side == 'local':
                tc_manager_cmd = self.r['ssh_cmd'] + ['python', self.r['tunnel_manager']]
            else:
                tc_manager_cmd = ['python', self.tunnel_manager]
        else:
            tc_manager_cmd = self.mm_cmd + ['python', self.tunnel_manager]

        sys.stderr.write('[tunnel client manager (tcm)] ')
        self.tc_manager = Popen(tc_manager_cmd, stdin=PIPE, stdout=PIPE, preexec_fn=os.setsid)
        tc_manager = self.tc_manager

        while True:
            running = tc_manager.stdout.readline().decode(encoding=sys.stdout.encoding)
            if 'tunnel manager is running' in running:
                sys.stderr.write(running)
                break

        tc_manager.stdin.write(b'prompt [tcm]\n')
        tc_manager.stdin.flush()

        return ts_manager, tc_manager

    def run_tunnel_server(self, tun_id, ts_manager):
        if self.server_side == self.sender_side:
            ts_cmd = 'mm-tunnelserver --ingress-log=%s --egress-log=%s' % (
                self.acklink_ingress_logs[tun_id], self.datalink_egress_logs[tun_id])
        else:
            ts_cmd = 'mm-tunnelserver --ingress-log=%s --egress-log=%s' % (
                self.datalink_ingress_logs[tun_id], self.acklink_egress_logs[tun_id])

        if self.mode == 'remote':
            if self.server_side == 'remote':
                if self.remote_if is not None:
                    ts_cmd += ' --interface=' + self.remote_if
            else:
                if self.local_if is not None:
                    ts_cmd += ' --interface=' + self.local_if

        ts_cmd = 'tunnel %s %s\n' % (tun_id, ts_cmd)
        ts_cmd = ts_cmd.encode('ascii')
        ts_manager.stdin.write(ts_cmd)
        ts_manager.stdin.flush()

        # read the command to run tunnel client
        readline_cmd = 'tunnel %s readline\n' % tun_id
        readline_cmd= readline_cmd.encode(sys.stdout.encoding)
        ts_manager.stdin.write(readline_cmd)
        ts_manager.stdin.flush()

        cmd_to_run_tc = ts_manager.stdout.readline().split()
        return cmd_to_run_tc

    def run_tunnel_client(self, tun_id, tc_manager, cmd_to_run_tc):
        if self.mode == 'local':
            cmd_to_run_tc[1] = '$MAHIMAHI_BASE'
        else:
            if self.server_side == 'remote':
                cmd_to_run_tc[1] = self.r['ip']
            else:
                cmd_to_run_tc[1] = self.local_addr
        cmd_to_run_tc = [cmd.decode(sys.stdout.encoding) if isinstance(cmd, bytes) else cmd for cmd in cmd_to_run_tc]
        print(cmd_to_run_tc)
        cmd_to_run_tc_str = ' '.join(cmd_to_run_tc)

        if self.server_side == self.sender_side:
            tc_cmd = '%s --ingress-log=%s --egress-log=%s' % (
                cmd_to_run_tc_str, self.datalink_ingress_logs[tun_id], self.acklink_egress_logs[tun_id])
        else:
            tc_cmd = '%s --ingress-log=%s --egress-log=%s' % (
                cmd_to_run_tc_str, self.acklink_ingress_logs[tun_id], self.datalink_egress_logs[tun_id])

        if self.mode == 'remote':
            if self.server_side == 'remote':
                if self.local_if is not None:
                    tc_cmd += ' --interface=' + self.local_if
            else:
                if self.remote_if is not None:
                    tc_cmd += ' --interface=' + self.remote_if

        tc_cmd = 'tunnel %s %s\n' % (tun_id, tc_cmd)
        readline_cmd = 'tunnel %s readline\n' % tun_id

        # re-run tunnel client after 20s timeout for at most 3 times
        max_run = 3
        curr_run = 0
        got_connection = ''
        while 'got connection' not in got_connection:
            curr_run += 1
            if curr_run > max_run:
                sys.stderr.write('Unable to establish tunnel\n')
                return False

            tc_manager.stdin.write(tc_cmd.encode( sys.stdout.encoding))
            tc_manager.stdin.flush()
            while True:
                tc_manager.stdin.write(readline_cmd.encode( sys.stdout.encoding))
                tc_manager.stdin.flush()

                signal.signal(signal.SIGALRM, utils.timeout_handler)
                signal.alarm(20)

                try:
                    got_connection = tc_manager.stdout.readline().decode(sys.stdout.encoding)
                    sys.stderr.write('Tunnel is connected\n')
                except utils.TimeoutError:
                    sys.stderr.write('Tunnel connection timeout\n')
                    break
                except IOError:
                    sys.stderr.write('Tunnel client failed to connect to '
                                     'tunnel server\n')
                    return False
                else:
                    signal.alarm(0)
                    if 'got connection' in got_connection:
                        break

        return True

    def run_first_side(self, tun_id, send_manager, recv_manager, send_pri_ip, recv_pri_ip):

        first_src = self.cc_src
        second_src = self.cc_src

        if self.run_first == 'receiver':
            if self.mode == 'remote':
                if self.sender_side == 'local':
                    first_src = self.r['cc_src']
                else:
                    second_src = self.r['cc_src']

            port = utils.get_open_port()

            first_cmd = 'tunnel %s python %s receiver %s\n' % (tun_id, first_src, port)
            second_cmd = 'tunnel %s python %s sender %s %s\n' % (tun_id, second_src, recv_pri_ip, port)

            recv_manager.stdin.write(first_cmd.encode('ascii'))
            recv_manager.stdin.flush()
        elif self.run_first == 'sender':  # self.run_first == 'sender'
            if self.mode == 'remote':
                if self.sender_side == 'local':
                    second_src = self.r['cc_src']
                else:
                    first_src = self.r['cc_src']

            port = utils.get_open_port()

            first_cmd = 'tunnel %s python %s sender %s\n' % (tun_id, first_src, port)
            second_cmd = 'tunnel %s python %s receiver %s %s\n' % (tun_id, second_src, send_pri_ip, port)

            send_manager.stdin.write(first_cmd.encode('ascii'))
            send_manager.stdin.flush()

        # get run_first and run_second from the flow object
        else:
            assert (hasattr(self, 'flow_objs'))
            flow = self.flow_objs[tun_id]

            first_src = flow.cc_src_local
            second_src = flow.cc_src_local

            if flow.run_first == 'receiver':
                if self.mode == 'remote':
                    if self.sender_side == 'local':
                        first_src = flow.cc_src_remote
                    else:
                        second_src = flow.cc_src_remote

                port = utils.get_open_port()

                first_cmd = 'tunnel %s python %s receiver %s\n' % (tun_id, first_src, port)
                second_cmd = 'tunnel %s python %s sender %s %s\n' % (tun_id, second_src, recv_pri_ip, port)

                recv_manager.stdin.write(first_cmd)
                recv_manager.stdin.flush()
            else:  # flow.run_first == 'sender'
                if self.mode == 'remote':
                    if self.sender_side == 'local':
                        second_src = flow.cc_src_remote
                    else:
                        first_src = flow.cc_src_remote

                port = utils.get_open_port()

                first_cmd = 'tunnel %s python %s sender %s\n' % (tun_id, first_src, port)
                second_cmd = 'tunnel %s python %s receiver %s %s\n' % (tun_id, second_src, send_pri_ip, port)

                send_manager.stdin.write(first_cmd)
                send_manager.stdin.flush()

        return second_cmd

    def run_second_side(self, send_manager, recv_manager, second_cmds):
        time.sleep(self.run_first_setup_time)

        start_time = time.time()
        self.test_start_time = utils.utc_time()

        # start each flow self.interval seconds after the previous one
        for i in range(len(second_cmds)):
            if i != 0:
                time.sleep(self.interval)
            second_cmd = second_cmds[i]

            if self.run_first == 'receiver':
                send_manager.stdin.write(second_cmd.encode(sys.stdout.encoding))
                send_manager.stdin.flush()
            elif self.run_first == 'sender':
                recv_manager.stdin.write(second_cmd.encode(sys.stdout.encoding))
                recv_manager.stdin.flush()
            else:
                assert (hasattr(self, 'flow_objs'))
                flow = self.flow_objs[i]
                if flow.run_first == 'receiver':
                    send_manager.stdin.write(second_cmd.encode(sys.stdout.encoding))
                    send_manager.stdin.flush()
                elif flow.run_first == 'sender':
                    recv_manager.stdin.write(second_cmd.encode(sys.stdout.encoding))
                    recv_manager.stdin.flush()

        elapsed_time = time.time() - start_time
        if elapsed_time > self.runtime:
            sys.stderr.write(b'Interval time between flows is too long')
            return False

        time.sleep(self.runtime - elapsed_time)
        self.test_end_time = utils.utc_time()

        return True

    # test congestion control using tunnel client and tunnel server
    def run_with_tunnel(self):
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

            tc_pri_ip = cmd_to_run_tc[3]  # tunnel client private IP
            ts_pri_ip = cmd_to_run_tc[4]  # tunnel server private IP

            if self.sender_side == self.server_side:
                send_pri_ip = ts_pri_ip
                recv_pri_ip = tc_pri_ip
            else:
                send_pri_ip = tc_pri_ip
                recv_pri_ip = ts_pri_ip

            # run the side that runs first and get cmd to run the other side
            second_cmd = self.run_first_side(tun_id, send_manager, recv_manager, str(send_pri_ip), recv_pri_ip)
            second_cmds.append(second_cmd)

        # run the side that runs second
        if not self.run_second_side(send_manager, recv_manager, second_cmds):
            return False

        # stop all the running flows and quit tunnel managers
        ts_manager.stdin.write(b'halt\n')
        ts_manager.stdin.flush()
        tc_manager.stdin.write(b'halt\n')
        tc_manager.stdin.flush()

        # process tunnel logs
        self.process_tunnel_logs()

        return True

    def download_tunnel_logs(self, tun_id):
        assert (self.mode == 'remote')

        # download logs from remote side
        cmd = 'scp -C %s:' % self.r['host_addr']
        cmd += '%(remote_log)s %(local_log)s'

        # function to get a corresponding local path from a remote path
        f = lambda p: path.join(utils.tmp_dir, path.basename(p))

        if self.sender_side == 'remote':
            local_log = f(self.datalink_egress_logs[tun_id])
            call(cmd % {'remote_log': self.datalink_egress_logs[tun_id], 'local_log': local_log}, shell=True)
            self.datalink_egress_logs[tun_id] = local_log

            local_log = f(self.acklink_ingress_logs[tun_id])
            call(cmd % {'remote_log': self.acklink_ingress_logs[tun_id], 'local_log': local_log}, shell=True)
            self.acklink_ingress_logs[tun_id] = local_log
        else:
            local_log = f(self.datalink_ingress_logs[tun_id])
            call(cmd % {'remote_log': self.datalink_ingress_logs[tun_id], 'local_log': local_log}, shell=True)
            self.datalink_ingress_logs[tun_id] = local_log

            local_log = f(self.acklink_egress_logs[tun_id])
            call(cmd % {'remote_log': self.acklink_egress_logs[tun_id], 'local_log': local_log}, shell=True)
            self.acklink_egress_logs[tun_id] = local_log
