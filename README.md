# A New Pantheon of Congestion Control

In 2018, Yan et al. introduced [*Pantheon: the training ground for Internet congestion-control research*]((https://www.usenix.org/conference/atc18/presentation/yan-francis)) at USENIX ATC'18. This paper proposed a novel testbed designed to enable reproducible evaluation of internet transport protocols, providing a valuable tool for network researchers to test and refine their ideas. Since its release, Pantheon has been widely adopted in the [research community](https://scholar.google.com/scholar?oi=bibs&hl=en&cites=7172685335945405090).

However, the original Pantheon codebase, written in Python 2, has become outdated, with Python 2 reaching end-of-life in 2020. According to the [project's website](https://pantheon.stanford.edu/), Pantheon is no longer maintained, and no new congestion-control schemes or experiments are being accepted. This repository offers a reimplementation of Pantheon, updated to Python 3, incorporating modern dependencies, and following current software engineering best practices.

## Development

This project is managed using [Hatch](https://hatch.pypa.io/latest/), which is the official project manager recommended by the Python Packaging Authority (PyPA). See instructions on installing Hatch [here](https://hatch.pypa.io/latest/install/).

With Hatch installed, you can create the developement environment by running:
```
hatch env create dev
```
This creates a new environment with all of the dependencies specified in the [pyproject.toml](./pyproject.toml) file, as well as the dev dependencies. Then, activate the new environment by running:
```
hatch shell dev
```
Lastly, you may need to install NewPantheon in that environment by running:
```
pip install -e .
```
from the top-level directory of this repository.

### Installing Mahimahi

To run tests locally, you'll need a network emulator; currently, Mahimahi is supported.

You can find instructions on downloading and installing Mahimahi on [their website](http://mahimahi.mit.edu/).

After installing Mahimahi, you should be able to run `mm-delay 50 mm-loss uplink 0.2` from the terminal to spawn a Mahimahi shell.

## Experiments

To run the experiments, you can run
```sh
python src/newpantheon/__main__.py experiment test local --scheme <scheme>
```
where `<scheme>` is a CC scheme with a corresponding wrapper in `src/newpantheon/wrappers`.

Alternatively, you can replace `--scheme <scheme>` with `--all` to run all supported CC algorithms in sequence.

### Testing CC Scheme Interactions (New)

To test interactions between different CC schemes, you need run NewPantheon in *configuration* mode, where you pass a pre-defined *configuration* file.

A configuration file is a YAML file with the following format:
```yaml
test-name: test
flows:
  - scheme: cubic
  - scheme: vegas
```

With this file you can run:
```sh
python src/newpantheon/__main__.py experiment test -c test_config.yml local --all --data-dir output_dir
```

Note: you must specify a output directory in this case.

## Analysis

To run analysis, use the following command:
```sh
python src/newpantheon/__main__.py analysis --data-dir DIR
```

`--data-dir` is optional, the default is `src/tmp`

If you want to run analysis for interacting schemes, you can use the `--interactions` flag, as shown below.
```sh
python src/newpantheon/__main__.py analysis --data-dir DIR --interactions
```

## Acknowledgements

Much of the code in this repository stems from refactoring and updating the original [Pantheon codebase](https://github.com/StanfordSNR/pantheon). The original Pantheon paper was written by Francis Y. Yan, Jestin Ma, Greg D. Hill, Deepti Raghavan, Riad S. Wahby, Philip Levis, and Keith Winstein of Stanford University and the Massachusetts Institute of Technology, and presented at the 2018 USENIX Annual Technical Conference. 
