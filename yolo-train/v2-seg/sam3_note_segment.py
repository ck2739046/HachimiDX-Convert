from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np
from ultralytics.models.sam import SAM3SemanticPredictor


SAM3_PT: str | None = None

# Research flags
DRAW_CONTOURS = True
DRAW_LABELS = True

# Dataset locations (this script is for the v2-seg dataset layout)
HERE = Path(__file__).resolve().parent
DATASET_ROOT = HERE / "dataset" / "11820"
IMAGES_DIR = DATASET_ROOT / "images"
LABELS_DETECT_DIR = DATASET_ROOT / "labels_detect"
LABELS_OBB_DIR = DATASET_ROOT / "labels_obb"

# Filename pattern
FILE_PREFIX = "11820_120_standardized_"
IMAGE_EXT = ".jpg"

# Hardcoded class order (from your dataset YAMLs)
DETECT_CLASS_NAMES = ["tap", "slide", "touch", "touch-hold"]
OBB_CLASS_NAMES = ["hold"]


COLORS_BGR: dict[str, tuple[int, int, int]] = {
    "tap": (0, 255, 255),
    "slide": (255, 0, 255),
    "touch": (0, 255, 0),
    "touch-hold": (0, 128, 255),
    "hold": (255, 128, 0),
}

def get_color(cls_name: str, cls_id: int) -> tuple[int, int, int]:
    if cls_name in COLORS_BGR:
        return COLORS_BGR[cls_name]
    return (255, 255, 255)


def _read_detect_boxes(label_path: Path, img_w: int, img_h: int) -> dict[int, list[list[float]]]:
    """YOLO detect format: class cx cy w h (normalized). Returns class_id -> list[xyxy]."""
    boxes_by_class: dict[int, list[list[float]]] = {}
    for line in label_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        c_s, cx_s, cy_s, w_s, h_s, *_ = line.split()
        c = int(float(c_s))
        cx = float(cx_s)
        cy = float(cy_s)
        bw = float(w_s)
        bh = float(h_s)

        x1 = (cx - bw / 2.0) * img_w
        y1 = (cy - bh / 2.0) * img_h
        x2 = (cx + bw / 2.0) * img_w
        y2 = (cy + bh / 2.0) * img_h

        boxes_by_class.setdefault(c, []).append([x1, y1, x2, y2])

    return boxes_by_class


def _read_obb_boxes(label_path: Path, img_w: int, img_h: int) -> dict[int, list[list[float]]]:
    """YOLO OBB format: class x1 y1 x2 y2 x3 y3 x4 y4 (normalized). Returns class_id -> list[xyxy]."""
    boxes_by_class: dict[int, list[list[float]]] = {}
    for line in label_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split()
        c = int(float(parts[0]))
        coords = [float(x) for x in parts[1:9]]
        xs = [coords[i] * img_w for i in (0, 2, 4, 6)]
        ys = [coords[i] * img_h for i in (1, 3, 5, 7)]

        x1 = min(xs)
        y1 = min(ys)
        x2 = max(xs)
        y2 = max(ys)
        boxes_by_class.setdefault(c, []).append([x1, y1, x2, y2])

    return boxes_by_class


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


def main_ids(frame_ids: list[int], output_dir: str) -> None:
    """Segment only the given frame ids (no directory scanning)."""
    if SAM3_PT is None:
        raise RuntimeError("SAM3_PT must be set.")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    overrides: dict[str, Any] = {
        "conf": 0.25,
        "task": "segment",
        "mode": "predict",
        "model": str(SAM3_PT),
        "imgsz": 644,  # 14 的倍数
        "half": True,
        "save": False,
        "verbose": False,
    }
    predictor = SAM3SemanticPredictor(overrides=overrides)

    for idx, frame_id in enumerate(frame_ids, start=1):
        stem = f"{FILE_PREFIX}{frame_id}"
        img_path = IMAGES_DIR / f"{stem}{IMAGE_EXT}"
        det_path = LABELS_DETECT_DIR / f"{stem}.txt"
        obb_path = LABELS_OBB_DIR / f"{stem}.txt"

        image_bgr = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
        h, w = image_bgr.shape[:2]

        detect_boxes = _read_detect_boxes(det_path, w, h)
        obb_boxes = _read_obb_boxes(obb_path, w, h)

        predictor.set_image(str(img_path))
        overlay = image_bgr.copy()
        alpha = 0.45

        # Detect classes (tap/slide/touch/touch-hold)
        for cls_id, bboxes in detect_boxes.items():
            cls_name = DETECT_CLASS_NAMES[cls_id]
            results = predictor(bboxes=bboxes)
            masks = results[0].masks.data.detach().cpu().numpy()
            if masks.ndim == 4:
                masks = masks.squeeze(1)
            color = get_color(cls_name, cls_id)
            for mask in masks:
                _overlay_mask_bgr(overlay, mask, color, alpha)
                _draw_contours_and_label(overlay, mask, cls_name, color)

        # OBB classes (hold)
        for cls_id, bboxes in obb_boxes.items():
            cls_name = OBB_CLASS_NAMES[cls_id]
            results = predictor(bboxes=bboxes)
            masks = results[0].masks.data.detach().cpu().numpy()
            if masks.ndim == 4:
                masks = masks.squeeze(1)
            color = get_color(cls_name, 1000 + cls_id)
            for mask in masks:
                _overlay_mask_bgr(overlay, mask, color, alpha)
                _draw_contours_and_label(overlay, mask, cls_name, color)

        out_path = out_dir / f"{stem}{IMAGE_EXT}"
        cv2.imwrite(str(out_path), overlay)
        print(f"[{idx}/{len(frame_ids)}] Wrote: {out_path}")


if __name__ == "__main__":

    SAM3_PT = r"D:\git\aaa-HachimiDX-Convert\yolo-train\sam3.pt"

    FRAME_IDS = [512, 1080, 1459, 2223, 2458, 3242, 3616, 4435,
                 4660, 4720, 5757, 30472, 30482, 29172, 28591]

    output_dir = str(HERE / "sam3_output")
    main_ids(FRAME_IDS, output_dir)
