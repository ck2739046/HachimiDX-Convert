from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np
from ultralytics.models.sam import SAM3SemanticPredictor


SAM3_PT: str | None = None

PROMPTS: dict[str, str] = {
    "tap_note": "hollow circular ring",
    "hold_note": "elongated hexagonal frame",
    "slide_note": "star polygon outline",
    "touch_note": "cluster of four inward-pointing triangles",
    "touch_hold": "geometric diamond enclosed by a circular arc",
    "wifi_tip": "pattern of parallel chevron lines",
}

# Control flags (research use only)
DRAW_CONTOURS = True   # Draw contour lines around each mask
DRAW_LABELS = True     # Draw class name label

# BGR colors for OpenCV overlay
COLORS_BGR: dict[str, tuple[int, int, int]] = {
    "tap_note": (0, 255, 255),  # yellow
    "hold_note": (255, 128, 0),  # blue-ish (BGR)
    "slide_note": (255, 0, 255),  # magenta
    "touch_note": (0, 255, 0),  # green
    "touch_hold": (0, 128, 255),  # orange
    "wifi_tip": (255, 255, 0),  # cyan
}

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def _iter_images(input_dir: str | os.PathLike[str]) -> Iterable[Path]:
    base = Path(input_dir)
    for p in sorted(base.rglob("*")):
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
            yield p


def _overlay_mask_bgr(image_bgr: np.ndarray, mask: np.ndarray, color_bgr: tuple[int, int, int], alpha: float) -> None:
    """In-place tint overlay on the original image using mask as per-pixel alpha.

    If mask is float (0..1), we preserve soft edges by scaling alpha per pixel.
    """
    if mask.ndim != 2:
        raise ValueError(f"mask must be 2D, got shape={mask.shape}")

    if mask.dtype == np.bool_:
        mask_f = mask.astype(np.float32)
    else:
        mask_f = mask.astype(np.float32)
        # SAM masks are typically 0..1 floats; clamp defensively.
        mask_f = np.clip(mask_f, 0.0, 1.0)

    a = (mask_f * float(alpha)).astype(np.float32)  # HxW
    if float(alpha) <= 0.0:
        return

    img_f = image_bgr.astype(np.float32)
    color = np.array(color_bgr, dtype=np.float32).reshape(1, 1, 3)
    img_f = img_f * (1.0 - a[..., None]) + color * a[..., None]
    image_bgr[:] = img_f.astype(np.uint8)


def _draw_contours_and_label(
    image_bgr: np.ndarray,
    mask: np.ndarray,
    label: str,
    color_bgr: tuple[int, int, int],
) -> None:
    if not DRAW_CONTOURS and not DRAW_LABELS:
        return

    # Contours need a binary mask.
    if mask.dtype == np.bool_:
        bin_mask = mask
    else:
        bin_mask = (mask.astype(np.float32) > 0.5)

    mask_u8 = (bin_mask.astype(np.uint8) * 255)
    contours, _hier = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return

    if DRAW_CONTOURS:
        cv2.drawContours(image_bgr, contours, -1, color_bgr, thickness=2)

    if DRAW_LABELS:
        # Label at the largest contour
        largest = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest)
        cv2.putText(
            image_bgr,
            label,
            (x, max(0, y - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color_bgr,
            2,
            cv2.LINE_AA,
        )


def main(input_dir: str, output_dir: str) -> None:
    """Batch-segment all images in input_dir and save colored overlays to output_dir."""
    if not SAM3_PT:
        raise RuntimeError("SAM3_PT is not set. Please set it in __main__.")

    in_dir = Path(input_dir)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    overrides = dict(
        conf=0.25,
        task="segment",
        mode="predict",
        model=str(SAM3_PT),
        half=True,
        save=False,
        verbose=False,
    )
    predictor = SAM3SemanticPredictor(overrides=overrides)

    images = list(_iter_images(in_dir))
    if not images:
        print(f"No images found under: {in_dir}")
        return

    print(f"Found {len(images)} images. Output -> {out_dir}")

    for i, img_path in enumerate(images, start=1):
        rel = img_path.relative_to(in_dir)
        out_path = out_dir / rel
        out_path.parent.mkdir(parents=True, exist_ok=True)

        image_bgr = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
        if image_bgr is None:
            print(f"[{i}/{len(images)}] Skip unreadable: {img_path}")
            continue

        predictor.set_image(str(img_path))

        overlay = image_bgr.copy()
        alpha = 0.45

        for cls, prompt in PROMPTS.items():
            try:
                results = predictor(text=[prompt])
            except Exception as e:
                print(f"[{i}/{len(images)}] Prompt failed ({cls}): {e}")
                continue

            if not results:
                continue

            r0 = results[0]
            if getattr(r0, "masks", None) is None or r0.masks is None:
                continue

            masks_t = getattr(r0.masks, "data", None)
            if masks_t is None:
                continue

            masks = masks_t.detach().cpu().numpy()
            if masks.ndim != 3:
                continue

            color = COLORS_BGR.get(cls, (0, 0, 255))
            for mask in masks:
                _overlay_mask_bgr(overlay, mask, color, alpha)
                _draw_contours_and_label(overlay, mask, cls, color)

        cv2.imwrite(str(out_path), overlay)
        print(f"[{i}/{len(images)}] Wrote: {out_path}")


if __name__ == "__main__":

    SAM3_PT = r"D:\git\aaa-HachimiDX-Convert\yolo-train\sam3.pt"
    input_dir = r"C:\Users\ck273\Desktop\a"
    output_dir = r"C:\Users\ck273\Desktop\b"

    main(input_dir, output_dir)
