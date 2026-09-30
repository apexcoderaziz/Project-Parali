import os
import numpy as np
import torch
import torch.nn as nn

from torch.utils.data import Dataset, DataLoader
from torchvision import models, transforms
from datasets import load_dataset
from PIL import Image

from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report
)


# =========================================================
# CONFIG
# =========================================================

BATCH_SIZE = 16
EPOCHS = 12
LEARNING_RATE = 1e-4
IMAGE_SIZE = 224

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

print("Device:", DEVICE)


# =========================================================
# LOAD DATASET
# =========================================================

print("\nLoading dataset...")

ds = load_dataset(
    "munish0838/crop-burn-detection-labeled"
)

train_data = ds["train"]
test_data = ds["test"]

print("Training samples:", len(train_data))
print("Test samples:", len(test_data))


# =========================================================
# TRAIN / VALIDATION SPLIT
# =========================================================

labels = [
    int(train_data[i]["burn_detected"])
    for i in range(len(train_data))
]

indices = np.arange(len(train_data))

train_indices, val_indices = train_test_split(
    indices,
    test_size=0.15,
    random_state=42,
    stratify=labels
)

print("Training:", len(train_indices))
print("Validation:", len(val_indices))
print("Test:", len(test_data))


# =========================================================
# TRANSFORMS
# =========================================================

train_transform = transforms.Compose([

    transforms.Resize(
        (IMAGE_SIZE, IMAGE_SIZE)
    ),

    transforms.RandomHorizontalFlip(),

    transforms.RandomVerticalFlip(),

    transforms.RandomRotation(15),

    transforms.ColorJitter(
        brightness=0.15,
        contrast=0.15
    ),

    transforms.ToTensor(),

    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    )
])


test_transform = transforms.Compose([

    transforms.Resize(
        (IMAGE_SIZE, IMAGE_SIZE)
    ),

    transforms.ToTensor(),

    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    )
])


# =========================================================
# DATASET
# =========================================================

class DualSatelliteDataset(Dataset):

    def __init__(
        self,
        dataset,
        indices,
        transform
    ):

        self.dataset = dataset
        self.indices = indices
        self.transform = transform

    def __len__(self):

        return len(self.indices)

    def __getitem__(self, idx):

        real_index = self.indices[idx]

        item = self.dataset[real_index]

        rgb = item["rgb_image"]
        swir = item["swir_image"]

        if not isinstance(rgb, Image.Image):

            rgb = Image.fromarray(
                np.array(rgb)
            )

        if not isinstance(swir, Image.Image):

            swir = Image.fromarray(
                np.array(swir)
            )

        label = int(
            item["burn_detected"]
        )

        rgb = self.transform(rgb)

        swir = self.transform(swir)

        return rgb, swir, label


# =========================================================
# CREATE DATASETS
# =========================================================

train_dataset = DualSatelliteDataset(
    train_data,
    train_indices,
    train_transform
)

val_dataset = DualSatelliteDataset(
    train_data,
    val_indices,
    test_transform
)

test_indices = np.arange(
    len(test_data)
)

test_dataset = DualSatelliteDataset(
    test_data,
    test_indices,
    test_transform
)


# =========================================================
# DATALOADERS
# =========================================================

train_loader = DataLoader(
    train_dataset,
    batch_size=BATCH_SIZE,
    shuffle=True,
    num_workers=0
)

val_loader = DataLoader(
    val_dataset,
    batch_size=BATCH_SIZE,
    shuffle=False,
    num_workers=0
)

test_loader = DataLoader(
    test_dataset,
    batch_size=BATCH_SIZE,
    shuffle=False,
    num_workers=0
)


# =========================================================
# RESNET BACKBONE
# =========================================================

def create_backbone():

    weights = models.ResNet18_Weights.DEFAULT

    model = models.resnet18(
        weights=weights
    )

    feature_size = model.fc.in_features

    model.fc = nn.Identity()

    return model, feature_size


print("\nLoading RGB backbone...")

rgb_model, feature_size = create_backbone()


print("Loading SWIR backbone...")

swir_model, _ = create_backbone()


# =========================================================
# DUAL MODEL
# =========================================================

class DualResNet(nn.Module):

    def __init__(
        self,
        rgb_model,
        swir_model,
        feature_size
    ):

        super().__init__()

        self.rgb_model = rgb_model

        self.swir_model = swir_model

        self.classifier = nn.Sequential(

            nn.Linear(
                feature_size * 2,
                512
            ),

            nn.ReLU(),

            nn.Dropout(0.4),

            nn.Linear(
                512,
                128
            ),

            nn.ReLU(),

            nn.Dropout(0.3),

            nn.Linear(
                128,
                2
            )
        )

    def forward(
        self,
        rgb,
        swir
    ):

        rgb_features = self.rgb_model(
            rgb
        )

        swir_features = self.swir_model(
            swir
        )

        combined = torch.cat(
            [
                rgb_features,
                swir_features
            ],
            dim=1
        )

        output = self.classifier(
            combined
        )

        return output


