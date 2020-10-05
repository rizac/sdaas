This is the folder where the scikit models are stored as files
*WARNING: git add and commit only used models, as they might be heavy in size!*

Models are usually those created with the 'sod' Python package.
To copy here a trained model from 'sod', `cd` in the the root directory of
this project and then (`$PATH` below is usually `..`):

```bash
cp $PATH/sod/sod/evaluations/results/clf\=IsolationForest\&tr_set\=uniform_train.hdf\&feats\=psd\@5sec\&behaviour\=new\&contamination\=auto\&max_samples\=2048\&n_estimators\=50\&random_state\=11.sklmodel ./sdaas/core/models/
```

As reference, here some evaluation results obtained in 'sod':
(clf=classifier, feats=features, t=n_estimators, psi=max_samples,
r=random_state, aps= average_precision_score):

```
clf				feats		t	psi		r	aps			best_th_pr_curve	roc_auc_score	log_loss	relative_filepath
IsolationForest	psd@5sec	100	1024	11	0.970564	0.739007	0.975348	0.577372	clf=IsolationForest&tr_set=uniform_train.hdf&feats=psd@5sec&behaviour=new&contamination=auto&max_samples=1024&n_estimators=100&random_state=11/uniform_test.hdf
IsolationForest	psd@5sec	100	 512	11	0.970490	0.743559	0.975866	0.604658	clf=IsolationForest&tr_set=uniform_train.hdf&feats=psd@5sec&behaviour=new&contamination=auto&max_samples=512&n_estimators=100&random_state=11/uniform_test.hdf
IsolationForest	psd@5sec	 50	2048	11	0.970213	0.737760	0.975100	0.559445	clf=IsolationForest&tr_set=uniform_train.hdf&feats=psd@5sec&behaviour=new&contamination=auto&max_samples=2048&n_estimators=50&random_state=11/uniform_test.hdf
IsolationForest	psd@5sec	100	2048	11	0.970131	0.723908	0.974888	0.559709	clf=IsolationForest&tr_set=uniform_train.hdf&feats=psd@5sec&behaviour=new&contamination=auto&max_samples=2048&n_estimators=100&random_state=11/uniform_test.hdf
IsolationForest	psd@5sec	 50	1024	25	0.969853	0.739561	0.975201	0.574039	clf=IsolationForest&tr_set=uniform_train.hdf&feats=psd@5sec&behaviour=new&contamination=auto&max_samples=1024&n_estimators=50&random_state=25/uniform_test.hdf
IsolationForest	psd@5sec	100	4096	25	0.969622	0.680671	0.974166	0.556366	clf=IsolationForest&tr_set=uniform_train.hdf&feats=psd@5sec&behaviour=new&contamination=auto&max_samples=4096&n_estimators=100&random_state=25/uniform_test.hdf
IsolationForest	psd@5sec	 50	 512	11	0.968845	0.745870	0.975527	0.605512	clf=IsolationForest&tr_set=uniform_train.hdf&feats=psd@5sec&behaviour=new&contamination=auto&max_samples=512&n_estimators=50&random_state=11/uniform_test.hdf
IsolationForest	psd@5sec	 50	4096	11	0.968842	0.668166	0.973910	0.556683	clf=IsolationForest&tr_set=uniform_train.hdf&feats=psd@5sec&behaviour=new&contamination=auto&max_samples=4096&n_estimators=50&random_state=11/uniform_test.hdf
```