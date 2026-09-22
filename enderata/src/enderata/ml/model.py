"""A small U-Net for binary segmentation, shared between both training
pipelines: the Sentinel-2 per-pixel built-up classifier (ml/dataset.py,
5 input channels) and the Maxar per-building segmentation model
(ml/maxar_dataset.py, 3 input channels) -- same architecture, just a
different in_channels and training data. User's instruction: both
datasets feed real models, precision prioritized over training speed
-- this is a standard 4-level encoder/decoder U-Net with skip
connections and BatchNorm, not a minimal/toy shortcut version.

Sized for a 6GB GPU (verified locally against a real NVIDIA RTX A1000):
default channel widths (32-512 at the bottleneck) -- see train.py for
the batch sizes actually used at each patch size.

Input spatial dimensions (H, W) must both be divisible by 16 (four
2x poolings) -- patch sizes used elsewhere in this package (512 for
Maxar, a multiple-of-16 crop size for Sentinel-2) satisfy this.
"""

from __future__ import annotations

import torch
from torch import nn


class DoubleConv(nn.Module):
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.block(x)


class UNet(nn.Module):
    def __init__(self, in_channels: int, out_channels: int = 1, base_channels: int = 32):
        super().__init__()
        c = base_channels
        self.enc1 = DoubleConv(in_channels, c)
        self.enc2 = DoubleConv(c, c * 2)
        self.enc3 = DoubleConv(c * 2, c * 4)
        self.enc4 = DoubleConv(c * 4, c * 8)
        self.pool = nn.MaxPool2d(2)

        self.bottleneck = DoubleConv(c * 8, c * 16)

        self.up4 = nn.ConvTranspose2d(c * 16, c * 8, kernel_size=2, stride=2)
        self.dec4 = DoubleConv(c * 16, c * 8)
        self.up3 = nn.ConvTranspose2d(c * 8, c * 4, kernel_size=2, stride=2)
        self.dec3 = DoubleConv(c * 8, c * 4)
        self.up2 = nn.ConvTranspose2d(c * 4, c * 2, kernel_size=2, stride=2)
        self.dec2 = DoubleConv(c * 4, c * 2)
        self.up1 = nn.ConvTranspose2d(c * 2, c, kernel_size=2, stride=2)
        self.dec1 = DoubleConv(c * 2, c)

        self.out_conv = nn.Conv2d(c, out_channels, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        e4 = self.enc4(self.pool(e3))

        b = self.bottleneck(self.pool(e4))

        d4 = self.dec4(torch.cat([self.up4(b), e4], dim=1))
        d3 = self.dec3(torch.cat([self.up3(d4), e3], dim=1))
        d2 = self.dec2(torch.cat([self.up2(d3), e2], dim=1))
        d1 = self.dec1(torch.cat([self.up1(d2), e1], dim=1))

        return self.out_conv(d1)  # logits, shape (B, out_channels, H, W)


def dice_loss(logits: torch.Tensor, targets: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
    probs = torch.sigmoid(logits)
    targets = targets.float()
    intersection = (probs * targets).sum(dim=(1, 2, 3))
    union = probs.sum(dim=(1, 2, 3)) + targets.sum(dim=(1, 2, 3))
    dice = (2 * intersection + eps) / (union + eps)
    return 1 - dice.mean()


def focal_loss(
    logits: torch.Tensor, targets: torch.Tensor, alpha: float = 0.25, gamma: float = 2.0
) -> torch.Tensor:
    """Focal loss (Lin et al. 2017) -- an alternative to weighted BCE
    for severe class imbalance. Down-weights already-easy/confident
    predictions per PIXEL (via (1-p_t)^gamma) and balances the rare
    positive class via `alpha`, rather than applying one global scalar
    to every positive pixel regardless of how confidently it's already
    predicted.

    Added after `combined_loss`'s `pos_weight` alone proved too coarse
    a tool at this imbalance level, verified on two real training runs
    (Sentinel-2, ~1.3% positive pixels): the raw imbalance ratio (65)
    as pos_weight flipped the model to predicting positive on ~97% of
    pixels; a sqrt-dampened ratio (8.07) wasn't enough to escape
    predicting negative everywhere (0 true positives across every
    validation crop, confirmed by inspecting real per-pixel
    predictions both times) -- a single scalar reweight sits on a
    knife edge between two collapse modes for this data. Focal loss's
    per-pixel modulation is the standard next step in the literature
    for exactly this failure pattern, not a second untested guess."""
    targets = targets.float()
    bce = nn.functional.binary_cross_entropy_with_logits(logits, targets, reduction="none")
    probs = torch.sigmoid(logits)
    p_t = probs * targets + (1 - probs) * (1 - targets)
    alpha_t = alpha * targets + (1 - alpha) * (1 - targets)
    return (alpha_t * (1 - p_t).clamp(min=0) ** gamma * bce).mean()


def combined_loss(
    logits: torch.Tensor,
    targets: torch.Tensor,
    pos_weight: torch.Tensor | None = None,
    use_focal: bool = False,
    focal_alpha: float = 0.25,
    focal_gamma: float = 2.0,
) -> torch.Tensor:
    """BCE (or focal, if `use_focal=True`) + Dice -- standard pairing
    for imbalanced binary segmentation (our positive-pixel fraction is
    ~1-7%, see ml/dataset.py and ml/maxar_dataset.py's verified
    real-data stats).

    `pos_weight` (pass the real negative:positive pixel ratio from the
    training data, see train.py) is NOT optional in practice at this
    imbalance level if `use_focal=False`: verified directly on a real
    training run without it (Sentinel-2, ~1.3% positive pixels) -- the
    model collapsed to predicting background everywhere (logits
    ~0.40-0.49 across every pixel of every validation crop, confirmed
    by inspecting real per-crop predictions), because BCE's abundant,
    easy-to-fit negative
    class dominated the combined gradient. `pos_weight` counteracts
    that by scaling up the loss contribution of positive pixels."""
    if use_focal:
        cls_loss = focal_loss(logits, targets, alpha=focal_alpha, gamma=focal_gamma)
    else:
        cls_loss = nn.functional.binary_cross_entropy_with_logits(logits, targets.float(), pos_weight=pos_weight)
    dice = dice_loss(logits, targets)
    return cls_loss + dice
