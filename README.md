# sdaas

**S**eismic **D**ata (and metadata) **A**mplitude **A**nomaly **S**core

<img align="right" width="27%" src="outlierspaper-img004.png"><img align="right"  width="29%" src="outlierspaper-img005.png">

Simple program to compute amplitude anomaly scores in seismic data and metadata.
Given a set of waveforms and their metadata, it removes the waveform response
and returns the relative anomaly score computed on the waveform amplitudes.

This program can be used to filter out a set of  malformed waveforms,
or to check the correctness of the metadata fields (e.g. Station inventory xml)
by checking the anomaly score on a set of station recordings. 


## Installation

Always work within a virtual environment. From a terminal, in the directory
where you cloned this repository (last argument of `git clone`),

1. create a virtual environment (once). **Be sure you use Python>=3.7 (Type `python3 --version` to check)**:

```bash
python3 -m venv .env
```

2. activate it (to be done also every time you use this program):
```bash
source .env/bin/activate
```
(then to deactivate, simply type ... `deactivate` on the terminal). 

Then, you have two options:

#### 1. with requirements.txt (recommended on a new, empty virtual environment where you plan to use this program only)

```bash
pip install --upgrade pip && pip install "numpy==1.15.4" && pip install -r ./requirements.txt && pip install -e .
```
(-e is optional)

<!-- This installs all dependencies with a specific tested version, meaning that this
program is certain to work, but already installed programs *might* break -->


#### 2. with setup.py (recommended if this program is needed togehter with other packages in your virtual environment)

```bash
pip install --upgrade pip && pip install "numpy>=1.15.4" && pip install -e .
```
(-e is optional)

<!-- This installs all dependencies with a *minimum required* version, and thus already
installed packages *are more likely* to continue working. However, there is a
slightly higher chance that this program doe not work properly (we do our best but we cannot keep
up rapidly with all libraries updates, fix the new errors in our code, their
deprecation warnings, and so on. Note that scikit-learn is in any case installed with
a specific version 0.21.3, necessary to load the model trained with that version) -->


## Usage


### As command line application

