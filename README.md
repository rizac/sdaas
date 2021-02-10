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

Install the program (You could simply run:
`pip install --upgrade pip && pip install "numpy>=1.15.4" && pip install -e .`,
but we suggest to run commands separately because installation
problems are easier to track down).

pip (python package installer, just upgrade)
```
pip install --upgrade pip setuptools 
```

numpy (scientific computing library) :
```
pip install "numpy>=1.15.4"
```

obspy (seismological library):
```
pip install "obspy>=1.1.1'"
```

scikit (machine learning library. Here we will be strict about the version because of
[model persistence](https://scikit-learn.org/stable/modules/model_persistence.html)):
```
pip install "scikit-learn==0.21.3"
```

**Important**: Due to the specific version to be installed,
scikit might have problems installing, especially on MacOS. 

Few hints here:
- you might need to preinstall `cython` (`pip install cython`)
- you might need to `brew install libomp`, set the follwing env variables:
  ```
  export CC=/usr/bin/clang;export CXX=/usr/bin/clang++;export CPPFLAGS="$CPPFLAGS -Xpreprocessor -fopenmp";export CFLAGS="$CFLAGS -I/usr/local/opt/libomp/include";export CXXFLAGS="$CXXFLAGS -I/usr/local/opt/libomp/include";export LDFLAGS="$LDFLAGS -Wl,-rpath,/usr/local/opt/libomp/lib -L/usr/local/opt/libomp/lib -lomp"
  ```
- and then install with the following flags:
  ```
  pip install --verbose --no-build-isolation "scikit-learn==0.21.3"
  ```

**(For any further detail, see
[scikit-learn installation page](https://scikit-learn.org/dev/developers/advanced_installation.html))**


And finally, install this package
```
pip install -e .
```
 (-e is optional. With -e, you just need a `git pull` to update
to the last release. Without it, you need to pull and re-install `pip install --force .`)

<!-- IMOPORTANT NOTE: IT IS NOT TRUE THAT REQUIREMENTS.TXT IS ALWAYS SAFER, 
AS THERE COULD BE NEWER OS VERSION FOR WHICH YOU NEED TO UPGRADE SOME PACKAGES
BECAUSE THE SPECIFIED  ONE DO NOT WORK ANYMORE. IT WAS THE CASE WITH opsy
1.15.4 MacOs Big Sur and Python 3.9.1 -->

<!-- Then, you have two options:

#### 1. with setup.py (recommended if this program is needed together with other packages in your virtual environment)

```bash
pip install --upgrade pip && pip install "numpy>=1.15.4" && pip install -e .
```
(-e is optional)

Troubleshooting:

Note in case of scikit-learn errors, you might



#### 1. with requirements.txt (recommended on a new, empty virtual environment where you plan to use this program only)

```bash
pip install --upgrade pip && pip install "numpy==1.15.4" && pip install -r ./requirements.txt && pip install -e .
```
(-e is optional)
 -->

#### Run tests

```bash
python -m unittest         
```

## Usage


### As command line application

After activating your virtual environment (see above) you can access the program as
command line application in your terminal by typing `sdaas`. The application
can compute the score(s) of a single miniSEED file, a directory of miniSEED files, or 
a FDSN url ([dataselect or station](https://www.fdsn.org/webservices/) url).

**Please type `sdaas --help` for details and usages not covered in the examples below**


**Examples**

Compute scores from randomly selected segments of a given station and channel

```bash
>>> sdaas "http://geofon.gfz-potsdam.de/fdsnws/station/1/query?net=GE&sta=EIL&cha=BH?&start=2019-01-01" -v
[███████████████████████████████████████████████████████████████]  100%  0d 00:00:00
Output columns: | waveform_id | waveform_start | waveform_end | anomaly_score |
GE.EIL..BHN    2019-07-26T05:01:45  2019-07-26T05:04:20  0.45
GE.EIL..BHE    2019-07-26T05:01:54  2019-07-26T05:04:10  0.43
GE.EIL..BHZ    2019-07-26T05:01:57  2019-07-26T05:04:10  0.43
GE.EIL..BHN    2019-11-23T17:49:44  2019-11-23T17:52:00  0.83
GE.EIL..BHE    2019-11-23T17:49:36  2019-11-23T17:52:28  0.83
GE.EIL..BHZ    2019-11-23T17:49:59  2019-11-23T17:52:16  0.66
```
*(notes: when providing a station url, as in the example above, the only required query argument is `net`/`network`.
The paremeter `-v` / verbose prints additional info before the scores table)*

Same as above, but provide also a user-defined threshold (parameter `-th`),
which will also add an additional last column "anomaly" denoting the class label (1:outlier, 0:inlier)

```bash
>>> sdaas "http://geofon.gfz-potsdam.de/fdsnws/station/1/query?net=GE&sta=EIL&cha=BH?&start=2019-01-01" -v -th 0.7
[███████████████████████████████████████████████████████████████]  100%  0d 00:00:00
Output columns: | waveform_id | waveform_start | waveform_end | anomaly_score | anomaly |
GE.EIL..BHN    2019-07-26T05:01:45  2019-07-26T05:04:20  0.45  0
GE.EIL..BHE    2019-07-26T05:01:54  2019-07-26T05:04:10  0.43  0
GE.EIL..BHZ    2019-07-26T05:01:57  2019-07-26T05:04:10  0.43  0
GE.EIL..BHN    2019-11-23T17:49:44  2019-11-23T17:52:00  0.83  1
GE.EIL..BHE    2019-11-23T17:49:36  2019-11-23T17:52:28  0.83  1
GE.EIL..BHZ    2019-11-23T17:49:59  2019-11-23T17:52:16  0.66  1
```

Same as the first example, but compute and return the score median (on a channel base):

```bash
>>> sdaas "http://geofon.gfz-potsdam.de/fdsnws/station/1/query?net=GE&sta=EIL&cha=BH?&start=2019-01-01" -v -agg median
[███████████████████████████████████████████████████████████████]  100%  0d 00:00:00
Output columns: | waveform_id | waveform_start | waveform_end | anomaly_score |
GE.EIL..BHN    2019-07-26T05:01:45  2019-11-23T17:52:00  0.62
GE.EIL..BHE    2019-07-26T05:01:54  2019-11-23T17:52:28  0.63
GE.EIL..BHZ    2019-07-26T05:01:57  2019-11-23T17:52:16  0.44
```

Same as above, but save the scores table to CSV via the parameter `-sep` and
`>` (normal redirection of the standard output `stdout` to file)

```bash
>>> sdaas "http://geofon.gfz-potsdam.de/fdsnws/station/1/query?net=GE&sta=EIL&cha=BH?&start=2019-01-01" -v -sep "," > /path/to/myfile.csv
[███████████████████████████████████████████████████████████████]  100%  0d 00:00:00
Output columns: | waveform_id | waveform_start | waveform_end | anomaly_score |
```
*(note: only the scores table is output to `stdout`. Everything else is printed to 
`stderr` and thus should still be visible on the terminal, as in the example above)*

### As library in your Python code

<!-- 
IMPORTANT: THE PYTHON CODE SNIPPETS BELOW ARE AUTOGENERATED. TO ADD A NEW CODE 
SNIPPET, See SEE tests/test_and_create_readme_snippet.py module docstring
-->

This software can also be used as library in Python code (e.g. Jupyter Notebook)
to work with [ObsPy](https://docs.obspy.org/) objects (ObsPy is already included in the installation):
assuming you have one or more [Stream](https://docs.obspy.org/packages/autogen/obspy.core.stream.Stream.html)
or [Trace](https://docs.obspy.org/packages/autogen/obspy.core.trace.Trace.html),
with relative [Inventory](https://docs.obspy.org/packages/obspy.core.inventory.html), then

Compute the scores in a stream or iterable of traces (e.g. list. tuple, generator):
<!-- THE CODE SNIPPET BELOW IS AUTOGENERATED WHEN RUNNING TESTS. SEE tests/test_and_create_readme_snippet.py -->
```python
>>> from sdaas.core import traces_scores
>>> traces_scores(stream, inventory)
array([ 0.47900702,  0.46478282,  0.44947399])
```



Compute the scores in a stream or iterable of traces, getting also the traces id (by 
default the tuple `(seed_id, start, end)`, where seed_id is the 
[Trace SEED identifier](https://docs.obspy.org/packages/autogen/obspy.core.trace.Trace.get_id.html)):
<!-- THE CODE SNIPPET BELOW IS AUTOGENERATED WHEN RUNNING TESTS. SEE tests/test_and_create_readme_snippet.py -->
```python
>>> from sdaas.core import traces_idscores
>>> traces_idscores(stream, inventory)
([('GE.FLT1..HHE', datetime.datetime(2011, 9, 3, 16, 38, 5, 550001), datetime.datetime(2011, 9, 3, 16, 42, 12, 50001)), ('GE.FLT1..HHN', datetime.datetime(2011, 9, 3, 16, 38, 5, 760000), datetime.datetime(2011, 9, 3, 16, 42, 9, 670000)), ('GE.FLT1..HHZ', datetime.datetime(2011, 9, 3, 16, 38, 8, 40000), datetime.datetime(2011, 9, 3, 16, 42, 9, 670000))], array([ 0.47900702,  0.46478282,  0.44947399]))
```



Same as above, with custom traces id (their SEED identifier only):
<!-- THE CODE SNIPPET BELOW IS AUTOGENERATED WHEN RUNNING TESTS. SEE tests/test_and_create_readme_snippet.py -->
```python
>>> from sdaas.core import traces_idscores
>>> traces_idscores(stream, inventory, idfunc=lambda t: t.get_id())
(['GE.FLT1..HHE', 'GE.FLT1..HHN', 'GE.FLT1..HHZ'], array([ 0.47900702,  0.46478282,  0.44947399]))
```



You can also compute scores and ids from iterables of streams (e.g., when reading from files)...
<!-- THE CODE SNIPPET BELOW IS AUTOGENERATED WHEN RUNNING TESTS. SEE tests/test_and_create_readme_snippet.py -->
```python
from sdaas.core import streams_scores
from sdaas.core import streams_idscores
```



... or from a single trace:
<!-- THE CODE SNIPPET BELOW IS AUTOGENERATED WHEN RUNNING TESTS. SEE tests/test_and_create_readme_snippet.py -->
```python
from sdaas.core import trace_score
```



For instance, to compute the anomaly score of several streams
(for each stream and for each trace therein, return the trace anomaly score):
<!-- THE CODE SNIPPET BELOW IS AUTOGENERATED WHEN RUNNING TESTS. SEE tests/test_and_create_readme_snippet.py -->
```python
>>> from sdaas.core import streams_scores
>>> streams_scores(streams, inventory)
array([ 0.47900702,  0.46478282,  0.44947399,  0.47900702,  0.46478282,
        0.44947399,  0.47900702,  0.46478282,  0.44947399,  0.47900702,
        0.46478282,  0.44947399,  0.47900702,  0.46478282,  0.44947399])
```



Same as above, computing the features and the scores separately for more control:
<!-- THE CODE SNIPPET BELOW IS AUTOGENERATED WHEN RUNNING TESTS. SEE tests/test_and_create_readme_snippet.py -->
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
of N feature vectors (Nx1 numpy array).
Note that for better performances, `aa_scores` should be called once on all feature vectors and not inside a for loop (see example above)
