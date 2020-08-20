# sdaas

(**s**)eismic (**d**)ata (and metadata) (**a**)mplitude (**a**)nomaly (**s**)core


Simple program to compute amplitude anomaly scores in seismic data and metadata.
Given a set of waveforms and their metadata, it removes the waveform response and returns
the relative anomaly score computed on the waveform amplitudes.

This program can be used to filter out a set of  malformed waveforms,
or to check the correctness of the metadata fields (e.g. Station inventory xml)
by checking the anomaly score on a set of station recordings.



## Installation

Always work within a virtual environment.
Assuming you are on a terminal,
in the directory where you cloned this repository,

1. create a virtual environment (once):

```bash
python -m venv .env
```

2. activate it (every time you use this program, including also before installing it, see below):
```bash
source .env/bin/activate
```
(then to deactivate, simply type ... `deactivate` on the terminal). 

#### 1. with requirements.txt

```bash
pip install --upgrade pip && pip install -r ./requirements.txt
```

Pros:
  - safest and always working solution (this is why is recommended)

Cons: 
  - The program from the terminal must be invoked via `python sdaas/run.py` (quite verbose)
  - If the virtual environment is new (usual case), skip this point. Otherwise, if it already has stuff installed,
    then you might override specific versions with this program's versions

#### 2. with setup.py

```bash
pip install --upgrade pip && pip install "numpy>=1.15.4" && python setup.py install
```

Pros:
  - The program from the terminal can be invoked via `sdaas` (simpler)
  - If the virtual environment is new (usual case), skip this point. Otherwise, if it already has stuff installed,
    there are less chances of version conflicts (although note that scikit-learn is installed with a specific version
    (required to open the saved Isolation Forest model) and thus it might override already installed libraries)

Cons: 
  - Higher chance of using libraries with newer versions and thus untested/unexpected behaviour (we do our best
    but we cannot keep up rapidly with all libraries updates, fix the new errors in our code,
    their deprecation warnings, and so on)



## Usage

As command line, type `sdaas --help` or `python sdaas/run.py --help` (depending
on the installation above).

Example(s):

```bash
python sdaas/run.py "http://geofon.gfz-potsdam.de/fdsnws/station/1/query?net=GE&sta=BKB&cha=BH?&start=2016-01-01&level=response" -c -th 0.7
```

or:

```bash
sdaas "http://geofon.gfz-potsdam.de/fdsnws/station/1/query?net=GE&sta=BKB&cha=BH?&start=2016-01-01&level=response" -c -th 0.7
```
