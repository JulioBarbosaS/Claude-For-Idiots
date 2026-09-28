# data/ holds the datasets themselves (raw/interim/processed) in the classic
# cookiecutter-data-science layout, but small prototypes commonly keep a
# loader script alongside the data it loads instead of factoring it out to
# src/data/ from day one.
import pandas as pd


def load_raw():
    return pd.read_csv("data/raw/dataset.csv")
