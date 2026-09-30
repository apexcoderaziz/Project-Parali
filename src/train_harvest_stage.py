import numpy as np

from datasets import load_dataset
from PIL import Image

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix
)


# ============================================================
# LOAD DATA
# ============================================================

print("Loading dataset...")

ds = load_dataset(
    "munish0838/crop-burn-detection-labeled"
)

train_data = ds["train"]
test_data = ds["test"]

print("Train:", len(train_data))
print("Test :", len(test_data))


# ============================================================
# FEATURE EXTRACTION
# ============================================================

def extract_features(image):

    image = np.array(image).astype(np.float32)

    # Normalize
    image = image / 255.0

    features = []

    # Per-channel statistics
    for channel in range(image.shape[2]):

        data = image[:, :, channel]

        features.extend([
            np.mean(data),
            np.std(data),
            np.min(data),
            np.max(data),
            np.median(data)
        ])

    # Percentiles
    for channel in range(image.shape[2]):

        data = image[:, :, channel]

        features.extend([
            np.percentile(data, 10),
            np.percentile(data, 25),
            np.percentile(data, 75),
            np.percentile(data, 90)
        ])

    return features


def create_features(dataset):

    X = []
    y = []

    for i in range(len(dataset)):

        item = dataset[i]

        rgb = item["rgb_image"]
        swir = item["swir_image"]

        rgb_features = extract_features(rgb)
        swir_features = extract_features(swir)

        combined = (
            rgb_features +
            swir_features
        )

        X.append(combined)

        phase = item["vegetation_phase"]

        y.append(phase)

    return np.array(X), np.array(y)


# ============================================================
# CREATE FEATURES
# ============================================================

print("\nExtracting RGB + SWIR features...")

X_train, y_train = create_features(
    train_data
)

X_test, y_test = create_features(
    test_data
)

print(
    "Feature shape:",
    X_train.shape
)


# ============================================================
# SHOW CLASSES
# ============================================================

print("\nClasses:")

for cls in np.unique(y_train):

    print(
        cls,
        "→",
        np.sum(y_train == cls)
    )


# ============================================================
# RANDOM FOREST
# ============================================================

print("\nTraining Harvest Stage Model...")

model = RandomForestClassifier(

    n_estimators=500,

    max_depth=None,

    min_samples_split=2,

    min_samples_leaf=1,

    class_weight="balanced",

    random_state=42,

    n_jobs=-1
)


model.fit(
    X_train,
    y_train
)


# ============================================================
# PREDICTION
# ============================================================

print("\nPredicting...")

predictions = model.predict(
    X_test
)


# ============================================================
# METRICS
# ============================================================

accuracy = accuracy_score(
    y_test,
    predictions
)


print("\n")
print("=" * 60)
print("PROJECT PARALI — HARVEST STAGE MODEL")
print("=" * 60)

print(
    f"\nAccuracy: {accuracy:.4f}"
)


print("\nClassification Report:")

print(
    classification_report(
        y_test,
        predictions
    )
)


print("\nConfusion Matrix:")

print(
    confusion_matrix(
        y_test,
        predictions
    )
)


# ============================================================
# SAVE MODEL
# ============================================================

import os
import joblib

os.makedirs(
    "models",
    exist_ok=True
)

joblib.dump(
    model,
    "models/parali_harvest_stage_rf.pkl"
)

print(
    "\nModel saved to:"
)

print(
    "models/parali_harvest_stage_rf.pkl"
)