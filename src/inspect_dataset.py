from datasets import load_dataset
from collections import Counter
import pandas as pd

print("Loading dataset...")

ds = load_dataset("munish0838/crop-burn-detection-labeled")

print(ds)

print("\nTrain columns:")
print(ds["train"].column_names)

print("\nDataset sizes:")
print("Train:", len(ds["train"]))
print("Test:", len(ds["test"]))

print("\nBurn distribution:")
print("Train:", Counter(ds["train"]["burn_detected"]))
print("Test:", Counter(ds["test"]["burn_detected"]))

train_df = pd.DataFrame(ds["train"])

print("\nStates:")
print(train_df["state"].value_counts())

print("\nBurn by state:")
print(pd.crosstab(
    train_df["state"],
    train_df["burn_detected"]
))

print("\nBurn by vegetation phase:")
print(pd.crosstab(
    train_df["vegetation_phase"],
    train_df["burn_detected"]
))