"""Run this manually to train the Sentinel-2 per-pixel built-up
classifier on real data. NOT part of the add-on CLI (cli.py) -- a
local research script (see train_maxar.py's docstring for why).

Usage: PYTHONPATH=src python -m enderata.ml.train_sentinel
"""

from __future__ import annotations

import os

from torch.utils.data import DataLoader

from enderata.aoi import load_luanda_aoi
from enderata.ml.dataset import build_training_dataset, load_training_dataset, save_training_dataset
from enderata.ml.model import UNet
from enderata.ml.train import (
    SentinelCropDataset,
    list_sentinel_crops,
    spatial_train_val_split,
    train_model,
)

DATASET_PATH = "ml_data/luanda_train"
CHECKPOINT_PATH = "ml_checkpoints/sentinel_unet.pt"
CROP_SIZE = 128  # 1.28km per crop at 10m/pixel; divisible by 16 (4 UNet poolings)


def main(epochs: int = 40, batch_size: int = 8) -> None:
    if os.path.exists(f"{DATASET_PATH}.npz"):
        dataset = load_training_dataset(DATASET_PATH)
        print(f"[train_sentinel] loaded cached dataset from {DATASET_PATH}.npz")
    else:
        aoi = load_luanda_aoi()
        dataset = build_training_dataset(aoi)
        os.makedirs("ml_data", exist_ok=True)
        save_training_dataset(dataset, DATASET_PATH)
        print(f"[train_sentinel] built and saved dataset to {DATASET_PATH}.npz")

    crops = list_sentinel_crops(dataset, crop_size=CROP_SIZE)
    print(f"[train_sentinel] {len(crops)} crops of {CROP_SIZE}x{CROP_SIZE}px from the full raster")

    train_crops, val_crops = spatial_train_val_split(crops, sort_key=lambda c: c.col0, val_fraction=0.15)
    print(f"[train_sentinel] train={len(train_crops)} val={len(val_crops)}")

    train_dataset = SentinelCropDataset(dataset, train_crops, CROP_SIZE)
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(SentinelCropDataset(dataset, val_crops, CROP_SIZE), batch_size=batch_size, shuffle=False)

    # Focal loss, not pos_weight -- verified on real training runs that
    # a single global pos_weight scalar is too coarse at this imbalance
    # level (~1.3% positive pixels): the raw ratio overcorrected to
    # predicting positive almost everywhere, a sqrt-dampened ratio
    # wasn't enough to escape predicting negative everywhere. See
    # model.py's focal_loss docstring.
    model = UNet(in_channels=5, out_channels=1, base_channels=32)
    os.makedirs("ml_checkpoints", exist_ok=True)
    history = train_model(
        model,
        train_loader,
        val_loader,
        device="cuda",
        epochs=epochs,
        checkpoint_path=CHECKPOINT_PATH,
        use_focal=True,
    )
    print(f"[train_sentinel] DONE best_val_iou={history.best_val_iou:.4f}")


if __name__ == "__main__":
    main()
