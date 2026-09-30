import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    ConfusionMatrixDisplay
)

print("=" * 60)
print("PROJECT PARALI - FINAL ML MODEL EVALUATION")
print("=" * 60)


# ============================================================
# 1. RESULTS FROM COMPLETED MODEL EXPERIMENTS
# ============================================================
#
# These are the test-set confusion matrices produced by the
# training scripts.
#
# Binary classification:
# 0 = No Burn
# 1 = Burn
#
# Matrix format:
# [[TN, FP],
#  [FN, TP]]
# ============================================================

models = {
    "Random Forest": np.array([
        [81, 18],
        [17, 151]
    ]),

    "SVM": np.array([
        [80, 19],
        [13, 155]
    ]),

    "CNN": np.array([
        [84, 15],
        [35, 133]
    ]),

    "Dual CNN": np.array([
        [88, 11],
        [11, 157]
    ])
}


# ============================================================
# 2. CALCULATE METRICS
# ============================================================

results = []

for model_name, cm in models.items():

    tn, fp = cm[0]
    fn, tp = cm[1]

    y_true = (
        [0] * (tn + fp) +
        [1] * (fn + tp)
    )

    y_pred = (
        [0] * tn +
        [1] * fp +
        [0] * fn +
        [1] * tp
    )

    accuracy = accuracy_score(y_true, y_pred)

    precision = precision_score(
        y_true,
        y_pred,
        zero_division=0
    )

    recall = recall_score(
        y_true,
        y_pred,
        zero_division=0
    )

    f1 = f1_score(
        y_true,
        y_pred,
        zero_division=0
    )

    results.append({
        "Model": model_name,
        "Accuracy": accuracy,
        "Precision": precision,
        "Recall": recall,
        "F1 Score": f1
    })


# ============================================================
# 3. HARVEST-STAGE MODEL
# ============================================================
#
# Classes:
# 0 = pre_harvest
# 1 = post_harvest
# 2 = harvest_in_progress
#
# This is a separate multiclass model and therefore is not
# directly compared with the binary burn-detection models.
# ============================================================

harvest_cm = np.array([
    [67, 10, 9],
    [18, 62, 0],
    [9, 0, 92]
])

harvest_true = []
harvest_pred = []

for actual_class in range(3):
    for predicted_class in range(3):

        count = harvest_cm[actual_class][predicted_class]

        harvest_true.extend(
            [actual_class] * count
        )

        harvest_pred.extend(
            [predicted_class] * count
        )

harvest_accuracy = accuracy_score(
    harvest_true,
    harvest_pred
)

harvest_precision = precision_score(
    harvest_true,
    harvest_pred,
    average="weighted",
    zero_division=0
)

harvest_recall = recall_score(
    harvest_true,
    harvest_pred,
    average="weighted",
    zero_division=0
)

harvest_f1 = f1_score(
    harvest_true,
    harvest_pred,
    average="weighted",
    zero_division=0
)

harvest_result = {
    "Model": "Harvest Stage RF",
    "Accuracy": harvest_accuracy,
    "Precision": harvest_precision,
    "Recall": harvest_recall,
    "F1 Score": harvest_f1
}


# ============================================================
# 4. CREATE COMPARISON TABLE
# ============================================================

results_df = pd.DataFrame(results)

print("\n")
print("=" * 60)
print("BINARY BURN-DETECTION MODELS")
print("=" * 60)

print(
    results_df.to_string(
        index=False,
        formatters={
            "Accuracy": "{:.4f}".format,
            "Precision": "{:.4f}".format,
            "Recall": "{:.4f}".format,
            "F1 Score": "{:.4f}".format
        }
    )
)


print("\n")
print("=" * 60)
print("HARVEST-STAGE MODEL")
print("=" * 60)

print(
    f"Accuracy  : {harvest_accuracy:.4f}"
)

print(
    f"Precision : {harvest_precision:.4f}"
)

print(
    f"Recall    : {harvest_recall:.4f}"
)

print(
    f"F1 Score  : {harvest_f1:.4f}"
)


# ============================================================
# 5. SAVE RESULTS
# ============================================================

os.makedirs("data/processed", exist_ok=True)

output_file = (
    "data/processed/final_model_comparison.csv"
)

results_df.to_csv(
    output_file,
    index=False
)

print("\nComparison saved to:")
print(output_file)


# ============================================================
# 6. PRINT CLASSIFICATION REPORTS
# ============================================================

print("\n")
print("=" * 60)
print("CLASSIFICATION REPORTS")
print("=" * 60)

for model_name, cm in models.items():

    tn, fp = cm[0]
    fn, tp = cm[1]

    y_true = (
        [0] * (tn + fp) +
        [1] * (fn + tp)
    )

    y_pred = (
        [0] * tn +
        [1] * fp +
        [0] * fn +
        [1] * tp
    )

    print("\n" + "-" * 50)
    print(model_name)
    print("-" * 50)

    print(
        classification_report(
            y_true,
            y_pred,
            target_names=["No Burn", "Burn"],
            zero_division=0
        )
    )


# ============================================================
# 7. CONFUSION MATRIX VISUALIZATIONS
# ============================================================

os.makedirs("data/processed/confusion_matrices", exist_ok=True)

for model_name, cm in models.items():

    display = ConfusionMatrixDisplay(
        confusion_matrix=cm,
        display_labels=["No Burn", "Burn"]
    )

    display.plot()

    plt.title(
        f"{model_name} - Confusion Matrix"
    )

    filename = (
        model_name.lower()
        .replace(" ", "_")
        + "_confusion_matrix.png"
    )

    filepath = os.path.join(
        "data/processed/confusion_matrices",
        filename
    )

    plt.savefig(
        filepath,
        dpi=200,
        bbox_inches="tight"
    )

    plt.close()

    print(
        f"Saved confusion matrix: {filepath}"
    )


# ============================================================
# 8. ACCURACY COMPARISON
# ============================================================

plt.figure(figsize=(9, 6))

plt.bar(
    results_df["Model"],
    results_df["Accuracy"]
)

plt.ylabel("Accuracy")
plt.xlabel("Model")
plt.title(
    "Project Parali - Model Accuracy Comparison"
)

plt.ylim(0, 1)

plt.xticks(rotation=20)

for i, value in enumerate(
    results_df["Accuracy"]
):
    plt.text(
        i,
        value + 0.02,
        f"{value:.2%}",
        ha="center"
    )

plt.tight_layout()

accuracy_plot = (
    "data/processed/model_accuracy_comparison.png"
)

plt.savefig(
    accuracy_plot,
    dpi=200,
    bbox_inches="tight"
)

plt.close()

print(
    f"\nAccuracy comparison saved to: {accuracy_plot}"
)


# ============================================================
# 9. FINAL SUMMARY
# ============================================================

print("\n")
print("=" * 60)
print("FINAL PROJECT PARALI ML SUMMARY")
print("=" * 60)

print(
    "\nBinary burn-detection models:"
)

for _, row in results_df.iterrows():

    print(
        f"{row['Model']:15s} "
        f"Accuracy={row['Accuracy']:.2%} "
        f"F1={row['F1 Score']:.2%}"
    )

print(
    "\nHarvest-stage model:"
)

print(
    f"Harvest Stage RF  "
    f"Accuracy={harvest_accuracy:.2%} "
    f"F1={harvest_f1:.2%}"
)

print("\nFINAL EVALUATION COMPLETE!")

