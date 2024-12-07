import re
import uuid
import numpy as np
from fpdf import FPDF
from os import path
from newpantheon.helpers import utils
from analysis import parse_report


class PDF(FPDF):
    def __init__(self, args):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=15)
        self.data_dir = path.abspath(args.data_dir)
        self.include_acklink = args.include_acklink

        metadata_path = path.join(args.data_dir, 'pantheon_metadata.json')
        self.meta = utils.load_test_metadata(metadata_path)
        # self.cc_schemes = utils.verify_schemes_with_meta(args.schemes, self.meta)

        self.run_times = self.meta['run_times']
        self.flows = self.meta['flows']
        self.config = utils.parse_config()

    def header(self):
        self.set_font("Arial", "B", 12)
        self.cell(0, 10, "Pantheon Report", align="C", ln=True)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

    def describe_metadata(self):
        self.multi_cell(0, 10, 'Generated at %s (UTC).\n\n' % utils.utc_time())

        meta = self.meta

        if meta['mode'] == 'local':
            mm_cmd = []
            if 'prepend_mm_cmds' in meta:
                mm_cmd.append(meta['prepend_mm_cmds'])
            mm_cmd += ['mm-link', meta['uplink_trace'], meta['downlink_trace']]
            if 'extra_mm_link_args' in meta:
                mm_cmd.append(meta['extra_mm_link_args'])
            if 'append_mm_cmds' in meta:
                mm_cmd.append(meta['append_mm_cmds'])

            mm_cmd = ' '.join(mm_cmd).replace('_', '\\_')

            self.multi_cell(0, 10, f"Tested in mahimahi: {mm_cmd}\n\n")
        elif meta['mode'] == 'remote':
            txt = {side: [] for side in ['local', 'remote']}
            for side in ['local', 'remote']:
                if f"{side}_desc" in meta:
                    txt[side].append(meta[f"{side}_desc"])
                if f"{side}_if" in meta:
                    txt[side].append(f"on {meta[f'{side}_if']}")
                txt[side] = ' '.join(txt[side]).replace('_', '\\_')

            if meta['sender_side'] == 'remote':
                self.multi_cell(0, 10, f"Data path: {txt['remote']} (remote) → {txt['local']} (local).\n\n")
            else:
                self.multi_cell(0, 10, f"Data path: {txt['local']} (local) → {txt['remote']} (remote).\n\n")

        if meta['flows'] == 1:
            flows = '1 flow'
        else:
            flows = f'{meta['flows']} flows with {meta['interval']}-second interval between two flows'

        if meta['runtime'] == 1:
            runtime = '1 second'
        else:
            runtime = f'{meta['runtime']} seconds'

        run_times = meta['run_times']
        if run_times == 1:
            times = 'once'
        elif run_times == 2:
            times = 'twice'
        else:
            times = '{run_times} times'

        self.multi_cell(0, 10, f"Repeated the test of {len(self.cc_schemes)} congestion control schemes {times}.\n")
        self.multi_cell(0, 10, f"Each test lasted for {runtime} running {flows}.\n\n")

        if 'ntp_addr' in meta:
            self.multi_cell(0, 10, f"NTP offsets were measured against {meta['ntp_addr']} and applied to logs.\n\n")

        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, "System info:", ln=True)

        self.set_font('Courier', '', 10)
        self.multi_cell(0, 10, f"{utils.get_sys_info().decode('utf-8')}")
        
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, "Git Summary:", ln=True)

        self.set_font('Courier', '', 10)
        self.multi_cell(0, 10, meta['git_summary'])

        # Add a page break
        self.add_page()

    def create_table(self, data):
        self.add_page(orientation="L")
        self.set_font("Arial", "B", 10)

        # Header Row
        header = ["Scheme", "# Runs"]
        for _ in range(self.flows):
            header.extend([f"Flow {_+1} Tput", f"Flow {_+1} Delay", f"Flow {_+1} Loss"])
        self.set_fill_color(200, 200, 200)
        self.cell(40, 10, "Scheme", border=1, fill=True)
        self.cell(20, 10, "# Runs", border=1, fill=True)
        for _ in range(self.flows):
            self.cell(40, 10, f"Flow {_+1} Tput", border=1, fill=True)
            self.cell(40, 10, f"Flow {_+1} Delay", border=1, fill=True)
            self.cell(40, 10, f"Flow {_+1} Loss", border=1, fill=True)
        self.ln()

        # Data Rows
        self.set_font("Arial", size=10)
        for cc in self.cc_schemes:
            flow_data = {data_t: [] for data_t in ['tput', 'delay', 'loss']}
            for data_t in ['tput', 'delay', 'loss']:
                for flow_id in range(1, self.flows + 1):
                    mean_value = np.mean(data[cc][flow_id][data_t]) if data[cc][flow_id][data_t] else "N/A"
                    flow_data[data_t].append(f"{mean_value:.2f}" if isinstance(mean_value, float) else mean_value)

            self.cell(40, 10, data[cc]['name'], border=1)
            self.cell(20, 10, str(data[cc]['valid_runs']), border=1)
            for idx in range(self.flows):
                self.cell(40, 10, flow_data['tput'][idx], border=1)
                self.cell(40, 10, flow_data['delay'][idx], border=1)
                self.cell(40, 10, flow_data['loss'][idx], border=1)
            self.ln()

        # align = ' c | c'
        # for data_t in ['tput', 'delay', 'loss']:
        #     align += ' | ' + ' '.join(['Y' for _ in range(self.flows)])
        # align += ' '

        # flow_cols = ' & '.join(
        #     ['flow %d' % flow_id for flow_id in range(1, 1 + self.flows)])

        # table_width = 0.9 if self.flows == 1 else ''
        # table = (
        #     '\\begin{landscape}\n'
        #     '\\centering\n'
        #     '\\begin{tabularx}{%(width)s\linewidth}{%(align)s}\n'
        #     '& & \\multicolumn{%(flows)d}{c|}{mean avg tput (Mbit/s)}'
        #     ' & \\multicolumn{%(flows)d}{c|}{mean 95th-\\%%ile delay (ms)}'
        #     ' & \\multicolumn{%(flows)d}{c}{mean loss rate (\\%%)} \\\\\n'
        #     'scheme & \\# runs & %(flow_cols)s & %(flow_cols)s & %(flow_cols)s'
        #     ' \\\\\n'
        #     '\\hline\n'
        # ) % {'width': table_width,
        #      'align': align,
        #      'flows': self.flows,
        #      'flow_cols': flow_cols}

        # for cc in self.cc_schemes:
        #     flow_data = {}
        #     for data_t in ['tput', 'delay', 'loss']:
        #         flow_data[data_t] = []
        #         for flow_id in range(1, self.flows + 1):
        #             if data[cc][flow_id][data_t]:
        #                 mean_value = np.mean(data[cc][flow_id][data_t])
        #                 flow_data[data_t].append('%.2f' % mean_value)
        #             else:
        #                 flow_data[data_t].append('N/A')

        #     table += (
        #         '%(name)s & %(valid_runs)s & %(flow_tputs)s & '
        #         '%(flow_delays)s & %(flow_losses)s \\\\\n'
        #     ) % {'name': data[cc]['name'],
        #          'valid_runs': data[cc]['valid_runs'],
        #          'flow_tputs': ' & '.join(flow_data['tput']),
        #          'flow_delays': ' & '.join(flow_data['delay']),
        #          'flow_losses': ' & '.join(flow_data['loss'])}

        # table += (
        #     '\\end{tabularx}\n'
        #     '\\end{landscape}\n\n'
        # )

        # return table

    def summary_table(self):
        data = {}

        re_tput = lambda x: re.match(r'Average throughput: (.*?) Mbit/s', x)
        re_delay = lambda x: re.match(
            r'95th percentile per-packet one-way delay: (.*?) ms', x)
        re_loss = lambda x: re.match(r'Loss rate: (.*?)%', x)

        for cc in self.cc_schemes:
            data[cc] = {}
            data[cc]['valid_runs'] = 0

            cc_name = self.config['schemes'][cc]['name']
            cc_name = cc_name.strip().replace('_', '\\_')
            data[cc]['name'] = cc_name

            for flow_id in range(1, self.flows + 1):
                data[cc][flow_id] = {}

                data[cc][flow_id]['tput'] = []
                data[cc][flow_id]['delay'] = []
                data[cc][flow_id]['loss'] = []

            for run_id in range(1, 1 + self.run_times):
                fname = '%s_stats_run%s.log' % (cc, run_id)
                stats_log_path = path.join(self.data_dir, fname)

                if not path.isfile(stats_log_path):
                    continue

                stats_log = open(stats_log_path)

                valid_run = False
                flow_id = 1

                while True:
                    line = stats_log.readline()
                    if not line:
                        break

                    if 'Datalink statistics' in line:
                        valid_run = True
                        continue

                    if 'Flow %d' % flow_id in line:
                        ret = re_tput(stats_log.readline())
                        if ret:
                            ret = float(ret.group(1))
                            data[cc][flow_id]['tput'].append(ret)

                        ret = re_delay(stats_log.readline())
                        if ret:
                            ret = float(ret.group(1))
                            data[cc][flow_id]['delay'].append(ret)

                        ret = re_loss(stats_log.readline())
                        if ret:
                            ret = float(ret.group(1))
                            data[cc][flow_id]['loss'].append(ret)

                        if flow_id < self.flows:
                            flow_id += 1

                stats_log.close()

                if valid_run:
                    data[cc]['valid_runs'] += 1

        return self.create_table(data)
    
    def add_figure(self, figure_path):
        """Add a figure to the PDF if it exists, otherwise add a placeholder."""
        if path.isfile(figure_path):
            self.image(figure_path, w=self.w - 20)  # Adjust width with padding
        else:
            self.set_font("Arial", size=12, style='B')
            self.cell(0, 10, "Figure is missing", align="C")
        self.ln(10)  # Add some space after the figure

    def include_summary(self):
        self.set_font("Arial", size=12)

        raw_summary = path.join(self.data_dir, 'pantheon_summary.pdf')
        mean_summary = path.join(self.data_dir, 'pantheon_summary_mean.pdf')

        metadata_desc = self.describe_metadata()
        self.multi_cell(0, 10, metadata_desc)
        self.ln(10)  # Add some space
        self.summary_table()

        if path.isfile(raw_summary):
            self.image(raw_summary, w=self.w - 20)  # Adjust width with padding
        else:
            self.cell(0, 10, "Figure is missing", align="C")
        self.ln(10)  # Add some space after the figure

        if path.isfile(mean_summary):
            self.image(mean_summary, w=self.w - 20)  # Adjust width with padding
        else:
            self.cell(0, 10, "Figure is missing", align="C")
        self.ln(10)  # Add some space after the figure

    def include_runs(self):
        cc_id = 0
        for cc in self.cc_schemes:
            cc_id += 1
            cc_name = self.config['schemes'][cc]['name'].strip().replace('_', ' ')

            for run_id in range(1, 1 + self.run_times):
                fname = f"{cc}_stats_run{run_id}.log"
                stats_log_path = path.join(self.data_dir, fname)

                if path.isfile(stats_log_path):
                    with open(stats_log_path, "r") as stats_log:
                        stats_info = stats_log.read()
                else:
                    stats_info = f"{stats_log_path} does not exist\n"

                # Add a new page for each run
                self.add_page()

                # Write statistics information
                self.set_font("Arial", style="B", size=12)
                self.cell(0, 10, f"Run {run_id}: Statistics of {cc_name}", ln=True)
                self.ln(5)

                self.set_font("Courier", size=10)
                self.multi_cell(0, 10, stats_info)
                self.ln(5)

                # Add graphs for Data Link
                self.set_font("Arial", style="B", size=12)
                self.cell(0, 10, f"Run {run_id}: Report of {cc_name} --- Data Link", ln=True)
                self.ln(5)

                link_directions = ['datalink']
                if self.include_acklink:
                    link_directions.append('acklink')

                for link_t in link_directions:
                    for metric_t in ['throughput', 'delay']:
                        graph_path = path.join(
                            self.data_dir, f"{cc}_{link_t}_{metric_t}_run{run_id}.png"
                        )

                        if path.isfile(graph_path):
                            self.image(graph_path, x=10, y=self.get_y(), w=190)
                            self.ln(70)  # Adjust the spacing based on the image size
                        else:
                            self.set_font("Arial", style="I", size=10)
                            self.cell(0, 10, f"Missing: {graph_path}", ln=True)
                            self.ln(5)

                    self.ln(5)

                # Add graphs for ACK Link (if enabled)
                if self.include_acklink:
                    self.set_font("Arial", style="B", size=12)
                    self.cell(0, 10, f"Run {run_id}: Report of {cc_name} --- ACK Link", ln=True)
                    self.ln(5)

                    for metric_t in ['throughput', 'delay']:
                        graph_path = path.join(
                            self.data_dir, f"{cc}_acklink_{metric_t}_run{run_id}.png"
                        )

                        if path.isfile(graph_path):
                            self.image(graph_path, x=10, y=self.get_y(), w=190)
                            self.ln(70)  # Adjust the spacing based on the image size
                        else:
                            self.set_font("Arial", style="I", size=10)
                            self.cell(0, 10, f"Missing: {graph_path}", ln=True)
                            self.ln(5)

    def run(self):
        report_uid = uuid.uuid4()
        pdf_path = path.join(self.data_dir, f"pantheon_report_{report_uid}.pdf")
        self.include_summary()
        self.include_runs()
        self.output(pdf_path)
        
        print(f"Saved pantheon_report.pdf in {self.data_dir}")


def main():
    args = parse_report()
    PDF(args)


if __name__ == '__main__':
    main()