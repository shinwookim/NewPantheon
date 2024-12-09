#!/usr/bin/env python

from os import path
import sys
import math
import itertools
import numpy as np
import matplotlib
import matplotlib.pyplot as plt

matplotlib.use('Agg')
# from analysis import parse_tunnel_graph

# import arg_parser


class TunnelGraph(object):
    def __init__(self, tunnel_log, throughput_graph=None, delay_graph=None,
                 ms_per_bin=500):
        # plt.use('Agg')
        self.tunnel_log = tunnel_log
        self.throughput_graph = throughput_graph
        self.delay_graph = delay_graph
        self.ms_per_bin = ms_per_bin

    def ms_to_bin(self, ts, first_ts):
        return int((ts - first_ts) / self.ms_per_bin)

    def bin_to_s(self, bin_id):
        return bin_id * self.ms_per_bin / 1000.0

    def parse_tunnel_log(self):
        tunlog = open(self.tunnel_log)

        self.flows = {}
        first_ts = None
        capacities = {}

        arrivals = {}
        departures = {}
        self.delays_t = {}
        self.delays = {}

        first_capacity = None
        last_capacity = None
        first_arrival = {}
        last_arrival = {}
        first_departure = {}
        last_departure = {}

        total_first_departure = None
        total_last_departure = None
        total_arrivals = 0
        total_departures = 0

        while True:
            line = tunlog.readline()
            if not line:
                break

            if line.startswith('#'):
                continue

            items = line.split()
            ts = float(items[0])
            event_type = items[1]
            num_bits = int(items[2]) * 8

            if first_ts is None:
                first_ts = ts

            bin_id = self.ms_to_bin(ts, first_ts)

            if event_type == '#':
                capacities[bin_id] = capacities.get(bin_id, 0) + num_bits

                if first_capacity is None:
                    first_capacity = ts

                if last_capacity is None or ts > last_capacity:
                    last_capacity = ts
            elif event_type == '+':
                if len(items) == 4:
                    flow_id = int(items[-1])
                else:
                    flow_id = 0

                self.flows[flow_id] = True

                if flow_id not in arrivals:
                    arrivals[flow_id] = {}
                    first_arrival[flow_id] = ts

                if flow_id not in last_arrival:
                    last_arrival[flow_id] = ts
                else:
                    if ts > last_arrival[flow_id]:
                        last_arrival[flow_id] = ts

                old_value = arrivals[flow_id].get(bin_id, 0)
                arrivals[flow_id][bin_id] = old_value + num_bits

                total_arrivals += num_bits
            elif event_type == '-':
                if len(items) == 5:
                    flow_id = int(items[-1])
                else:
                    flow_id = 0

                self.flows[flow_id] = True

                if flow_id not in departures:
                    departures[flow_id] = {}
                    first_departure[flow_id] = ts

                if flow_id not in last_departure:
                    last_departure[flow_id] = ts
                else:
                    if ts > last_departure[flow_id]:
                        last_departure[flow_id] = ts

                old_value = departures[flow_id].get(bin_id, 0)
                departures[flow_id][bin_id] = old_value + num_bits

                total_departures += num_bits

                # update total variables
                if total_first_departure is None:
                    total_first_departure = ts
                if (total_last_departure is None or
                        ts > total_last_departure):
                    total_last_departure = ts

                # store delays in a list for each flow and sort later
                delay = float(items[3])
                if flow_id not in self.delays:
                    self.delays[flow_id] = []
                    self.delays_t[flow_id] = []
                self.delays[flow_id].append(delay)
                self.delays_t[flow_id].append((ts - first_ts) / 1000.0)

        tunlog.close()

        us_per_bin = 1000.0 * self.ms_per_bin

        self.avg_capacity = None
        self.link_capacity = []
        self.link_capacity_t = []
        if capacities:
            # calculate average capacity
            if last_capacity == first_capacity:
                self.avg_capacity = 0
            else:
                delta = 1000.0 * (last_capacity - first_capacity)
                self.avg_capacity = sum(capacities.values()) / delta

            # transform capacities into a list
            capacity_bins = capacities.keys()
            for bin_id in range(min(capacity_bins), max(capacity_bins) + 1):
                self.link_capacity.append(
                    capacities.get(bin_id, 0) / us_per_bin)
                self.link_capacity_t.append(self.bin_to_s(bin_id))

        # calculate ingress and egress throughput for each flow
        self.ingress_tput = {}
        self.egress_tput = {}
        self.ingress_t = {}
        self.egress_t = {}
        self.avg_ingress = {}
        self.avg_egress = {}
        self.percentile_delay = {}
        self.loss_rate = {}

        total_delays = []

        for flow_id in self.flows:
            self.ingress_tput[flow_id] = []
            self.egress_tput[flow_id] = []
            self.ingress_t[flow_id] = []
            self.egress_t[flow_id] = []
            self.avg_ingress[flow_id] = 0
            self.avg_egress[flow_id] = 0

            if flow_id in arrivals:
                # calculate average ingress and egress throughput
                first_arrival_ts = first_arrival[flow_id]
                last_arrival_ts = last_arrival[flow_id]

                if last_arrival_ts == first_arrival_ts:
                    self.avg_ingress[flow_id] = 0
                else:
                    delta = 1000.0 * (last_arrival_ts - first_arrival_ts)
                    flow_arrivals = sum(arrivals[flow_id].values())
                    self.avg_ingress[flow_id] = flow_arrivals / delta

                ingress_bins = arrivals[flow_id].keys()
                for bin_id in range(min(ingress_bins), max(ingress_bins) + 1):
                    self.ingress_tput[flow_id].append(
                        arrivals[flow_id].get(bin_id, 0) / us_per_bin)
                    self.ingress_t[flow_id].append(self.bin_to_s(bin_id))

            if flow_id in departures:
                first_departure_ts = first_departure[flow_id]
                last_departure_ts = last_departure[flow_id]

                if last_departure_ts == first_departure_ts:
                    self.avg_egress[flow_id] = 0
                else:
                    delta = 1000.0 * (last_departure_ts - first_departure_ts)
                    flow_departures = sum(departures[flow_id].values())
                    self.avg_egress[flow_id] = flow_departures / delta

                egress_bins = departures[flow_id].keys()

                self.egress_tput[flow_id].append(0.0)
                self.egress_t[flow_id].append(self.bin_to_s(min(egress_bins)))

                for bin_id in range(min(egress_bins), max(egress_bins) + 1):
                    self.egress_tput[flow_id].append(
                        departures[flow_id].get(bin_id, 0) / us_per_bin)
                    self.egress_t[flow_id].append(self.bin_to_s(bin_id + 1))

            # calculate 95th percentile per-packet one-way delay
            self.percentile_delay[flow_id] = None
            if flow_id in self.delays:
                self.percentile_delay[flow_id] = np.percentile(
                    self.delays[flow_id], 95, interpolation='nearest')
                total_delays += self.delays[flow_id]

            # calculate loss rate for each flow
            if flow_id in arrivals and flow_id in departures:
                flow_arrivals = sum(arrivals[flow_id].values())
                flow_departures = sum(departures[flow_id].values())

                self.loss_rate[flow_id] = None
                if flow_arrivals > 0:
                    self.loss_rate[flow_id] = (
                        1 - 1.0 * flow_departures / flow_arrivals)

        self.total_loss_rate = None
        if total_arrivals > 0:
            self.total_loss_rate = 1 - 1.0 * total_departures / total_arrivals

        # calculate total average throughput and 95th percentile delay
        self.total_avg_egress = None
        if total_last_departure == total_first_departure:
            self.total_duration = 0
            self.total_avg_egress = 0
        else:
            self.total_duration = total_last_departure - total_first_departure
            self.total_avg_egress = total_departures / (
                1000.0 * self.total_duration)

        self.total_percentile_delay = None
        if total_delays:
            self.total_percentile_delay = np.percentile(
                total_delays, 95, interpolation='nearest')

    def flip(self, items, ncol):
        return list(itertools.chain(*[items[i::ncol] for i in range(ncol)]))

    def plot_throughput_graph(self):
        empty_graph = True
        fig, ax = plt.subplots()

        # Fill the link capacity if it exists
        if self.link_capacity:
            empty_graph = False
            ax.fill_between(
                self.link_capacity_t, 
                0, 
                self.link_capacity, 
                facecolor='linen', 
                label=f'Link Capacity (Avg: {self.avg_capacity:.2f} Mbit/s)' if self.avg_capacity else None
            )

        # Color cycle using Matplotlib's built-in color cycle
        colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
        color_i = 0

        # Plot data for each flow
        for flow_id in self.flows:
            color = colors[color_i % len(colors)]

            if flow_id in self.ingress_tput and flow_id in self.ingress_t:
                empty_graph = False
                ax.plot(
                    self.ingress_t[flow_id], 
                    self.ingress_tput[flow_id], 
                    label=f'Flow {flow_id} ingress (mean {self.avg_ingress.get(flow_id, 0):.2f} Mbit/s)',
                    color=color, 
                    linestyle='--'
                )

            if flow_id in self.egress_tput and flow_id in self.egress_t:
                empty_graph = False
                ax.plot(
                    self.egress_t[flow_id], 
                    self.egress_tput[flow_id], 
                    label=f'Flow {flow_id} egress (mean {self.avg_egress.get(flow_id, 0):.2f} Mbit/s)',
                    color=color
                )

            color_i += 1

        # If no data, warn the user and exit
        if empty_graph:
            sys.stderr.write('No valid throughput graph is generated\n')
            return

        # Configure axes labels
        ax.set_xlabel('Time (s)', fontsize=12)
        ax.set_ylabel('Throughput (Mbit/s)', fontsize=12)

        # Set title if capacity data exists
        if self.link_capacity and self.avg_capacity:
            ax.set_title(f'Average capacity {self.avg_capacity:.2f} Mbit/s (shaded region)')

        # Add grid and legend
        ax.grid(True)
        handles, labels = ax.get_legend_handles_labels()
        legend = ax.legend(
            handles[::-1], 
            labels[::-1], 
            loc='upper center', 
            bbox_to_anchor=(0.5, -0.1), 
            ncol=2, 
            fontsize=12
        )

        # Improve figure size and save with tight layout
        fig.set_size_inches(12, 6)
        fig.savefig(
            self.throughput_graph, 
            bbox_extra_artists=(legend,), 
            bbox_inches='tight', 
            pad_inches=0.2, 
            dpi=300  # Improved resolution
        )
        plt.close(fig)

    def plot_delay_graph(self):
        empty_graph = True
        fig, ax = plt.subplots()

        max_delay = 0
        # Use Matplotlib's default color cycle for better scalability
        colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
        color_i = 0

        # Plot data for each flow
        for flow_id in self.flows:
            color = colors[color_i % len(colors)]
            if flow_id in self.delays and flow_id in self.delays_t:
                empty_graph = False
                max_delay = max(max_delay, max(self.delays_t[flow_id]))

                # Use scatter plot for delays
                ax.scatter(
                    self.delays_t[flow_id],
                    self.delays[flow_id],
                    s=1,
                    color=color,
                    marker='.',
                    label=f'Flow {flow_id} (95th percentile {self.percentile_delay.get(flow_id, 0):.2f} ms)'
                )
                color_i += 1

        # Handle empty graph scenario
        if empty_graph:
            sys.stderr.write('No valid delay graph is generated\n')
            return

        # Set x-axis limit and labels
        ax.set_xlim(0, int(math.ceil(max_delay)))
        ax.set_xlabel('Time (s)', fontsize=12)
        ax.set_ylabel('Per-packet one-way delay (ms)', fontsize=12)

        # Add grid
        ax.grid(True)

        # Add legend with modernized options
        handles, labels = ax.get_legend_handles_labels()
        legend = ax.legend(
            handles[::-1],
            labels[::-1],
            scatterpoints=1,
            bbox_to_anchor=(0.5, -0.1),
            loc='upper center',
            ncol=3,
            fontsize=12,
            markerscale=2,  # Adjust marker scale for better visibility
            handletextpad=0.5  # Space between legend marker and text
        )

        # Configure figure size and save it
        fig.set_size_inches(12, 6)
        fig.savefig(
            self.delay_graph,
            bbox_extra_artists=(legend,),
            bbox_inches='tight',
            pad_inches=0.2,
            dpi=300  # Improved resolution
        )

        # Close the figure to free up memory
        plt.close(fig)

    def statistics_string(self):
        flows_str = 'flow' if len(self.flows) == 1 else 'flows'
        ret = f"-- Total of {len(self.flows)} {flows_str}:\n"

        if self.avg_capacity is not None:
            ret += f"Average capacity: {self.avg_capacity:.2f} Mbit/s\n"

        if self.total_avg_egress is not None:
            ret += f"Average throughput: {self.total_avg_egress:.2f} Mbit/s"
            if self.avg_capacity is not None:
                utilization = 100.0 * self.total_avg_egress / self.avg_capacity
                ret += f" ({utilization:.1f}% utilization)"
            ret += "\n"

        if self.total_percentile_delay is not None:
            ret += f"95th percentile per-packet one-way delay: {self.total_percentile_delay:.3f} ms\n"

        if self.total_loss_rate is not None:
            ret += f"Loss rate: {self.total_loss_rate * 100.0:.2f}%\n"

        for flow_id in self.flows:
            ret += f"-- Flow {flow_id}:\n"

            avg_egress = self.avg_egress.get(flow_id)
            if avg_egress is not None:
                ret += f"Average throughput: {avg_egress:.2f} Mbit/s\n"

            percentile_delay = self.percentile_delay.get(flow_id)
            if percentile_delay is not None:
                ret += f"95th percentile per-packet one-way delay: {percentile_delay:.3f} ms\n"

            loss_rate = self.loss_rate.get(flow_id)
            if loss_rate is not None:
                ret += f"Loss rate: {loss_rate * 100.0:.2f}%\n"

        return ret

    def run(self):
        self.parse_tunnel_log()

        if self.throughput_graph:
            self.plot_throughput_graph()

        if self.delay_graph:
            self.plot_delay_graph()

        tunnel_results = {}
        tunnel_results['throughput'] = self.total_avg_egress
        tunnel_results['delay'] = self.total_percentile_delay
        tunnel_results['loss'] = self.total_loss_rate
        tunnel_results['duration'] = self.total_duration
        tunnel_results['stats'] = self.statistics_string()

        flow_data = {}
        flow_data['all'] = {}
        flow_data['all']['tput'] = self.total_avg_egress
        flow_data['all']['delay'] = self.total_percentile_delay
        flow_data['all']['loss'] = self.total_loss_rate

        for flow_id in self.flows:
            if flow_id != 0:
                flow_data[flow_id] = {}
                flow_data[flow_id]['tput'] = self.avg_egress[flow_id]
                flow_data[flow_id]['delay'] = self.percentile_delay[flow_id]
                flow_data[flow_id]['loss'] = self.loss_rate[flow_id]

        tunnel_results['flow_data'] = flow_data

        return tunnel_results

def run(args):
    tg = TunnelGraph(tunnel_log=args.tunnel_log,
        throughput_graph=args.throughput_graph,
        delay_graph=args.delay_graph,
        ms_per_bin=args.ms_per_bin)
    tg.run()

def main():
    args = parse_tunnel_graph()

    tunnel_graph = TunnelGraph(
        tunnel_log=args.tunnel_log,
        throughput_graph=args.throughput_graph,
        delay_graph=args.delay_graph,
        ms_per_bin=args.ms_per_bin)
    tunnel_results = tunnel_graph.run()

    sys.stderr.write(tunnel_results['stats'])


if __name__ == '__main__':
    main()
