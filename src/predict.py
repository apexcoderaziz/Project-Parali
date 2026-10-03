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
    transforms.Resize(
        (IMAGE_SIZE, IMAGE_SIZE)
    ),

    transforms.ToTensor(),

    transforms.Normalize(
        mean=[
            0.485,
            0.456,
            0.406
        ],
        std=[
            0.229,
            0.224,
            0.225
        ]
    )
])


# =========================================================
# RESNET BACKBONE
# Same architecture used during training
# =========================================================

def create_backbone():

    # The trained checkpoint already contains the ResNet18 parameters.
    # Do not download ImageNet weights at Render runtime; that would add
    # an unnecessary network dependency and slow first-request model loading.
    model = models.resnet18(
        weights=None
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

    print(
        "\nLoading Project Parali model..."
    )

    print(
        f"Device: {DEVICE}"
    )

    print(
        f"Model path: {MODEL_PATH}"
    )


    # -----------------------------------------------------
    # Check model
    # -----------------------------------------------------

    if not os.path.exists(
        MODEL_PATH
    ):

        print(
            "\nERROR: Model not found:"
        )

        print(
            MODEL_PATH
        )

        sys.exit(1)


    # -----------------------------------------------------
    # Create RGB backbone
    # -----------------------------------------------------

    print(
        "\nCreating RGB backbone..."
    )

    rgb_model, feature_size = (
        create_backbone()
    )


    # -----------------------------------------------------
    # Create SWIR backbone
    # -----------------------------------------------------

    print(
        "Creating SWIR backbone..."
    )

    swir_model, _ = (
        create_backbone()
    )


    # -----------------------------------------------------
    # Create dual model
    # -----------------------------------------------------

    model = DualResNet(
        rgb_model,
        swir_model,
        feature_size
    )


    # -----------------------------------------------------
    # Load trained weights
    # -----------------------------------------------------

    print(
        "\nLoading trained weights..."
    )

    checkpoint = torch.load(
        MODEL_PATH,
        map_location=DEVICE
    )


    print(
        "Checkpoint loaded."
    )


    # -----------------------------------------------------
    # Inspect checkpoint
    # -----------------------------------------------------

    if isinstance(
        checkpoint,
        dict
    ):

        print(
            f"Checkpoint entries: "
            f"{len(checkpoint)}"
        )


    model.load_state_dict(
        checkpoint
    )


    # -----------------------------------------------------
    # Move model to device
    # -----------------------------------------------------

    model = model.to(
        DEVICE
    )

    model.eval()


    print(
        "Model loaded successfully!"
    )


    return model


# =========================================================
# IMAGE STATISTICS
# =========================================================

def print_image_statistics(
    name,
    image_tensor
):

    tensor = (
        image_tensor
        .detach()
        .cpu()
    )


    mean = (
        tensor.mean()
        .item()
    )


    std = (
        tensor.std()
        .item()
    )


    minimum = (
        tensor.min()
        .item()
    )


    maximum = (
        tensor.max()
        .item()
    )


    print(
        f"\n{name} tensor statistics:"
    )

    print(
        f"  Mean : {mean:.6f}"
    )

    print(
        f"  Std  : {std:.6f}"
    )

    print(
        f"  Min  : {minimum:.6f}"
    )

    print(
        f"  Max  : {maximum:.6f}"
    )


# =========================================================
# RAW IMAGE STATISTICS
# =========================================================

def print_raw_image_statistics(
    name,
    image
):

    array = np.asarray(
        image
    ).astype(
        np.float32
    )


    print(
        f"\n{name} original image:"
    )

    print(
        f"  Size   : {image.size}"
    )

    print(
        f"  Shape  : {array.shape}"
    )

    print(
        f"  Mean   : {array.mean():.4f}"
    )

    print(
        f"  Std    : {array.std():.4f}"
    )

    print(
        f"  Min    : {array.min():.4f}"
    )

    print(
        f"  Max    : {array.max():.4f}"
    )


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

    if not os.path.exists(
        rgb_path
    ):

        raise FileNotFoundError(
            f"RGB image not found: "
            f"{rgb_path}"
        )


    if not os.path.exists(
        swir_path
    ):

        raise FileNotFoundError(
            f"SWIR image not found: "
            f"{swir_path}"
        )


    # -----------------------------------------------------
    # Display input paths
    # -----------------------------------------------------

    print(
        "\n===================================="
    )

    print(
        "INPUT IMAGES"
    )

    print(
        "===================================="
    )

    print(
        f"RGB : {rgb_path}"
    )

    print(
        f"SWIR: {swir_path}"
    )


    # -----------------------------------------------------
    # Load RGB
    # -----------------------------------------------------

    rgb_image = Image.open(
        rgb_path
    ).convert(
        "RGB"
    )


    # -----------------------------------------------------
    # Load SWIR
    # -----------------------------------------------------

    swir_image = Image.open(
        swir_path
    ).convert(
        "RGB"
    )


    # -----------------------------------------------------
    # Print original image statistics
    # -----------------------------------------------------

    print_raw_image_statistics(
        "RGB",
        rgb_image
    )


    print_raw_image_statistics(
        "SWIR",
        swir_image
    )


    # -----------------------------------------------------
    # Apply preprocessing
    # -----------------------------------------------------

    rgb = transform(
        rgb_image
    )


    swir = transform(
        swir_image
    )


    # -----------------------------------------------------
    # Print transformed statistics
    # -----------------------------------------------------

    print_image_statistics(
        "RGB",
        rgb
    )


    print_image_statistics(
        "SWIR",
        swir
    )


    # -----------------------------------------------------
    # Add batch dimension
    # -----------------------------------------------------

    rgb = rgb.unsqueeze(
        0
    )


    swir = swir.unsqueeze(
        0
    )


    # -----------------------------------------------------
    # Move to device
    # -----------------------------------------------------

    rgb = rgb.to(
        DEVICE
    )


    swir = swir.to(
        DEVICE
    )


    # =====================================================
    # MODEL PREDICTION
    # =====================================================

    with torch.no_grad():

        # -------------------------------------------------
        # Raw logits
        # -------------------------------------------------

        outputs = model(
            rgb,
            swir
        )


        # -------------------------------------------------
        # Softmax probabilities
        # -------------------------------------------------

        probabilities = (
            torch.softmax(
                outputs,
                dim=1
            )
        )


        # -------------------------------------------------
        # Prediction
        # -------------------------------------------------

        prediction = (
            torch.argmax(
                probabilities,
                dim=1
            ).item()
        )


    # =====================================================
    # DEBUG OUTPUT
    # =====================================================

    raw_logits = (
        outputs[0]
        .detach()
        .cpu()
        .numpy()
    )


    probs = (
        probabilities[0]
        .detach()
        .cpu()
        .numpy()
    )


    print(
        "\n===================================="
    )

    print(
        "MODEL DEBUG"
    )

    print(
        "===================================="
    )


    print(
        "\nRaw model logits:"
    )


    print(
        f"  No Burn: "
        f"{raw_logits[0]:.6f}"
    )


    print(
        f"  Burn   : "
        f"{raw_logits[1]:.6f}"
    )


    print(
        "\nSoftmax probabilities:"
    )


    print(
        f"  No Burn: "
        f"{probs[0] * 100:.6f}%"
    )


    print(
        f"  Burn   : "
        f"{probs[1] * 100:.6f}%"
    )


    print(
        "\nLogit difference:"
    )


    print(
        f"  Burn - No Burn: "
        f"{raw_logits[1] - raw_logits[0]:.6f}"
    )


    # =====================================================
    # RESULTS
    # =====================================================

    predicted_class = (
        CLASS_NAMES[
            prediction
        ]
    )


    confidence = (
        probabilities[
            0,
            prediction
        ].item()
        * 100
    )


    no_burn_probability = (
        probabilities[
            0,
            0
        ].item()
        * 100
    )


    burn_probability = (
        probabilities[
            0,
            1
        ].item()
        * 100
    )


    return {

        "prediction":
            predicted_class,

        "confidence":
            confidence,

        "no_burn_probability":
            no_burn_probability,

        "burn_probability":
            burn_probability,

        "raw_logits":
            {
                "no_burn":
                    float(
                        raw_logits[0]
                    ),

                "burn":
                    float(
                        raw_logits[1]
                    )
            }
    }


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    print(
        "\n===================================="
    )

    print(
        "PROJECT PARALI"
    )

    print(
        "BURN PREDICTION"
    )

    print(
        "===================================="
    )


    # -----------------------------------------------------
    # Load model
    # -----------------------------------------------------

    model = load_model()


    # -----------------------------------------------------
    # Get image paths
    # -----------------------------------------------------

    if len(sys.argv) != 3:

        print(
            "\nUsage:"
        )

        print(
            "python src/predict.py "
            "<rgb_image> <swir_image>"
        )


        print(
            "\nExample:"
        )

        print(
            "python src/predict.py "
            "data/rgb.jpg "
            "data/swir.jpg"
        )


        sys.exit(1)


    rgb_path = (
        sys.argv[1]
    )

    swir_path = (
        sys.argv[2]
    )


    # -----------------------------------------------------
    # Predict
    # -----------------------------------------------------

    result = predict(
        model,
        rgb_path,
        swir_path
    )


    # -----------------------------------------------------
    # Display final result
    # -----------------------------------------------------

    print(
        "\n===================================="
    )

    print(
        "PREDICTION RESULT"
    )

    print(
        "===================================="
    )


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


    print(
        "\nRaw logits:"
    )


    print(
        f"No Burn    : "
        f"{result['raw_logits']['no_burn']:.6f}"
    )


    print(
        f"Burn       : "
        f"{result['raw_logits']['burn']:.6f}"
    )


    print(
        "\n===================================="
    )