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

**Example 1**: to compute the traces scores in a stream or iterable of traces (e.g. list. tuple):

```python
>>> from sdaas.core import traces_scores
>>> traces_scores(stream, inventory)
array([ 0.47279325,  0.46220043,  0.44874805])
```

**Example 2**: to compute the traces scores in an iterable of streams (e.g., when reading from files)

```python
>>> from sdaas.core import streams_scores
>>> streams_scores(streams, inventory)
array([ 0.47279325,  0.46220043,  0.44874805,  0.51276321,  0.43225043, 0.74856103])
```

**Example 3**: to compute the traces ids and scores in a stream or iterable of traces (e.g. list. tuple):
(ids are tuples of the form (trace_id:str, trace_start:datetime, trace_end:datetime))

```python
>>> from sdaas.core import traces_idscores
>>> traces_idscores(stream, inventory)
([('GE.FLT1..HHE', datetime.datetime(2011, 9, 3, 16, 38, 5, 550001), datetime.datetime(2011, 9, 3, 16, 40, 5, 450001)), ... ], array([ 0.47279325, ... ]))
```

**Example 4**: to compute the traces ids and scores on an iterable of streams (e.g., when reading from files)
(ids are tuples of the form (trace_id:str, trace_start:datetime, trace_end:datetime))

```python
>>> from sdaas.core import streams_idscores
>>> streams_idscores(streams, inventory)
([('GE.FLT1..HHE', datetime.datetime(2011, 9, 3, 16, 38, 5, 550001), datetime.datetime(2011, 9, 3, 16, 40, 5, 450001)), ... ], array([ 0.47279325, ... ]))
```

*(Note: the last two functions have an optionl argument `idfunc=lambda trace: custom_trace_id` for customizing the returned trace id)*


**Example 5** (Performance hint):
All functions computing the anomaly score from an ObsPy Trace or Stream
first transform the given object into a feature vector via
the functions implemented in the `sdaas.core.features` module. The feature computation
is the time consuming part and can not be further optimized. However, the function computing scores
from the given features is faster if you can call it once 
and not in a loop (same principle of many numpy functions).

Example script

```python
import time
from sdaas.core import trace_features, trace_score, traces_scores, streams_scores,\
    scores 


print(f"Computing scores on {N} Streams")


# method 1 (standard)
t = time.time()
scores = streams_scores(streams, metadata)
print(f'1)  `streams_scores`: {(time.time() - t):.2f}s')


print('To obtain the same results with more control over the loop,\n'
      'check these alternative options:')


# method 2a (same as method 1, compute scores once avoiding loops)
t = time.time()
feats = []
for stream in streams:
    for trace in stream:
        feats.append(trace_features(trace, metadata))
scores = scores(feats)
print(f'2a) `trace_features` within loop + `scores`: {(time.time() - t):.2f}s')


# method 2b (same as 2a, compute scores in loop. Less performant)
scores_ = []
t = time.time()
for stream in streams:
    scores_.extend(traces_scores(stream, metadata))
scores_ = np.array(scores_)
print(f'2b) `traces_score` within loop: {(time.time() - t):.2f}s')


# method 2c (same as 2a, compute scores in loop, even less performant)
scores_ = []
t = time.time()
for stream in streams:
    for trace in stream:
        scores_.append(trace_score(trace, metadata))
scores_ = np.array(scores_)
print(f'2c) `trace_score` within loop: {(time.time() - t):.2f}s')
```

Output:

```
>>> Computing scores on 10 Streams
1)  `streams_scores`: 0.43s
To obtain the same results with more control over the loop,
check these alternative options:
2a) `trace_features` within loop + `scores`: 0.43s
2b) `traces_score` within loop: 1.06s
2c) `trace_score` within loop: 2.49s
```
