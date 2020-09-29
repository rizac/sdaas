# sdaas

(**s**)eismic (**d**)ata (and metadata) (**a**)mplitude (**a**)nomaly (**s**)core


Simple program to compute amplitude anomaly scores in seismic data and metadata.
Given a set of waveforms and their metadata, it removes the waveform response
and returns the relative anomaly score computed on the waveform amplitudes.

This program can be used to filter out a set of  malformed waveforms,
or to check the correctness of the metadata fields (e.g. Station inventory xml)
by checking the anomaly score on a set of station recordings.



## Installation

Always work within a virtual environment. From a terminal, in the directory
where you cloned this repository (last argument of `git clone`),

1. create a virtual environment (once):

```bash
python -m venv .env
```

2. activate it (to be done also every time you use this program):
```bash
source .env/bin/activate
```
(then to deactivate, simply type ... `deactivate` on the terminal). 

#### 1. with requirements.txt (recommended on a new, empty virtual environment where you plan to use this program only)

```bash
pip install --upgrade pip && pip install "numpy==1.15.4" && pip install -r ./requirements.txt && pip install -e .
```
(-e is optional)

This is the safest option, as it installs all dependencies with a specific tested version.
**However it will override already installed dependencies, if present in the virtual environment**


#### 2. with setup.py (recommended if you already have stuff installed in your virtual environment)

```bash
pip install --upgrade pip && pip install "numpy>=1.15.4" && pip install -e .
```
(-e is optional)

Less safe option as it installs all dependencies with the newest available.
Consenquently, something which might not work (we do our best but we cannot keep
up rapidly with all libraries updates, fix the new errors in our code, their
deprecation warnings, and so on). **However it will NOT necessarily override
already installed dependencies, if present in the virtual environment**
(not that scikit is in any case installed with a specific version 0.21.3,
necessary to load the model trained with that version)


## Usage


### As command line application

Activate your virtual environment (see above), and then to use the program
as command line application. You can compute scores from a given station(s), all stations
from given network(s), a single waveform segment,  You can always type `sdaas --help` for details


Example (compute scores from randomly selected segments of a givens station and channel):

```bash
>>> sdaas "http://geofon.gfz-potsdam.de/fdsnws/station/1/query?net=GE&sta=BKB&cha=BH?&start=2016-01-01&level=response" -v -c -th 0.7

[███████████████████████████████████████████████████████████████]  100%  0d 00:00:00

GE.EIL..BHN    2019-07-26T05:01:45  2019-07-26T05:04:20  0.45  0
GE.EIL..BHE    2019-07-26T05:01:54  2019-07-26T05:04:10  0.43  0
GE.EIL..BHZ    2019-07-26T05:01:57  2019-07-26T05:04:10  0.43  0
GE.EIL..BHN    2019-11-23T17:49:44  2019-11-23T17:52:00  0.83  1
GE.EIL..BHE    2019-11-23T17:49:36  2019-11-23T17:52:28  0.83  1
GE.EIL..BHZ    2019-11-23T17:49:59  2019-11-23T17:52:16  0.66  1
```

### As library in Python code
Assuming you have one or more [Stream](https://docs.obspy.org/packages/autogen/obspy.core.stream.Stream.html)
or [Trace](https://docs.obspy.org/packages/autogen/obspy.core.trace.Trace.html),
with relative [Inventory](https://docs.obspy.org/packages/obspy.core.inventory.html), then

<!--AUTO GENERATED SNIPPET DO NOT EDIT -->
<!-- (see tests/test_and_create_readme_snippet.py for details) -->

|Function|easy import|source (in the borwser, try to click for details)|
| --- | --- | --- |
|aa_scores|`from sdaas.core import aa_scores`|```sdaas.core.model.aa_scores```|
|psd_values|`from sdaas.core import psd_values`|```sdaas.core.psd.psd_values```|
|streams_features|`from sdaas.core import streams_features`|```sdaas.core.features.streams_features```|
|streams_idfeatures|`from sdaas.core import streams_idfeatures`|```sdaas.core.features.streams_idfeatures```|
|streams_idscores|`from sdaas.core import streams_idscores`|```sdaas.core.model.streams_idscores```|
|streams_scores|`from sdaas.core import streams_scores`|```sdaas.core.model.streams_scores```|
|trace_features|`from sdaas.core import trace_features`|```sdaas.core.features.trace_features```|
|trace_idfeatures|`from sdaas.core import trace_idfeatures`|```sdaas.core.features.trace_idfeatures```|
|trace_score|`from sdaas.core import trace_score`|```sdaas.core.model.trace_score```|
|traces_features|`from sdaas.core import traces_features`|```sdaas.core.features.traces_features```|
|traces_idfeatures|`from sdaas.core import traces_idfeatures`|```sdaas.core.features.traces_idfeatures```|
|traces_idscores|`from sdaas.core import traces_idscores`|```sdaas.core.model.traces_idscores```|
|traces_scores|`from sdaas.core import traces_scores`|```sdaas.core.model.traces_scores```|

**Examples**: Compute the scores in a stream or iterable of traces (e.g. list. tuple):
```python
>>> from sdaas.core import traces_scores
>>> traces_scores(stream, inventory)
array([ 0.47900702,  0.46478282,  0.44947399])
```

Compute the scores in a stream or iterable of traces, getting also the traces id (seed_id, start, end):
```python
>>> from sdaas.core import traces_idscores
>>> traces_idscores(stream, inventory)
([('GE.FLT1..HHE', datetime.datetime(2011, 9, 3, 16, 38, 5, 550001), datetime.datetime(2011, 9, 3, 16, 42, 12, 50001)), ('GE.FLT1..HHN', datetime.datetime(2011, 9, 3, 16, 38, 5, 760000), datetime.datetime(2011, 9, 3, 16, 42, 9, 670000)), ('GE.FLT1..HHZ', datetime.datetime(2011, 9, 3, 16, 38, 8, 40000), datetime.datetime(2011, 9, 3, 16, 42, 9, 670000))], array([ 0.47900702,  0.46478282,  0.44947399]))
```

Same as above, with custom id function given as the seed id (`trace.get_id()` in ObsPy):
```python
>>> from sdaas.core import traces_idscores
>>> traces_idscores(stream, inventory, idfunc=lambda t: t.get_id())
(['GE.FLT1..HHE', 'GE.FLT1..HHN', 'GE.FLT1..HHZ'], array([ 0.47900702,  0.46478282,  0.44947399]))
```

You can also compute scores and ids from terable of streams (e.g., when reading from files)...
```python
>>> from sdaas.core import streams_scores
>>> from sdaas.core import streams_idscores
```

... or from a single trace:
```python
>>> from sdaas.core import trace_score
```

Getting anomaly score from several streams
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

*Note* `trace_features` returns a vector (numpy array) representing
a given trace and which is used as input of our machine learning Isolation Forest algorithm.
Currently, it consists of a mono-dimensional vector (numpy array of length 1)
of the waveform power spectral density (PSD) computed at 5 s period.
`aa_scores` is the low-level function that computes amplitude anomaly score from an array
of feature vectors (Nx1 numpy array)

<!-- END AUTOGENERATED SNIPPET -->