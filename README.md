# sdaas

(**s**)eismic (**d**)ata (and metadata) (**a**)mplitude (**a**)nomaly (**s**)core

Simple program / library to compute amplitude anomaly scores in seismic data and metadata.
Given a set of waveforms and their metadata, it removes the waveform response and returns the relative anomaly score computed on the waveform amplitudes.
This program can be used to filter out a set of  malformed waveforms, or to check the correctness of the metadata fields (e.g. Station inventory xml) by checking the anomaly score on a set of station recordings
