import os
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision import models, transforms
from datasets import load_dataset
from PIL import Image

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report
)


# ==========================================
# Configuration
# ==========================================

BATCH_SIZE = 16
EPOCHS = 10
LEARNING_RATE = 1e-4
IMAGE_SIZE = 224

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

print("Device:", DEVICE)


# ==========================================
# Load Dataset
# ==========================================

print("Loading dataset...")

ds = load_dataset(
    "munish0838/crop-burn-detection-labeled"
)

print("Dataset loaded.")


# ==========================================
# Image Transformations
# ==========================================

train_transform = transforms.Compose([
    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),

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
    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),

    transforms.ToTensor(),

    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    )
])


# ==========================================
# Dataset Class
# ==========================================

class BurnDataset(Dataset):

    def __init__(self, dataset, transform=None):

        self.dataset = dataset
        self.transform = transform

    def __len__(self):

        return len(self.dataset)

    def __getitem__(self, index):

        item = self.dataset[index]

        image = item["rgb_image"]

        if not isinstance(image, Image.Image):

            image = Image.fromarray(
                np.array(image)
            )

        label = int(
            item["burn_detected"]
        )

        if self.transform:

            image = self.transform(image)

        return image, label


# ==========================================
# Create Datasets
# ==========================================

train_dataset = BurnDataset(
    ds["train"],
    train_transform
)

test_dataset = BurnDataset(
    ds["test"],
    test_transform
)


train_loader = DataLoader(
    train_dataset,
    batch_size=BATCH_SIZE,
    shuffle=True,
    num_workers=0
)

test_loader = DataLoader(
    test_dataset,
    batch_size=BATCH_SIZE,
    shuffle=False,
    num_workers=0
)


# ==========================================
# Load Pretrained ResNet18
# ==========================================

print("Loading ResNet18...")

weights = models.ResNet18_Weights.DEFAULT

model = models.resnet18(
    weights=weights
)


# Replace final classifier

num_features = model.fc.in_features

model.fc = nn.Linear(
    num_features,
    2
)

model = model.to(DEVICE)


# ==========================================
# Loss + Optimizer
# ==========================================

criterion = nn.CrossEntropyLoss()

optimizer = torch.optim.AdamW(
    model.parameters(),
    lr=LEARNING_RATE,
    weight_decay=1e-4
)


# ==========================================
# Training
# ==========================================

print("\nStarting training...\n")


for epoch in range(EPOCHS):

    model.train()

    running_loss = 0.0

    correct = 0
    total = 0

    for images, labels in train_loader:

        images = images.to(DEVICE)

        labels = labels.to(DEVICE)

        optimizer.zero_grad()

        outputs = model(images)

        loss = criterion(
            outputs,
            labels
        )

        loss.backward()

        optimizer.step()

        running_loss += loss.item()

        _, predicted = torch.max(
            outputs,
            1
        )

        total += labels.size(0)

        correct += (
            predicted == labels
        ).sum().item()


    train_accuracy = (
        correct / total
    )


    print(
        f"Epoch [{epoch + 1}/{EPOCHS}] "
        f"Loss: {running_loss / len(train_loader):.4f} "
        f"Train Accuracy: {train_accuracy:.4f}"
    )


# ==========================================
# Evaluation
# ==========================================

print("\nEvaluating on untouched test set...")

model.eval()

all_predictions = []

all_labels = []


with torch.no_grad():

    for images, labels in test_loader:

        images = images.to(DEVICE)

        outputs = model(images)

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


# ==========================================
# Metrics
# ==========================================

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
print("=" * 40)
print("PROJECT PARALI — RESNET18")
print("=" * 40)

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


# ==========================================
# Save Model
# ==========================================

os.makedirs(
    "models",
    exist_ok=True
)

torch.save(
    model.state_dict(),
    "models/parali_resnet18.pth"
)

print(
    "\nModel saved to:"
    " models/parali_resnet18.pth"
)