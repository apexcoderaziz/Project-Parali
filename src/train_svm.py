from datasets import load_dataset
import numpy as np

from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
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


# --------------------------------------------------
# Feature Extraction
# SAME FEATURES AS RANDOM FOREST BASELINE
# --------------------------------------------------

def extract_features(example):

    rgb = np.array(example["rgb_image"]).astype(np.float32) / 255.0
    swir = np.array(example["swir_image"]).astype(np.float32) / 255.0

    features = []

    # --------------------------------------------------
    # RGB statistics
    # --------------------------------------------------

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


    # --------------------------------------------------
    # SWIR statistics
    # --------------------------------------------------

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


    # --------------------------------------------------
    # Spatial statistics
    # --------------------------------------------------

    features.extend([
        np.mean(rgb),
        np.std(rgb),
        np.mean(swir),
        np.std(swir)
    ])

    return features


# --------------------------------------------------
# Extract Training Features
# --------------------------------------------------

print("Extracting training features...")

X_train = np.array([
    extract_features(ds["train"][i])
    for i in range(len(ds["train"]))
])

y_train = np.array([
    int(ds["train"][i]["burn_detected"])
    for i in range(len(ds["train"]))
])


# --------------------------------------------------
# Extract Test Features
# --------------------------------------------------

print("Extracting test features...")

X_test = np.array([
    extract_features(ds["test"][i])
    for i in range(len(ds["test"]))
])

y_test = np.array([
    int(ds["test"][i]["burn_detected"])
    for i in range(len(ds["test"]))
])


# --------------------------------------------------
# Feature Shape
# --------------------------------------------------

print("\nFeature shape:")
print("X_train:", X_train.shape)
print("X_test :", X_test.shape)


# --------------------------------------------------
# Train SVM
# --------------------------------------------------

print("\nTraining SVM...")

model = Pipeline([

    # SVM works better when features are scaled
    ("scaler", StandardScaler()),

    ("svm", SVC(
        kernel="rbf",
        C=10,
        gamma="scale",
        class_weight="balanced"
    ))
])


model.fit(X_train, y_train)

print("SVM training complete!")


# --------------------------------------------------
# Prediction
# --------------------------------------------------

y_pred = model.predict(X_test)


# --------------------------------------------------
# Evaluation
# --------------------------------------------------

accuracy = accuracy_score(y_test, y_pred)

precision = precision_score(
    y_test,
    y_pred
)

recall = recall_score(
    y_test,
    y_pred
)

f1 = f1_score(
    y_test,
    y_pred
)


# --------------------------------------------------
# Results
# --------------------------------------------------

print("\n==============================")
print("PROJECT PARALI — SVM MODEL")
print("==============================")

print(f"Accuracy  : {accuracy:.4f}")
print(f"Precision : {precision:.4f}")
print(f"Recall    : {recall:.4f}")
print(f"F1 Score  : {f1:.4f}")


# --------------------------------------------------
# Classification Report
# --------------------------------------------------

print("\nClassification Report:")

print(
    classification_report(
        y_test,
        y_pred,
        target_names=[
            "No Burn",
            "Burn"
        ]
    )
)


# --------------------------------------------------
# Confusion Matrix
# --------------------------------------------------

print("\nConfusion Matrix:")

print(
    confusion_matrix(
        y_test,
        y_pred
    )
)


# --------------------------------------------------
# Compare with Random Forest Baseline
# --------------------------------------------------

BASELINE_ACCURACY = 0.87

print("\n==============================")
print("MODEL COMPARISON")
print("==============================")

print(
    f"Random Forest Accuracy : "
    f"{BASELINE_ACCURACY:.4f}"
)

print(
    f"SVM Accuracy           : "
    f"{accuracy:.4f}"
)

print(
    f"\nSVM F1 Score           : "
    f"{f1:.4f}"
)

if accuracy > BASELINE_ACCURACY:

    print(
        "\nSVM improved over the "
        "Random Forest baseline."
    )

elif accuracy < BASELINE_ACCURACY:

    print(
        "\nRandom Forest currently "
        "performs better."
    )

else:

    print(
        "\nBoth models have the "
        "same accuracy."
    )

