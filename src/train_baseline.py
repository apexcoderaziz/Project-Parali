from datasets import load_dataset
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix
)

print("Loading dataset...")

ds = load_dataset("munish0838/crop-burn-detection-labeled")

print("Dataset loaded.")


def extract_features(example):
    rgb = np.array(example["rgb_image"]).astype(np.float32) / 255.0
    swir = np.array(example["swir_image"]).astype(np.float32) / 255.0

    features = []

    # RGB statistics
    for channel in range(3):
        c = rgb[:, :, channel]

        features.extend([
            np.mean(c),
            np.std(c),
            np.min(c),
            np.max(c),
            np.percentile(c, 25),
            np.percentile(c, 50),
            np.percentile(c, 75)
        ])

    # SWIR RGB representation statistics
    for channel in range(3):
        c = swir[:, :, channel]

        features.extend([
            np.mean(c),
            np.std(c),
            np.min(c),
            np.max(c),
            np.percentile(c, 25),
            np.percentile(c, 50),
            np.percentile(c, 75)
        ])

    # Spatial statistics
    features.extend([
        np.mean(rgb),
        np.std(rgb),
        np.mean(swir),
        np.std(swir)
    ])

    return features


print("Extracting training features...")

X_train = np.array([
    extract_features(ds["train"][i])
    for i in range(len(ds["train"]))
])

y_train = np.array([
    int(ds["train"][i]["burn_detected"])
    for i in range(len(ds["train"]))
])


print("Extracting test features...")

X_test = np.array([
    extract_features(ds["test"][i])
    for i in range(len(ds["test"]))
])

y_test = np.array([
    int(ds["test"][i]["burn_detected"])
    for i in range(len(ds["test"]))
])


print("\nFeature shape:")
print("X_train:", X_train.shape)
print("X_test :", X_test.shape)


# -----------------------------
# Train Random Forest
# -----------------------------

print("\nTraining Random Forest...")

model = RandomForestClassifier(
    n_estimators=500,
    max_depth=None,
    min_samples_split=2,
    class_weight="balanced",
    random_state=42,
    n_jobs=-1
)

model.fit(X_train, y_train)


# -----------------------------
# Prediction
# -----------------------------

y_pred = model.predict(X_test)


# -----------------------------
# Evaluation
# -----------------------------

accuracy = accuracy_score(y_test, y_pred)
precision = precision_score(y_test, y_pred)
recall = recall_score(y_test, y_pred)
f1 = f1_score(y_test, y_pred)

print("\n==============================")
print("PROJECT PARALI BASELINE")
print("==============================")

print(f"Accuracy  : {accuracy:.4f}")
print(f"Precision : {precision:.4f}")
print(f"Recall    : {recall:.4f}")
print(f"F1 Score  : {f1:.4f}")

print("\nClassification Report:")
print(classification_report(
    y_test,
    y_pred,
    target_names=["No Burn", "Burn"]
))

print("\nConfusion Matrix:")
print(confusion_matrix(y_test, y_pred))