After activating your virtual environment (see above) you can access the program as
command line application in your terminal by typing `sdaas`. The application
can compute the score(s) of a single miniSEED file, a directory of miniSEED files, or 
a FDSN url ([dataselect or station](https://www.fdsn.org/webservices/) url). **Type `sdaas --help` for details**


**Example**

1. Compute scores from randomly selected segments of a givens station and channel (`-v` verbose, print additional messages to `stderr`):

```bash
>>> sdaas "http://geofon.gfz-potsdam.de/fdsnws/station/1/query?net=GE&sta=BKB&cha=BH?&start=2016-01-01" -v
[███████████████████████████████████████████████████████████████]  100%  0d 00:00:00
Output columns: | waveform_id | waveform_start | waveform_end | anomaly_score |
GE.EIL..BHN    2019-07-26T05:01:45  2019-07-26T05:04:20  0.45
GE.EIL..BHE    2019-07-26T05:01:54  2019-07-26T05:04:10  0.43
GE.EIL..BHZ    2019-07-26T05:01:57  2019-07-26T05:04:10  0.43
GE.EIL..BHN    2019-11-23T17:49:44  2019-11-23T17:52:00  0.83
GE.EIL..BHE    2019-11-23T17:49:36  2019-11-23T17:52:28  0.83
GE.EIL..BHZ    2019-11-23T17:49:59  2019-11-23T17:52:16  0.66
```
*(note: when providing a station url, as in the example above, the only required URL argument is `net`/`network`)*

2. Same as above, but provide also a user-defined threshold (parameter `-th`),
which will also add an additional last column  (1:outlier, 0:inlier)

```bash
>>> sdaas "http://geofon.gfz-potsdam.de/fdsnws/station/1/query?net=GE&sta=BKB&cha=BH?&start=2016-01-01" -v -th 0.7
[███████████████████████████████████████████████████████████████]  100%  0d 00:00:00
Output columns: | waveform_id | waveform_start | waveform_end | anomaly_score | anomaly |
GE.EIL..BHN    2019-07-26T05:01:45  2019-07-26T05:04:20  0.45  0
GE.EIL..BHE    2019-07-26T05:01:54  2019-07-26T05:04:10  0.43  0
GE.EIL..BHZ    2019-07-26T05:01:57  2019-07-26T05:04:10  0.43  0
GE.EIL..BHN    2019-11-23T17:49:44  2019-11-23T17:52:00  0.83  1
GE.EIL..BHE    2019-11-23T17:49:36  2019-11-23T17:52:28  0.83  1
GE.EIL..BHZ    2019-11-23T17:49:59  2019-11-23T17:52:16  0.66  1
```

2. Same as the first example, but compute and return the score median (on a channel base):

```bash
>>> sdaas "http://geofon.gfz-potsdam.de/fdsnws/station/1/query?net=GE&sta=BKB&cha=BH?&start=2016-01-01" -v -agg median
[███████████████████████████████████████████████████████████████]  100%  0d 00:00:00
Output columns: | waveform_id | waveform_start | waveform_end | anomaly_score |
GE.EIL..BHN    2019-07-26T05:01:45  2019-07-26T05:04:20  0.62
GE.EIL..BHE    2019-07-26T05:01:54  2019-07-26T05:04:10  0.63
GE.EIL..BHZ    2019-07-26T05:01:57  2019-07-26T05:04:10  0.44
```

### As library in your Python code

This software can also be used as library in Python code (e.g. Jupyter Notebook)
to work with [ObsPy](https://docs.obspy.org/) objects (ObsPy is already included in the installation):
assuming you have one or more [Stream](https://docs.obspy.org/packages/autogen/obspy.core.stream.Stream.html)
or [Trace](https://docs.obspy.org/packages/autogen/obspy.core.trace.Trace.html),
with relative [Inventory](https://docs.obspy.org/packages/obspy.core.inventory.html), then

<!--AUTO GENERATED SNIPPET DO NOT EDIT -->
<!-- (see tests/test_and_create_readme_snippet.py for details) -->

**Examples**: Compute the scores in a stream or iterable of traces (e.g. list. tuple):
```python
>>> from sdaas.core import traces_scores
>>> traces_scores(stream, inventory)
array([ 0.47900702,  0.46478282,  0.44947399])
```

Compute the scores in a stream or iterable of traces, getting also the traces id (by default the tuple `(seed_id, start, end)`, where
seed_id is [the Trace SEED identifier](https://docs.obspy.org/packages/autogen/obspy.core.trace.Trace.get_id.html)):
```python
>>> from sdaas.core import traces_idscores
>>> traces_idscores(stream, inventory)
([('GE.FLT1..HHE', datetime.datetime(2011, 9, 3, 16, 38, 5, 550001), datetime.datetime(2011, 9, 3, 16, 42, 12, 50001)), ('GE.FLT1..HHN', datetime.datetime(2011, 9, 3, 16, 38, 5, 760000), datetime.datetime(2011, 9, 3, 16, 42, 9, 670000)), ('GE.FLT1..HHZ', datetime.datetime(2011, 9, 3, 16, 38, 8, 40000), datetime.datetime(2011, 9, 3, 16, 42, 9, 670000))], array([ 0.47900702,  0.46478282,  0.44947399]))
```

Same as above, with custom traces id (their SEED identifier only):
```python
>>> from sdaas.core import traces_idscores
>>> traces_idscores(stream, inventory, idfunc=lambda t: t.get_id())
(['GE.FLT1..HHE', 'GE.FLT1..HHN', 'GE.FLT1..HHZ'], array([ 0.47900702,  0.46478282,  0.44947399]))
```

You can also compute scores and ids from iterables of streams (e.g., when reading from files)...
```python
>>> from sdaas.core import streams_scores
>>> from sdaas.core import streams_idscores
```

... or from a single trace:
```python
>>> from sdaas.core import trace_score
```

For instance, to compute the anomaly score of several streams
(for each stream and for each trace therein, return the trace anomaly score):
```python
>>> from sdaas.core import streams_scores
>>> streams_scores(streams, inventory)
array([ 0.47900702,  0.46478282,  0.44947399,  0.47900702,  0.46478282,
        0.44947399,  0.47900702,  0.46478282,  0.44947399,  0.47900702,
        0.46478282,  0.44947399,  0.47900702,  0.46478282,  0.44947399])
```

Same as above, computing the features and the scores separately for more control (note that for better performances, scores are computed once on all features and not inside a for loop):
```python
>>> from sdaas.core import trace_features, aa_scores
>>> feats = []
>>> for stream in streams:
>>>     for trace in stream:
>>>         feats.append(trace_features(trace, inventory))
>>> aa_scores(feats)
array([ 0.47900702,  0.46478282,  0.44947399,  0.47900702,  0.46478282,
        0.44947399,  0.47900702,  0.46478282,  0.44947399,  0.47900702,
        0.46478282,  0.44947399,  0.47900702,  0.46478282,  0.44947399])
```

*Note* `trace_features` returns a vector (numpy array) of numeric features representing
a given trace and which is used as input of our machine learning model using the Isolation Forest algorithm.
Currently, it is a mono-dimensional vector (numpy array of length 1) calculating as
only feature the waveform power spectral density (PSD) in dB computed at 5s period.
`aa_scores` is the low-level function that computes amplitude anomaly score from an array
of N feature vectors (Nx1 numpy array)

<!-- END AUTOGENERATED SNIPPET -->
