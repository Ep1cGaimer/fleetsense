import numpy as np
import pandas as pd

from fleetsense.common import read_config


def sensor_list(training):
    config = read_config()["data"]
    return [name for name in training.columns if name.startswith("s") and name[1:].isdigit()
            and training[name].std() >= config["sensor_std_min"]
            and training[name].nunique() > config["sensor_unique_min"]]


def trailing_slope(values, window, minimum):
    output = np.full(len(values), np.nan)
    for position in range(minimum - 1, len(values)):
        prefix = values[max(0, position - window + 1):position + 1]
        coordinates = np.arange(len(prefix), dtype=float)
        coordinates -= coordinates.mean()
        output[position] = np.dot(coordinates, prefix) / np.dot(coordinates, coordinates)
    return output


def features(frame, sensors):
    config = read_config()["features"]
    parts = []
    for _, group in frame.groupby("engine", sort=False):
        group = group.sort_values("cycle")
        output = group[["engine", "cycle", "rul", "subset"]].copy()
        for sensor in sensors:
            series = group[sensor]
            output[f"{sensor}_last"] = series
            for window in config["windows"]:
                output[f"{sensor}_mean_{window}"] = series.rolling(window, min_periods=1).mean()
            output[f"{sensor}_std_20"] = series.rolling(20, min_periods=2).std()
            output[f"{sensor}_slope_20"] = trailing_slope(series.to_numpy(), 20, config["slope_min"])
            output[f"{sensor}_ewm"] = series.ewm(alpha=config["ewm_alpha"], adjust=False).mean()
        output["age"] = group.cycle
        parts.append(output)
    return pd.concat(parts, ignore_index=True)


def feature_columns(frame):
    return [name for name in frame.columns if name not in {"engine", "cycle", "rul", "subset"}]
