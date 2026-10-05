import numpy as np
from lightgbm import LGBMClassifier
from sklearn.isotonic import IsotonicRegression

from fleetsense.common import read_config
from fleetsense.features import feature_columns


class Forecast:
    def fit(self, training, calibration):
        self.train_ids = sorted(training.engine.unique())
        self.calibration_ids = sorted(calibration.engine.unique())
        if set(self.train_ids) & set(self.calibration_ids):
            raise AssertionError("Training and calibration engines overlap")
        self.columns = feature_columns(training)
        config = read_config()["forecast"].copy()
        self.horizons = config.pop("horizons")
        self.models, self.calibrators = [], []
        for horizon in self.horizons:
            model = LGBMClassifier(**config)
            model.fit(training[self.columns], (training.rul <= horizon).astype(int))
            probabilities = model.predict_proba(calibration[self.columns])[:, 1]
            calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1)
            calibrator.fit(probabilities, (calibration.rul <= horizon).astype(int))
            self.models.append(model)
            self.calibrators.append(calibrator)
        return self

    def predict(self, evaluation, enforce_disjoint=True):
        if enforce_disjoint and set(evaluation.engine) & (set(self.train_ids) | set(self.calibration_ids)):
            raise AssertionError("Evaluation engines were fitted")
        probabilities = np.column_stack([calibrator.predict(model.predict_proba(evaluation[self.columns])[:, 1])
                                         for model, calibrator in zip(self.models, self.calibrators)])
        return np.maximum.accumulate(probabilities, axis=1)