model = DualResNet(
    rgb_model,
    swir_model,
    feature_size
)

model = model.to(DEVICE)


# =========================================================
# LOSS
# =========================================================

criterion = nn.CrossEntropyLoss()


# =========================================================
# OPTIMIZER
# =========================================================

optimizer = torch.optim.AdamW(
    model.parameters(),
    lr=LEARNING_RATE,
    weight_decay=1e-4
)


# =========================================================
# VALIDATION FUNCTION
# =========================================================

def evaluate(loader):

    model.eval()

    predictions = []

    actual = []

    with torch.no_grad():

        for rgb, swir, labels in loader:

            rgb = rgb.to(DEVICE)

            swir = swir.to(DEVICE)

            outputs = model(
                rgb,
                swir
            )

            predicted = torch.argmax(
                outputs,
                dim=1
            )

            predictions.extend(
                predicted.cpu().numpy()
            )

            actual.extend(
                labels.numpy()
            )

    accuracy = accuracy_score(
        actual,
        predictions
    )

    return accuracy


# =========================================================
# TRAINING
# =========================================================

print("\n================================")
print("STARTING DUAL RGB + SWIR TRAINING")
print("================================\n")


best_val_accuracy = 0.0


for epoch in range(EPOCHS):

    model.train()

    running_loss = 0.0

    correct = 0

    total = 0


    for rgb, swir, labels in train_loader:

        rgb = rgb.to(DEVICE)

        swir = swir.to(DEVICE)

        labels = labels.to(DEVICE)


        optimizer.zero_grad()


        outputs = model(
            rgb,
            swir
        )


        loss = criterion(
            outputs,
            labels
        )


        loss.backward()

        optimizer.step()


        running_loss += loss.item()


        predicted = torch.argmax(
            outputs,
            dim=1
        )


        total += labels.size(0)

        correct += (
            predicted == labels
        ).sum().item()


    train_accuracy = (
        correct / total
    )


    val_accuracy = evaluate(
        val_loader
    )


    print(
        f"Epoch [{epoch + 1}/{EPOCHS}] "
        f"Loss: {running_loss / len(train_loader):.4f} "
        f"Train: {train_accuracy:.4f} "
        f"Val: {val_accuracy:.4f}"
    )


    # Save best validation model

    if val_accuracy > best_val_accuracy:

        best_val_accuracy = val_accuracy

        torch.save(
            model.state_dict(),
            "models/parali_dual_best.pth"
        )

        print(
            "  → Best model saved!"
        )


# =========================================================
# LOAD BEST MODEL
# =========================================================

print("\nLoading best validation model...")

model.load_state_dict(
    torch.load(
        "models/parali_dual_best.pth",
        map_location=DEVICE
    )
)


# =========================================================
# FINAL TEST
# =========================================================

print("\nEvaluating on untouched test set...")


model.eval()

all_predictions = []

all_labels = []


with torch.no_grad():

    for rgb, swir, labels in test_loader:

        rgb = rgb.to(DEVICE)

        swir = swir.to(DEVICE)

        outputs = model(
            rgb,
            swir
        )

        predictions = torch.argmax(
            outputs,
            dim=1
        )


        all_predictions.extend(
            predictions.cpu().numpy()
        )

        all_labels.extend(
            labels.numpy()
        )


# =========================================================
# METRICS
# =========================================================

accuracy = accuracy_score(
    all_labels,
    all_predictions
)

precision = precision_score(
    all_labels,
    all_predictions
)

recall = recall_score(
    all_labels,
    all_predictions
)

f1 = f1_score(
    all_labels,
    all_predictions
)


print("\n")
print("=" * 50)
print("PROJECT PARALI — RGB + SWIR")
print("=" * 50)

print(
    f"Accuracy  : {accuracy:.4f}"
)

print(
    f"Precision : {precision:.4f}"
)

print(
    f"Recall    : {recall:.4f}"
)

print(
    f"F1 Score  : {f1:.4f}"
)


print("\nClassification Report:")

print(
    classification_report(
        all_labels,
        all_predictions,
        target_names=[
            "No Burn",
            "Burn"
        ]
    )
)


print("\nConfusion Matrix:")

print(
    confusion_matrix(
        all_labels,
        all_predictions
    )
)


# =========================================================
# SAVE FINAL MODEL
# =========================================================

os.makedirs(
    "models",
    exist_ok=True
)

torch.save(
    model.state_dict(),
    "models/parali_dual_rgb_swir.pth"
)

print(
    "\nFinal model saved:"
)

print(
    "models/parali_dual_rgb_swir.pth"
)