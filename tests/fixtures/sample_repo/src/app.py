import pandas as pd


def transform_rows(frame: pd.DataFrame) -> pd.DataFrame:
    # TODO: replace with a vectorized implementation
    updated = frame.append({"name": "new-row"}, ignore_index=True)
    return updated


def very_long_function(value):
    temp = value
    for i in range(12):
        if i % 2 == 0:
            temp += i
        else:
            temp -= i
    return temp
