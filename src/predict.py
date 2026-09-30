import os
import sys
import numpy as np
import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image


# =========================================================
# CONFIG
# =========================================================

IMAGE_SIZE = 224

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

MODEL_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "models",
        "parali_dual_rgb_swir.pth"
    )
)

CLASS_NAMES = [
    "No Burn",
    "Burn"
]


# =========================================================
# TRANSFORM
# =========================================================

transform = transforms.Compose([
    transforms.Resize((IMAGE_SIZE, IMAGE_SIZE)),

    transforms.ToTensor(),

    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    )
])


# =========================================================
# RESNET BACKBONE
# Same architecture used during training
# =========================================================

def create_backbone():

    weights = models.ResNet18_Weights.DEFAULT

    model = models.resnet18(
        weights=weights
    )

    feature_size = model.fc.in_features

    model.fc = nn.Identity()

    return model, feature_size


# =========================================================
# DUAL RESNET MODEL
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


# =========================================================
# LOAD MODEL
# =========================================================

def load_model():

    print("Loading model...")

    print("Device:", DEVICE)

    print("Creating RGB backbone...")

    rgb_model, feature_size = create_backbone()

    print("Creating SWIR backbone...")

    swir_model, _ = create_backbone()

    model = DualResNet(
        rgb_model,
        swir_model,
        feature_size
    )

    if not os.path.exists(MODEL_PATH):

        print(
            f"\nERROR: Model not found:"
            f"\n{MODEL_PATH}"
        )

        sys.exit(1)

    print(
        "\nLoading trained weights..."
    )

    model.load_state_dict(
        torch.load(
            MODEL_PATH,
            map_location=DEVICE
        )
    )

    model = model.to(DEVICE)

    model.eval()

    print("Model loaded successfully!")

    return model


# =========================================================
# PREDICTION
# =========================================================

def predict(
    model,
    rgb_path,
    swir_path
):

    # -----------------------------------------------------
    # Check files
    # -----------------------------------------------------

    if not os.path.exists(rgb_path):

        raise FileNotFoundError(
            f"RGB image not found: {rgb_path}"
        )

    if not os.path.exists(swir_path):

        raise FileNotFoundError(
            f"SWIR image not found: {swir_path}"
        )


    # -----------------------------------------------------
    # Load images
    # -----------------------------------------------------

    rgb = Image.open(
        rgb_path
    ).convert("RGB")

    swir = Image.open(
        swir_path
    ).convert("RGB")


    # -----------------------------------------------------
    # Apply preprocessing
    # -----------------------------------------------------

    rgb = transform(rgb)

    swir = transform(swir)


    # -----------------------------------------------------
    # Add batch dimension
    # -----------------------------------------------------

    rgb = rgb.unsqueeze(0)

    swir = swir.unsqueeze(0)


    # -----------------------------------------------------
    # Move to device
    # -----------------------------------------------------

    rgb = rgb.to(DEVICE)

    swir = swir.to(DEVICE)


    # -----------------------------------------------------
    # Prediction
    # -----------------------------------------------------

    with torch.no_grad():

        outputs = model(
            rgb,
            swir
        )

        probabilities = torch.softmax(
            outputs,
            dim=1
        )

        prediction = torch.argmax(
            probabilities,
            dim=1
        ).item()


    # -----------------------------------------------------
    # Results
    # -----------------------------------------------------

    predicted_class = CLASS_NAMES[
        prediction
    ]

    confidence = probabilities[
        0,
        prediction
    ].item() * 100


    no_burn_probability = probabilities[
        0,
        0
    ].item() * 100

    burn_probability = probabilities[
        0,
        1
    ].item() * 100


    return {
        "prediction": predicted_class,
        "confidence": confidence,
        "no_burn_probability": no_burn_probability,
        "burn_probability": burn_probability
    }


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    print("\n====================================")
    print("PROJECT PARALI — BURN PREDICTION")
    print("====================================\n")


    # -----------------------------------------------------
    # Load model
    # -----------------------------------------------------

    model = load_model()


    # -----------------------------------------------------
    # Get image paths
    # -----------------------------------------------------

    if len(sys.argv) != 3:

        print("\nUsage:")

        print(
            "python src/predict.py "
            "<rgb_image> <swir_image>"
        )

        print("\nExample:")

        print(
            "python src/predict.py "
            "data/rgb.jpg "
            "data/swir.jpg"
        )

        sys.exit(1)


    rgb_path = sys.argv[1]

    swir_path = sys.argv[2]


    # -----------------------------------------------------
    # Predict
    # -----------------------------------------------------

    result = predict(
        model,
        rgb_path,
        swir_path
    )


    # -----------------------------------------------------
    # Display result
    # -----------------------------------------------------

    print("\n====================================")
    print("PREDICTION RESULT")
    print("====================================")

    print(
        f"\nPrediction : "
        f"{result['prediction']}"
    )

    print(
        f"Confidence : "
        f"{result['confidence']:.2f}%"
    )

    print(
        f"No Burn    : "
        f"{result['no_burn_probability']:.2f}%"
    )

    print(
        f"Burn       : "
        f"{result['burn_probability']:.2f}%"
    )

    print("\n====================================")