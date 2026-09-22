"""Generic training loop + PyTorch Dataset wrappers for both real
training pipelines (ml/dataset.py's Sentinel-2 per-pixel classifier,
ml/maxar_dataset.py's Maxar per-building segmentation) -- same UNet
architecture (model.py), same loss/metric/loop, different data.

Train/val split is SPATIAL (sorted by position, last `val_fraction`
held out), not a random shuffle -- random splitting of adjacent tiles/
crops leaks nearby, near-duplicate context between train and val and
overstates validation accuracy. A sorted-then-tail-split still has
some leakage at the single boundary line, but far less than scattering
held-out samples throughout the training area.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset

from enderata.ml.dataset import TrainingDataset
from enderata.ml.maxar_dataset import Patch
from enderata.ml.model import UNet, combined_loss

# Sentinel-2 L2A's official scale factor (surface reflectance x10000) --
# a principled normalization, not an empirically-tuned one. Real band
# values in our saved dataset (0-9028, p99 2262-4806) stay comfortably
# under this, consistent with valid L2A reflectance data.
SENTINEL2_SCALE = 10000.0
MAXAR_SCALE = 255.0  # uint8 RGB


def spatial_train_val_split(items: list, sort_key, val_fraction: float = 0.2) -> tuple[list, list]:
    ordered = sorted(items, key=sort_key)
    n_val = max(1, round(len(ordered) * val_fraction))
    return ordered[:-n_val], ordered[-n_val:]


class MaxarPatchDataset(Dataset):
    def __init__(self, patches: list[Patch]):
        self.patches = patches

    def __len__(self) -> int:
        return len(self.patches)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        patch = self.patches[idx]
        rgb = torch.from_numpy(patch.rgb.astype("float32") / MAXAR_SCALE)
        label = torch.from_numpy(patch.label_mask.astype("float32")).unsqueeze(0)
        return rgb, label


@dataclass
class SentinelCrop:
    row0: int
    col0: int


class SentinelCropDataset(Dataset):
    """Fixed-size crops taken from ml/dataset.py's single large
    Sentinel-2 raster + label mask (unlike Maxar, which is already
    tiled into separate patches)."""

    def __init__(self, dataset: TrainingDataset, crops: list[SentinelCrop], crop_size: int):
        self.dataset = dataset
        self.crops = crops
        self.crop_size = crop_size

    def __len__(self) -> int:
        return len(self.crops)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        crop = self.crops[idx]
        s = self.crop_size
        bands = self.dataset.bands[:, crop.row0 : crop.row0 + s, crop.col0 : crop.col0 + s]
        label = self.dataset.label_mask[crop.row0 : crop.row0 + s, crop.col0 : crop.col0 + s]
        bands_t = torch.from_numpy((bands / SENTINEL2_SCALE).astype("float32"))
        label_t = torch.from_numpy(label.astype("float32")).unsqueeze(0)
        return bands_t, label_t


def list_sentinel_crops(dataset: TrainingDataset, crop_size: int, stride: int | None = None) -> list[SentinelCrop]:
    """Non-overlapping (or `stride`-spaced) crop origins covering the
    full raster, dropping any crop that would run past the edge."""
    stride = stride or crop_size
    _, height, width = dataset.bands.shape
    crops = []
    row0 = 0
    while row0 + crop_size <= height:
        col0 = 0
        while col0 + crop_size <= width:
            crops.append(SentinelCrop(row0=row0, col0=col0))
            col0 += stride
        row0 += stride
    return crops


def compute_pos_weight(dataset: Dataset, cap: float = 100.0, dampen: bool = True) -> float:
    """Real negative:positive pixel ratio across every label mask in
    `dataset` (a MaxarPatchDataset or SentinelCropDataset) -- for
    `combined_loss`'s pos_weight.

    `dampen=True` (default) takes sqrt(ratio) rather than the raw
    ratio. Verified directly on a real training run: the raw ratio
    (65.15 on the real Sentinel-2 train split) overcorrected --
    inspecting real per-crop predictions after training showed the
    model flipped from predicting background everywhere (the original
    bug this exists to fix) to predicting building almost everywhere
    (~97% of pixels positive vs. a true ~1.3%), and val IoU stayed
    near zero either way. sqrt-dampening the pixel-count ratio before
    using it as a loss weight is a standard mitigation for exactly this
    overcorrection failure mode, not an untested guess -- but it's
    still a heuristic; if the real re-run shows dampened weighting is
    still off, the next thing to try is a manually chosen constant
    (see train_sentinel.py/train_maxar.py's pos_weight override) rather
    than trusting any one formula blindly.

    Capped (default 100, applied to the dampened value) since even a
    dampened ratio from a near-empty training set can be extreme."""
    total_pixels = 0
    positive_pixels = 0
    for i in range(len(dataset)):
        _, label = dataset[i]
        total_pixels += label.numel()
        positive_pixels += int(label.sum().item())
    if positive_pixels == 0:
        return cap
    ratio = (total_pixels - positive_pixels) / positive_pixels
    if dampen:
        ratio = math.sqrt(ratio)
    return min(ratio, cap)


def compute_iou(logits: torch.Tensor, targets: torch.Tensor, threshold: float = 0.5) -> float:
    preds = (torch.sigmoid(logits) > threshold).float()
    targets = targets.float()
    intersection = (preds * targets).sum().item()
    union = ((preds + targets) > 0).float().sum().item()
    if union == 0:
        return 1.0  # both empty -- perfect agreement, not undefined
    return intersection / union


@dataclass
class TrainHistory:
    train_loss: list[float] = field(default_factory=list)
    val_loss: list[float] = field(default_factory=list)
    val_iou: list[float] = field(default_factory=list)
    best_val_iou: float = 0.0


def train_model(
    model: UNet,
    train_loader: DataLoader,
    val_loader: DataLoader,
    device: str,
    epochs: int,
    lr: float = 1e-3,
    checkpoint_path: str | None = None,
    pos_weight: float | None = None,
    use_focal: bool = False,
    focal_alpha: float = 0.25,
    focal_gamma: float = 2.0,
) -> TrainHistory:
    model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    history = TrainHistory()
    pos_weight_t = torch.tensor(pos_weight, device=device) if pos_weight is not None else None

    def _loss(logits: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
        return combined_loss(
            logits, y, pos_weight=pos_weight_t, use_focal=use_focal, focal_alpha=focal_alpha, focal_gamma=focal_gamma
        )

    for epoch in range(epochs):
        model.train()
        train_losses = []
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            logits = model(x)
            loss = _loss(logits, y)
            loss.backward()
            optimizer.step()
            train_losses.append(loss.item())

        model.eval()
        val_losses = []
        tp = fp = fn = 0
        with torch.no_grad():
            for x, y in val_loader:
                x, y = x.to(device), y.to(device)
                logits = model(x)
                val_losses.append(_loss(logits, y).item())
                pred = (torch.sigmoid(logits) > 0.5).float()
                tp += int(((pred == 1) & (y == 1)).sum().item())
                fp += int(((pred == 1) & (y == 0)).sum().item())
                fn += int(((pred == 0) & (y == 1)).sum().item())

        train_loss = float(np.mean(train_losses))
        val_loss = float(np.mean(val_losses)) if val_losses else float("nan")
        # Aggregated over the WHOLE validation set's confusion matrix,
        # not averaged per-batch. Verified this distinction matters: a
        # per-batch average let a batch with zero true positives count
        # as a "free" IoU=1.0 regardless of its size, so a checkpoint
        # with real_recall=0.0 (finds nothing) once scored *better* than
        # one with real_recall=0.31 (finds real buildings) purely
        # because the all-negative epoch happened to align with more
        # empty batches. This aggregate form can't be gamed that way.
        recall = tp / (tp + fn) if (tp + fn) > 0 else float("nan")
        precision = tp / (tp + fp) if (tp + fp) > 0 else float("nan")
        denom = tp + fp + fn
        val_iou = (tp / denom) if denom > 0 else 1.0  # both empty -- perfect agreement
        history.train_loss.append(train_loss)
        history.val_loss.append(val_loss)
        history.val_iou.append(val_iou)

        print(
            f"[train] epoch {epoch + 1}/{epochs} train_loss={train_loss:.4f} "
            f"val_loss={val_loss:.4f} val_iou={val_iou:.4f} val_recall={recall:.4f} val_precision={precision:.4f}"
        )

        if checkpoint_path is not None and val_iou > history.best_val_iou:
            history.best_val_iou = val_iou
            torch.save(model.state_dict(), checkpoint_path)
            print(f"[train] new best val_iou={val_iou:.4f}, saved to {checkpoint_path}")

    return history
