import pytest

torch = pytest.importorskip("torch")  # not in requirements.txt (add-on Docker build) -- see requirements-ml.txt

from enderata.ml.model import UNet, combined_loss, dice_loss, focal_loss


def test_unet_forward_pass_shape():
    model = UNet(in_channels=3, out_channels=1, base_channels=4)  # tiny for a fast CPU test
    x = torch.randn(2, 3, 32, 32)
    logits = model(x)
    assert logits.shape == (2, 1, 32, 32)


def test_unet_accepts_different_in_channels():
    model = UNet(in_channels=5, out_channels=1, base_channels=4)
    x = torch.randn(1, 5, 32, 32)
    logits = model(x)
    assert logits.shape == (1, 1, 32, 32)


def test_dice_loss_is_zero_for_a_perfect_match():
    logits = torch.full((1, 1, 4, 4), 10.0)  # sigmoid(10) ~= 1
    targets = torch.ones((1, 1, 4, 4))
    loss = dice_loss(logits, targets)
    assert loss.item() < 0.01


def test_dice_loss_is_near_one_for_no_overlap():
    logits = torch.full((1, 1, 4, 4), 10.0)
    targets = torch.zeros((1, 1, 4, 4))
    loss = dice_loss(logits, targets)
    assert loss.item() > 0.9


def test_focal_loss_downweights_confident_correct_predictions():
    targets = torch.ones((1, 1, 2, 2))
    confident_correct = torch.full((1, 1, 2, 2), 10.0)  # sigmoid ~= 1, matches target
    unconfident_correct = torch.full((1, 1, 2, 2), 0.1)  # sigmoid ~= 0.52, barely right

    confident_loss = focal_loss(confident_correct, targets)
    unconfident_loss = focal_loss(unconfident_correct, targets)
    assert confident_loss.item() < unconfident_loss.item()


def test_focal_loss_is_finite_and_nonnegative():
    logits = torch.randn(4, 1, 8, 8)
    targets = (torch.rand(4, 1, 8, 8) > 0.9).float()
    loss = focal_loss(logits, targets)
    assert torch.isfinite(loss)
    assert loss.item() >= 0


def test_combined_loss_with_focal_matches_focal_plus_dice():
    logits = torch.randn(2, 1, 8, 8)
    targets = (torch.rand(2, 1, 8, 8) > 0.8).float()

    combined = combined_loss(logits, targets, use_focal=True)
    expected = focal_loss(logits, targets) + dice_loss(logits, targets)
    assert combined.item() == pytest.approx(expected.item())


def test_combined_loss_with_pos_weight_differs_from_unweighted():
    logits = torch.randn(2, 1, 8, 8)
    targets = (torch.rand(2, 1, 8, 8) > 0.8).float()

    unweighted = combined_loss(logits, targets)
    weighted = combined_loss(logits, targets, pos_weight=torch.tensor(10.0))
    assert unweighted.item() != pytest.approx(weighted.item())
