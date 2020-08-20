# sdaas

(**s**)eismic (**d**)ata (and metadata) (**a**)mplitude (**a**)nomaly (**s**)core


Simple program to compute amplitude anomaly scores in seismic data and metadata.
Given a set of waveforms and their metadata, it removes the waveform response and returns
the relative anomaly score computed on the waveform amplitudes.

This program can be used to filter out a set of  malformed waveforms,
or to check the correctness of the metadata fields (e.g. Station inventory xml)
by checking the anomaly score on a set of station recordings.



## Installation

Always work within a virtual environment:

To create a virtual environment (once):

```bash
python -m venv .env
```

To activate it (every time you use this program, including also before installing it, see below):
```bash
source .env/bin/activate
```
(then to deactivate, simply type ... `deactivate` on the terminal). 

### With requirements.txt

```bash
pip install -r ./requirements.txt
```

PROS: simplest and always working solution
CONS: 
	- The program from the terminal can be invoked via `python sdaas/run.py` (quite verbose)
	- If the virtual environment has already stuff installed, then you might override specific versions
      with this program versions

### With setup.py

```bash
pip install --upgrade pip && pip install "numpy>=1.15.4" && python setup.py install
```

PROS:
	- The program from the terminal can be invoked via `sdaas` (simpler)
 	- Less chance to interfere with already installed libraries and their versions
CONS: 
  - High chance of using libraries with untested/unexpected behaviour (we cannot keep up
    with all the updates every library has, their deprecation warnings, and their refactored code)

Alternatively, with this command you



## Usage

As command line, type `sdaas --help` or `python sdaas/run.py --help` (depending
on the installation above). Example(s):

Examples:

```bash
python sdaas/run.py "http://geofon.gfz-potsdam.de/fdsnws/station/1/query?net=GE&sta=BKB&cha=BH?&start=2016-01-01&level=response" -c -th 0.7
```

or:

```bash
sdaas "http://geofon.gfz-potsdam.de/fdsnws/station/1/query?net=GE&sta=BKB&cha=BH?&start=2016-01-01&level=response" -c -th 0.7
```
