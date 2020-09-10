# To copy a trained model from the repository 'sod' (or whatever it is called
# the repository evaluating the models), assuming sod is under $PATH,
# type this command from within the ROOT directoy of this project:

cp $PATH/sod/sod/evaluations/results/clf\=IsolationForest\&tr_set\=uniform_train.hdf\&feats\=psd\@5sec\&behaviour\=new\&contamination\=auto\&max_samples\=2048\&n_estimators\=50\&random_state\=11.sklmodel ./sdaas/models/