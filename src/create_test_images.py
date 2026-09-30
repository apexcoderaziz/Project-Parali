from datasets import load_dataset
from PIL import Image

print("Loading dataset...")

ds = load_dataset(
    "munish0838/crop-burn-detection-labeled"
)

# Take the first test sample
sample = ds["test"][0]

rgb = sample["rgb_image"]
swir = sample["swir_image"]

# Make sure they are PIL images
if not isinstance(rgb, Image.Image):
    rgb = Image.fromarray(rgb)

if not isinstance(swir, Image.Image):
    swir = Image.fromarray(swir)

# Save images
rgb.save("data/test_rgb.jpg")
swir.save("data/test_swir.jpg")

print("\nTest images created successfully!")

print("RGB : data/test_rgb.jpg")
print("SWIR:", "data/test_swir.jpg")

print("\nActual label:")
print("Burn detected:", sample["burn_detected"])