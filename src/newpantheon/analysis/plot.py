#!/usr/bin/env python

from os import path
import sys
import math
import json
import multiprocessing
from multiprocessing.pool import ThreadPool
import numpy as np

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
matplotlib.use('Agg')


from newpantheon.common import utils
from newpantheon.analysis import tunnel_graph


class Plot(object):
    def __init__(self, args):
        # plt.use('Agg')
        self.data_dir = path.abspath(args.data_dir)
        self.include_acklink = args.include_acklink
        self.no_graphs = args.no_graphs

        metadata_path = path.join(self.data_dir, 'pantheon_metadata.json')
        meta = utils.load_test_metadata(metadata_path)
        self.interactions = args.interactions
        if not self.interactions:
            self.cc_schemes = utils.verify_schemes_with_meta(args.schemes, meta)
            self.individual_schemes = utils.verify_schemes_with_meta(args.schemes, meta)
        else:
            self.cc_schemes = [args.test_name]
            self.individual_schemes = utils.verify_schemes_with_meta(args.schemes, meta)

        self.run_times = meta['run_times']
        self.flows = meta['flows']
        self.runtime = meta['runtime']
        self.expt_title = self.generate_expt_title(meta)

    def generate_expt_title(self, meta):
        if meta['mode'] == 'local':
            expt_title = 'Local test in mahimahi, '
        elif meta['mode'] == 'remote':
            txt = {'local': [], 'remote': []}
            for side in ['local', 'remote']:
                if f'{side}_desc' in meta:
                    txt[side].append(meta[f'{side}_desc'])
                else:
                    txt[side].append(side)

                txt[side] = ' '.join(txt[side])

            sender = txt['remote'] if meta['sender_side'] == 'remote' else txt['local']
            receiver = txt['local'] if meta['sender_side'] == 'remote' else txt['remote']
            expt_title = f"Test from {sender} to {receiver}, "

        runs_str = "run" if meta['run_times'] == 1 else "runs"
        expt_title += f"{meta['run_times']} {runs_str} of {meta['runtime']}s each per scheme\n"

        if meta['flows'] > 1:
            expt_title += f"{meta['flows']} flows with {meta['interval']}s interval between flows"

        return expt_title

    def parse_tunnel_log(self, cc, run_id):
        log_prefix = cc
        if self.flows == 0:
            log_prefix += '_mm'

        error = False
        ret = None

        link_directions = ['datalink']
        if self.include_acklink:
            link_directions.append('acklink')

        for link_t in link_directions:
            log_name = f"{log_prefix}_{link_t}_run{run_id}.log"
            log_path = path.join(self.data_dir, log_name)

            if not path.isfile(log_path):
                sys.stderr.write(f"Warning: {log_path} does not exist\n")
                error = True
                continue

            # if self.no_graphs:
            #     tput_graph_path = None
            #     delay_graph_path = None
            # else:
            tput_graph_path = path.join(self.data_dir, f"{cc}_{link_t}_throughput_run{run_id}.png")
            delay_graph_path = path.join(self.data_dir, f"{cc}_{link_t}_delay_run{run_id}.png")

            sys.stderr.write(f"$ tunnel_graph {log_path}\n")
            try:
                tunnel_results = tunnel_graph.TunnelGraph(
                    tunnel_log=log_path,
                    throughput_graph=tput_graph_path,
                    delay_graph=delay_graph_path).run()
            except Exception as exception:
                sys.stderr.write('Error: %s\n' % exception)
                sys.stderr.write('Warning: "tunnel_graph %s" failed but '
                                 'continued to run.\n' % log_path)
                error = True

            if error:
                continue

            if link_t == 'datalink':
                ret = tunnel_results
                duration = tunnel_results['duration'] / 1000.0

                if duration < 0.8 * self.runtime:
                    sys.stderr.write(
                        f"Warning: {log_path} had duration {duration:.2f}s "
                        f"but should have been around {self.runtime}s. Ignoring this run.\n"
                    )
                    error = True

        if error:
            return None

        return ret

    def update_stats_log(self, cc, run_id, stats):
        stats_log_path = path.join(self.data_dir, f"{cc}_stats_run{run_id}.log")

        if not path.isfile(stats_log_path):
            sys.stderr.write(f"Warning: {stats_log_path} does not exist\n")
            return

        saved_lines = ''

        # back up old stats logs
        with open(stats_log_path) as stats_log:
            for line in stats_log:
                if any([x in line for x in [
                        'Start at:', 'End at:', 'clock offset:']]):
                    saved_lines += line
                else:
                    continue

        # write to new stats log
        with open(stats_log_path, 'w') as stats_log:
            stats_log.write(saved_lines)

            if stats:
                stats_log.write(f"\n# Below is generated by {path.basename(__file__)} at {utils.utc_time()}\n")
                stats_log.write("# Datalink statistics\n")
                if self.interactions:
                    for i in range(len(self.individual_schemes)):
                        stats_log.write(f"# Flow {i+1} = {self.individual_schemes[i]}\n")
                stats_log.write(stats)

    def eval_performance(self):
        perf_data = {}
        stats = {}

        for cc in self.cc_schemes:
            perf_data[cc] = {}
            stats[cc] = {}

        cc_id = 0
        run_id = 1
        pool = ThreadPool(processes=multiprocessing.cpu_count())

        while cc_id < len(self.cc_schemes):
            cc = self.cc_schemes[cc_id]
            perf_data[cc][run_id] = pool.apply_async(
                self.parse_tunnel_log, args=(cc, run_id))

            run_id += 1
            if run_id > self.run_times:
                run_id = 1
                cc_id += 1

        for cc in self.cc_schemes:
            for run_id in range(1, 1 + self.run_times):
                perf_data[cc][run_id] = perf_data[cc][run_id].get()

                if perf_data[cc][run_id] is None:
                    continue
                stats_str = perf_data[cc][run_id]['stats']
                self.update_stats_log(cc, run_id, stats_str)
                stats[cc][run_id] = stats_str

        sys.stderr.write(f'Appended datalink statistics to stats files in {self.data_dir}\n')

        return perf_data, stats

    def xaxis_log_scale(self, ax, min_delay, max_delay):
        if min_delay < -2:
            x_min = int(-math.pow(2, math.ceil(math.log(-min_delay, 2))))
        elif min_delay < 0:
            x_min = -2
        elif min_delay < 2:
            x_min = 0
        else:
            x_min = int(math.pow(2, math.floor(math.log(min_delay, 2))))

        if max_delay < -2:
            x_max = int(-math.pow(2, math.floor(math.log(-max_delay, 2))))
        elif max_delay < 0:
            x_max = 0
        elif max_delay < 2:
            x_max = 2
        else:
            x_max = int(math.pow(2, math.ceil(math.log(max_delay, 2))))

        symlog = False
        if x_min <= -2:
            if x_max >= 2:
                symlog = True
        elif x_min == 0:
            if x_max >= 8:
                symlog = True
        elif x_min >= 2:
            if x_max > 4 * x_min:
                symlog = True

        if symlog:
            ax.set_xscale('symlog', base=2, linthresh=2, linscale=0.5)
            ax.set_xlim(x_min, x_max)
            ax.xaxis.set_major_formatter(ticker.FormatStrFormatter('%d'))

    def plot_throughput_delay(self, data):
        min_raw_delay = sys.maxsize
        min_mean_delay = sys.maxsize
        max_raw_delay = -sys.maxsize
        max_mean_delay = -sys.maxsize

        fig_raw, ax_raw = plt.subplots()
        fig_mean, ax_mean = plt.subplots()

        schemes_config = utils.parse_config()['schemes']
        
        for cc, value in data.items():
            if not value:
                sys.stderr.write(f"No performance data for scheme {cc}\n")
                continue
            
            if self.interactions:
                cc_name = self.cc_schemes
                color = 'blue'
                marker = '*'
            else:
                cc_name = schemes_config[cc]['name']
                color = schemes_config[cc]['color']
                marker = schemes_config[cc]['marker']
            y_data, x_data = zip(*value)

            # update min and max raw delay
            min_raw_delay = min(min(x_data), min_raw_delay)
            max_raw_delay = max(max(x_data), max_raw_delay)

            # plot raw values
            ax_raw.scatter(x_data, y_data, color=color, marker=marker, label=cc_name)

            # plot the average of raw values
            x_mean = np.mean(x_data)
            y_mean = np.mean(y_data)

            # update min and max mean delay
            min_mean_delay = min(x_mean, min_mean_delay)
            max_mean_delay = max(x_mean, max_mean_delay)

            ax_mean.scatter(x_mean, y_mean, color=color, marker=marker)
            ax_mean.annotate(cc_name, (x_mean, y_mean))

        for fig_type, fig, ax in [('raw', fig_raw, ax_raw),
                                  ('mean', fig_mean, ax_mean)]:
            if fig_type == 'raw':
                self.xaxis_log_scale(ax, min_raw_delay, max_raw_delay)
            else:
                self.xaxis_log_scale(ax, min_mean_delay, max_mean_delay)
            ax.invert_xaxis()

            yticks = ax.get_yticks()
            if yticks[0] < 0:
                ax.set_ylim(bottom=0)

            xlabel = '95th percentile one-way delay (ms)'
            ax.set_xlabel(xlabel, fontsize=12)
            ax.set_ylabel('Average throughput (Mbit/s)', fontsize=12)
            ax.grid()

        # save pantheon_summary.svg and .pdf
        ax_raw.set_title(self.expt_title.strip(), y=1.02, fontsize=12)
        lgd = ax_raw.legend(scatterpoints=1, bbox_to_anchor=(0.5, -0.15),
                            loc='upper center', fontsize=12)

        for graph_format in ['svg', 'pdf', 'png']:
            raw_summary = path.join(
                self.data_dir, 'pantheon_summary.%s' % graph_format)
            fig_raw.savefig(raw_summary, dpi=300, bbox_extra_artists=(lgd,),
                            bbox_inches='tight', pad_inches=0.2)

        # save pantheon_summary_mean.svg and .pdf
        ax_mean.set_title(self.expt_title +
                          ' (mean of all runs by scheme)', fontsize=12)

        for graph_format in ['svg', 'pdf', 'png']:
            mean_summary = path.join(
                self.data_dir, 'pantheon_summary_mean.%s' % graph_format)
            fig_mean.savefig(mean_summary, dpi=300,
                             bbox_inches='tight', pad_inches=0.2)

        sys.stderr.write(
            f'Saved throughput graphs, delay graphs, and summary graphs in {self.data_dir}\n')

    def run(self):
        perf_data, stats_logs = self.eval_performance()

        data_for_plot = {}
        data_for_json = {}

        for cc in perf_data:
            data_for_plot[cc] = []
            data_for_json[cc] = {}

            for run_id in perf_data[cc]:
                if perf_data[cc][run_id] is None:
                    continue

                tput = perf_data[cc][run_id]['throughput']
                delay = perf_data[cc][run_id]['delay']
                if tput is None or delay is None:
                    continue
                data_for_plot[cc].append((tput, delay))

                flow_data = perf_data[cc][run_id]['flow_data']
                if flow_data is not None:
                    data_for_json[cc][run_id] = flow_data

        # if not self.no_graphs:
        self.plot_throughput_delay(data_for_plot)

        plt.close('all')

        perf_path = path.join(self.data_dir, 'pantheon_perf.json')
        with open(perf_path, 'w') as fh:
            json.dump(data_for_json, fh)

def run(args):
    plot = Plot(args)
    plot.run()