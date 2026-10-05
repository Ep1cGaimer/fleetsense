import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from fleetsense.common import read_config


class HealthIndex:
    def fit(self, training, sensors):
        self.train_ids = sorted(training.engine.unique())
        self.columns = [f"{sensor}_ewm" for sensor in sensors]
        self.scaler = StandardScaler()
        values = self.scaler.fit_transform(training[self.columns])
        config = read_config()["health_index"]
        self.model = Ridge(alpha=config["alpha"])
        self.model.fit(values, np.minimum(training.rul, config["rul_clip"]) / config["rul_clip"])
        return self

    def predict(self, evaluation):
        if set(evaluation.engine) & set(self.train_ids):
            raise AssertionError("Health-index evaluation engines were fitted")
        return np.clip(self.model.predict(self.scaler.transform(evaluation[self.columns])), 0, 1)
