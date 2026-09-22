import numpy as np
import pytest

torch = pytest.importorskip("torch")  # not in requirements.txt (add-on Docker build) -- see requirements-ml.txt

from enderata.ml.dataset import TrainingDataset
from enderata.ml.maxar_dataset import Patch
from enderata.ml.train import (
    MaxarPatchDataset,
    SentinelCropDataset,
    compute_iou,
    compute_pos_weight,
    list_sentinel_crops,
    spatial_train_val_split,
)


def test_spatial_train_val_split_holds_out_the_tail_by_sort_key():
    items = [3, 1, 4, 1, 5, 9, 2, 6]
    train, val = spatial_train_val_split(items, sort_key=lambda x: x, val_fraction=0.25)
    assert train == [1, 1, 2, 3, 4, 5]
    assert val == [6, 9]


def test_spatial_train_val_split_always_holds_out_at_least_one():
    train, val = spatial_train_val_split([1, 2, 3], sort_key=lambda x: x, val_fraction=0.01)
    assert len(val) == 1
    assert len(train) == 2


def _fake_patch(size=16):
    return Patch(
        rgb=np.random.randint(0, 255, (3, size, size), dtype="uint8"),
        label_mask=np.zeros((size, size), dtype="uint8"),
        bounds_proj=(0.0, 0.0, size * 0.5, size * 0.5),
    )


def test_maxar_patch_dataset_returns_normalized_tensors_with_right_shape():
    patches = [_fake_patch(size=16) for _ in range(3)]
    dataset = MaxarPatchDataset(patches)
    assert len(dataset) == 3

    rgb, label = dataset[0]
    assert rgb.shape == (3, 16, 16)
    assert label.shape == (1, 16, 16)
    assert rgb.max() <= 1.0 and rgb.min() >= 0.0  # normalized to [0,1]
    assert rgb.dtype == torch.float32


def test_compute_pos_weight_undamped_matches_the_real_ratio():
    # 3 patches of 4x4=16 pixels each, 48 total; exactly 4 positive pixels
    # across all of them -> ratio = (48-4)/4 = 11.0
    patches = []
    for i in range(3):
        p = _fake_patch(size=4)
        p.label_mask[:] = 0
        patches.append(p)
    patches[0].label_mask[0, 0] = 1
    patches[0].label_mask[0, 1] = 1
    patches[1].label_mask[0, 0] = 1
    patches[2].label_mask[0, 0] = 1

    dataset = MaxarPatchDataset(patches)
    assert compute_pos_weight(dataset, dampen=False) == 11.0


def test_compute_pos_weight_dampens_by_default_with_sqrt():
    # Same data as above (ratio=11.0) -- default dampen=True must
    # return sqrt(11.0), not the raw ratio. Verified against a real
    # training run: the raw ratio overcorrected the model to predicting
    # positive almost everywhere (see train.py's docstring).
    patches = []
    for i in range(3):
        p = _fake_patch(size=4)
        p.label_mask[:] = 0
        patches.append(p)
    patches[0].label_mask[0, 0] = 1
    patches[0].label_mask[0, 1] = 1
    patches[1].label_mask[0, 0] = 1
    patches[2].label_mask[0, 0] = 1

    dataset = MaxarPatchDataset(patches)
    assert compute_pos_weight(dataset) == pytest.approx(11.0**0.5)


def test_compute_pos_weight_caps_extreme_ratios():
    patches = [_fake_patch(size=4) for _ in range(2)]
    for p in patches:
        p.label_mask[:] = 0  # no positive pixels at all
    dataset = MaxarPatchDataset(patches)
    assert compute_pos_weight(dataset, cap=50.0) == 50.0


def _fake_sentinel_dataset(height=32, width=48):
    bands = np.random.rand(5, height, width).astype("float32") * 3000
    label_mask = np.zeros((height, width), dtype="uint8")
    label_mask[10:15, 10:15] = 1
    return TrainingDataset(
        bands=bands,
        label_mask=label_mask,
        transform=None,
        crs="EPSG:32733",
        bounds_wgs84=(0.0, 0.0, 1.0, 1.0),
        scene_id="fake",
        scene_datetime="2026-01-01",
    )


def test_list_sentinel_crops_covers_the_raster_without_running_past_the_edge():
    ds = _fake_sentinel_dataset(height=32, width=48)
    crops = list_sentinel_crops(ds, crop_size=16)
    for crop in crops:
        assert crop.row0 + 16 <= 32
        assert crop.col0 + 16 <= 48
    # 32/16=2 rows of crops, 48/16=3 cols of crops
    assert len(crops) == 6


def test_sentinel_crop_dataset_returns_the_right_slice():
    ds = _fake_sentinel_dataset(height=32, width=48)
    crops = list_sentinel_crops(ds, crop_size=16)
    dataset = SentinelCropDataset(ds, crops, crop_size=16)

    bands_t, label_t = dataset[0]
    assert bands_t.shape == (5, 16, 16)
    assert label_t.shape == (1, 16, 16)
    # the crop starting at (0,0) should include the labeled square at [10:15,10:15]
    assert label_t.sum() > 0


def test_compute_iou_perfect_match():
    logits = torch.full((1, 1, 4, 4), 10.0)  # sigmoid(10) ~= 1
    targets = torch.ones((1, 1, 4, 4))
    assert compute_iou(logits, targets) == 1.0


def test_compute_iou_no_overlap():
    logits = torch.full((1, 1, 4, 4), 10.0)
    targets = torch.zeros((1, 1, 4, 4))
    assert compute_iou(logits, targets) == 0.0


def test_compute_iou_both_empty_is_perfect_agreement():
    logits = torch.full((1, 1, 4, 4), -10.0)  # sigmoid(-10) ~= 0
    targets = torch.zeros((1, 1, 4, 4))
    assert compute_iou(logits, targets) == 1.0
