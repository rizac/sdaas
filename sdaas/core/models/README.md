# Sdaas models

This is the folder where the scikit models (IsolationForest) are stored as files.
**WARNING**: git add and commit only used models, as they might be heavy in size!

## Backward incompatibility

It might happen that [saved models](https://scikit-learn.org/stable/modules/model_persistence.html) 
**are backward incompatible**.

You should regularly install the latest version of `sklearn` and then run tests to see if 
everything is ok. If not, create a new model (see below) and move the current 
outdated one into its folder with the version compatibility, e.g. `sklearn<=0.22.1`

### Changelog

- `sklearn=0.22`: Refactored private modules, backward incompatible: dumped models with v<0.22 can not be loaded: https://scikit-learn.org/stable/whats_new/v0.22.html#clear-definition-of-the-public-api |
- `sklearn=0.24.2`: Changed `ExtraTreeRegressor`, dumped models are loaded but with `UserWarning: Trying to unpickle estimator ExtraTreeRegressor from version 0.24.1 when using version 0.24.2. This might lead to breaking code or invalid results. Use at your own risk.`

## Create models

<details>

<summary> Using `sod` package (outdated)</summary>

Models are usually those created with the 'sod' or 'sdaas_eval' Python package
and copied here:

```bash
cp $PATH/sod/sod/evaluations/results/clf\=IsolationForest\&tr_set\=uniform_train.hdf\&feats\=psd\@5sec\&behaviour\=new\&contamination\=auto\&max_samples\=2048\&n_estimators\=50\&random_state\=11.sklmodel ./sdaas/core/models/
```

(this is still valid but as of 2021 not the recommended way, it's extremely
overcomplicated and there is a new package, `sdaas-eval` currently in construction)

</details>

You can execute this snippet of code to create and fit your IsolationForest
from a training set (but you need `pandas` additionally installed):

```python
import sklearn
import pandas as pd
from joblib import dump

# print(sklearn.__version__)  # e.g., '0.24.2'

# path of training set (pandas DataFrame: one row per sample, one column per feature):
TRSET_PATH = '.../sdaas_eval/sdaas_eval/_datasets/uniform_train.hdf'
# Path of trained classifier (serialized sklearn object)
CLF_PATH = '.../core/models/clf=IsolationForest&tr_set=uniform_train.hdf&feats=psd@5sec&contamination=auto&max_samples=4096&n_estimators=50&random_state=11.sklmodel'

# Load dataframe (The classifier requires only 1 feature and no label column, so load
# only 1 column 'psd@5sec'):
dataset = pd.read_hdf(TRSET_PATH, columns=['psd@5sec'])
# Remove NaNs (IsolationForest does not support them):
dataset = dataset[~pd.isna(dataset['psd@5sec'])]
# create classifier with parameters (classifier is IsolationForest here):
clf = sklearn.ensemble.IsolationForest(max_samples=4096, n_estimators=50, random_state=11)
# fit dataset:
clf.fit(dataset.values)
# serialize classifier (save to file). To load back, use joblib.load(file)
dump(clf, CLF_PATH)
```

### Add score file

When you add a new model, it is good practice to also create a CSV file with scores 
sampled at specific features point, in order to test that any new model is consistent with
previous ones (in principle, one could also use the score file as model file, using e.g. 
linear interpolation or grid search, but it is unfeasible with a lot of features).

For instance, this snippet has been used to create the CSV files sampling scores
at regular `psd@5sec` intervals (every 0.1 seconds in the range [-250, 0]).
To execute it, copy paste it in your code after changing `MODEL_PATH`:

```python
MODEL_PATH = 'path/to/mymodel.sklmodel'

import os
from joblib import load
from sdaas.core.model import aa_scores
import numpy as np

psds = np.arange(-250, 0.1, 0.1)
ifr = load(MODEL_PATH)
scores = aa_scores(psds, ifr)
outname = os.path.splitext(MODEL_PATH)[0] + '.scores.csv'
with open(outname,  'w') as fp:
    fp.write('psd@5sec,amplitude_anomaly_score\n')
    for psd, score in zip(psds, scores):
        fp.write('%s,%s\n' % (str(psd), str(score)))
```

If you want to visualize the currently loaded models in a plot,
execute this script after changing `REPO_PATH`:

```python
REPO_PATH = 'here the full absolute path of your sdaas repository (no ending slash)'

pths = {
    '1024.<0.22': REPO_PATH + '/sdaas/core/models/sklearn<0.22/clf=IsolationForest&tr_set=uniform_train.hdf&feats=psd@5sec&behaviour=new&contamination=auto&max_samples=1024&n_estimators=100&random_state=11.scores.csv',
    '4096.<0.22': REPO_PATH + '/sdaas/core/models/sklearn<0.22/clf=IsolationForest&tr_set=uniform_train.hdf&feats=psd@5sec&behaviour=new&contamination=auto&max_samples=4096&n_estimators=50&random_state=11.scores.csv',
    '4096.<0.24.1': REPO_PATH + '/sdaas/core/models/sklearn<=0.24.1/clf=IsolationForest&tr_set=uniform_train.hdf&feats=psd@5sec&contamination=auto&max_samples=4096&n_estimators=50&random_state=11.scores.csv',
    '4096': REPO_PATH + '/sdaas/core/models/clf=IsolationForest&tr_set=uniform_train.hdf&feats=psd@5sec&contamination=auto&max_samples=4096&n_estimators=50&random_state=11.scores.csv',
}

# note that last and next-to-last models are the same and their plot will overlap

import matplotlib.pyplot as plt
import csv

psds = []
for i, (label, pth) in enumerate(pths.items()):
    array = []
    with open(pth, newline='') as fp:
        csv_  = csv.DictReader(fp)
        for data in csv_:
            array.append(float(data['amplitude_anomaly_score']))
            if i == 0:
                psds.append(float(data['psd@5sec']))
    plt.plot(psds, array, label=label)

plt.legend()
plt.show()
```

## Evaluation results

As reference [(Zaccarelli et al, 2021)](https://pubs.geoscienceworld.org/ssa/srl/article/doi/10.1785/0220200339/596662/Anomaly-Detection-in-Seismic-Data-Metadata-Using),
 here some evaluation results obtained in 'sod':
(clf=classifier, feats=features, t=n_estimators, psi=max_samples,
r=random_state, aps=average_precision_score, best_th_pr=best threshold maximizing
Precision/Recall curve, auc=Area under ROC curve):

```
clf             feats	        t	 psi	 r	     aps	best_th_pr	     auc	log_loss	relative_filepath
IsolationForest	psd@5sec	100	1024	11	0.970564	0.739007	0.975348	0.577372	clf=IsolationForest&tr_set=uniform_train.hdf&feats=psd@5sec&behaviour=new&contamination=auto&max_samples=1024&n_estimators=100&random_state=11/uniform_test.hdf
IsolationForest	psd@5sec	100	 512	11	0.970490	0.743559	0.975866	0.604658	clf=IsolationForest&tr_set=uniform_train.hdf&feats=psd@5sec&behaviour=new&contamination=auto&max_samples=512&n_estimators=100&random_state=11/uniform_test.hdf
IsolationForest	psd@5sec	 50	2048	11	0.970213	0.737760	0.975100	0.559445	clf=IsolationForest&tr_set=uniform_train.hdf&feats=psd@5sec&behaviour=new&contamination=auto&max_samples=2048&n_estimators=50&random_state=11/uniform_test.hdf
IsolationForest	psd@5sec	100	2048	11	0.970131	0.723908	0.974888	0.559709	clf=IsolationForest&tr_set=uniform_train.hdf&feats=psd@5sec&behaviour=new&contamination=auto&max_samples=2048&n_estimators=100&random_state=11/uniform_test.hdf
IsolationForest	psd@5sec	 50	1024	25	0.969853	0.739561	0.975201	0.574039	clf=IsolationForest&tr_set=uniform_train.hdf&feats=psd@5sec&behaviour=new&contamination=auto&max_samples=1024&n_estimators=50&random_state=25/uniform_test.hdf
IsolationForest	psd@5sec	100	4096	25	0.969622	0.680671	0.974166	0.556366	clf=IsolationForest&tr_set=uniform_train.hdf&feats=psd@5sec&behaviour=new&contamination=auto&max_samples=4096&n_estimators=100&random_state=25/uniform_test.hdf
IsolationForest	psd@5sec	 50	 512	11	0.968845	0.745870	0.975527	0.605512	clf=IsolationForest&tr_set=uniform_train.hdf&feats=psd@5sec&behaviour=new&contamination=auto&max_samples=512&n_estimators=50&random_state=11/uniform_test.hdf
IsolationForest	psd@5sec	 50	4096	11	0.968842	0.668166	0.973910	0.556683	clf=IsolationForest&tr_set=uniform_train.hdf&feats=psd@5sec&behaviour=new&contamination=auto&max_samples=4096&n_estimators=50&random_state=11/uniform_test.hdf
```
