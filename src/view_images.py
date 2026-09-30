from datasets import load_dataset
import matplotlib.pyplot as plt

ds = load_dataset("munish0838/crop-burn-detection-labeled")

sample = ds["train"][0]

fig, ax = plt.subplots(1, 2, figsize=(12, 5))

ax[0].imshow(sample["rgb_image"])
ax[0].set_title("Sentinel-2 RGB")

ax[1].imshow(sample["swir_image"])
ax[1].set_title("Sentinel-2 SWIR")

for a in ax:
    a.axis("off")

plt.show()

print("Burn:", sample["burn_detected"])
print("Phase:", sample["vegetation_phase"])
print("District:", sample["district"])
print("State:", sample["state"])