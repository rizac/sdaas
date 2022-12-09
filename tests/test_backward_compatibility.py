import unittest
from os.path import dirname, join, isfile, abspath, relpath, normpath
from unittest import mock
from unittest.mock import patch

import numpy as np, csv


from sdaas.core import aa_scores
from sdaas.core.model import load_default_trained_model


@unittest.skip("dropped sklearn dependency")
class Test(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    @patch('sdaas.core.model._get_sklearn_version_tuple')
    def test_load_model(self, mock_sklearn_version):
        from sdaas.core.model import get_model_file_path
        previos_model_path = None
        for skverison in [(0, 21, 3),
                          (0, 22),
                          (0, 22, 1),
                          (0, 23, 1),
                          (0, 24, 1),
                          (0, 24, 2)]:
            mock_sklearn_version.return_value = skverison
            fle = get_model_file_path()
            self.assertTrue(isfile(fle))
            if skverison in ((0, 22), (0, 24, 2)):
                self.assertNotEqual(abspath(normpath(fle)),
                                    abspath(normpath(previos_model_path)))
            previos_model_path = fle

    def test_model_v22_is_ok(self):
        """tests new model computes scores as the old one"""
        fle = join(dirname(__file__), '..', 'sdaas', 'core', 'models', 'sklearn<0.22.0',
                   'clf=IsolationForest&tr_set=uniform_train.hdf&feats=psd@5sec&behaviour=new&contamination=auto&max_samples=4096&n_estimators=50&random_state=11.scores.csv')
        psd5, old_scores = [], []
        with open(abspath(fle), 'r') as fp:
            dr = csv.DictReader(fp)
            for row in dr:
                psd5.append(row['psd@5sec'])
                old_scores.append(row['amplitude_anomaly_score'])
        psd5 = np.array(psd5, dtype = float)
        old_scores = np.array(old_scores, dtype=float)

        # old_scores = [_.strip() for _ in fp]
        # old_scores = np.array(old_scores, dtype=float)
        model = load_default_trained_model()
        # psd5 = np.arange(-255, 0, 0.1)
        scores = aa_scores(psd5, model)
        assert len(scores) == len(old_scores)
        scores = scores[:len(scores)]
        old_scores = old_scores[:len(scores)]

        import matplotlib.pyplot as plt, scipy

        # To plot old scores, see models.README.md (rougsnippet below is commented)
        #######################################

        self.assertTrue(np.allclose(scores, old_scores, atol=0.04, rtol=0, equal_nan=True))


if __name__ == "__main__":
    #  import sys;sys.argv = ['', 'Test.testName']
    unittest.main()