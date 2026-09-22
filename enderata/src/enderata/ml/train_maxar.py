"""Run this manually to train the Maxar per-building segmentation
model on real data. NOT part of the add-on CLI (cli.py) -- a local
research script, not something the shipped add-on runs (torch isn't
even in its Docker requirements.txt, see requirements-ml.txt).

Usage: PYTHONPATH=src python -m enderata.ml.train_maxar
"""

from __future__ import annotations

import os

from torch.utils.data import DataLoader

from enderata.aoi import load_luanda_aoi
from enderata.ml.maxar_dataset import build_patch_dataset, load_patch_dataset, save_patch_dataset
from enderata.ml.model import UNet
from enderata.ml.train import MaxarPatchDataset, spatial_train_val_split, train_model

DATASET_PATH = "ml_data/luanda_maxar_patches_train"
CHECKPOINT_PATH = "ml_checkpoints/maxar_unet.pt"


def main(max_patches: int = 500, epochs: int = 25, batch_size: int = 4) -> None:
    if os.path.exists(f"{DATASET_PATH}.npz"):
        patches = load_patch_dataset(DATASET_PATH)
        print(f"[train_maxar] loaded {len(patches)} cached patches from {DATASET_PATH}.npz")
    else:
        aoi = load_luanda_aoi()
        patches = build_patch_dataset(aoi, patch_size_px=512, max_patches=max_patches)
        os.makedirs("ml_data", exist_ok=True)
        save_patch_dataset(patches, DATASET_PATH)
        print(f"[train_maxar] built and saved {len(patches)} patches to {DATASET_PATH}.npz")

    train_patches, val_patches = spatial_train_val_split(
        patches, sort_key=lambda p: p.bounds_proj[0], val_fraction=0.15
    )
    print(f"[train_maxar] train={len(train_patches)} val={len(val_patches)}")

    train_dataset = MaxarPatchDataset(train_patches)
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(MaxarPatchDataset(val_patches), batch_size=batch_size, shuffle=False)

    # Focal loss, not pos_weight -- see train_sentinel.py's comment and
    # model.py's focal_loss docstring for why (verified on real runs).
    model = UNet(in_channels=3, out_channels=1, base_channels=32)
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
    print(f"[train_maxar] DONE best_val_iou={history.best_val_iou:.4f}")


if __name__ == "__main__":
    main()
