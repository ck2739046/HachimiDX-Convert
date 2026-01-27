"""Compare YOLO detect + OBB model outputs against ground-truth label txt files.

Dataset layout (original_dataset):
  original_dataset/<group_id>/{images,labels_detect,labels_obb}/

- detect labels: class x_center y_center width height  (normalized)
- obb labels:    class x1 y1 x2 y2 x3 y3 x4 y4        (normalized)

This script is designed for large datasets (tens of thousands of images):
- streams inference (no bulk image list)
- does not keep per-image results in memory
- writes suspect ids to output file incrementally

Output line format (one per line): <group_id>_<inner_id>
Example: 11820_2000
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

from pathlib import Path
import cv2
import numpy as np
from ultralytics import YOLO


_NUMERIC_GROUP_RE = re.compile(r"^\d+$")
_LAST_INT_RE = re.compile(r"(\d+)$")


@dataclass(frozen=True)
class CompareThresholds:
    # IoU thresholds used to count a match as TP
    detect_match_iou: float = 0.80
    obb_match_iou: float = 0.70

    # Flag image as bad if quality is below these thresholds
    detect_min_f1: float = 0.80
    obb_min_f1: float = 0.60

    # Also flag if matched boxes exist but are too imprecise
    detect_min_mean_iou: float = 0.85
    obb_min_mean_iou: float = 0.75

    # Special-case: if GT is empty but predictions are too many
    detect_max_fp_when_no_gt: int = 1
    obb_max_fp_when_no_gt: int = 0


@dataclass(frozen=True)
class MatchStats:
    tp: int
    fp: int
    fn: int
    mean_iou: float

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom else 1.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom else 1.0

    @property
    def f1(self) -> float:
        p = self.precision
        r = self.recall
        return (2 * p * r / (p + r)) if (p + r) else 0.0


def _is_numeric_group_dir(name: str) -> bool:
    return bool(_NUMERIC_GROUP_RE.fullmatch(name))


def _inner_id_from_stem(stem: str) -> str:
    # Examples:
    #   11311_120_standardized_10000 -> 10000
    # If no trailing digits exist, fall back to full stem.
    m = _LAST_INT_RE.search(stem)
    return m.group(1) if m else stem


def _iter_group_dirs(original_dataset_dir: str) -> Iterable[Tuple[str, str]]:
    # yields (group_id, group_dir)
    with os.scandir(original_dataset_dir) as it:
        for entry in it:
            if not entry.is_dir():
                continue
            if not _is_numeric_group_dir(entry.name):
                continue
            yield entry.name, entry.path


def _read_detect_gt(label_path: str, w: int, h: int) -> List[Tuple[int, Tuple[float, float, float, float]]]:
    # returns [(cls, (x1,y1,x2,y2))] in pixel coordinates
    if not os.path.exists(label_path):
        return []
    boxes: List[Tuple[int, Tuple[float, float, float, float]]] = []
    with open(label_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) != 5:
                continue
            cls = int(float(parts[0]))
            xc = float(parts[1]) * w
            yc = float(parts[2]) * h
            bw = float(parts[3]) * w
            bh = float(parts[4]) * h
            x1 = xc - bw / 2.0
            y1 = yc - bh / 2.0
            x2 = xc + bw / 2.0
            y2 = yc + bh / 2.0
            boxes.append((cls, (x1, y1, x2, y2)))
    return boxes


def _read_obb_gt(label_path: str, w: int, h: int) -> List[Tuple[int, "cv2.Mat"]]:
    # returns [(cls, pts)] where pts is (4,2) float32 pixel coordinates
    if not os.path.exists(label_path):
        return []
    polys: List[Tuple[int, "cv2.Mat"]] = []
    with open(label_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) != 9:
                continue
            cls = int(float(parts[0]))
            coords = list(map(float, parts[1:]))
            pts = []
            for i in range(0, 8, 2):
                pts.append([coords[i] * w, coords[i + 1] * h])
            poly = np.asarray(pts, dtype=np.float32).reshape(4, 2)
            polys.append((cls, poly))
    return polys


def _iou_xyxy(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _poly_area(poly: "cv2.Mat") -> float:
    return float(abs(cv2.contourArea(poly.reshape(-1, 1, 2))))


def _iou_poly(a: "cv2.Mat", b: "cv2.Mat") -> float:
    # Works for convex polygons (our 4-point OBBs). Uses OpenCV convex intersection.
    a_pts = a.astype("float32").reshape(-1, 1, 2)
    b_pts = b.astype("float32").reshape(-1, 1, 2)

    inter_area, _ = cv2.intersectConvexConvex(a_pts, b_pts)
    if inter_area <= 0:
        return 0.0

    area_a = _poly_area(a)
    area_b = _poly_area(b)
    union = area_a + area_b - float(inter_area)
    return float(inter_area) / union if union > 0 else 0.0


def _greedy_match(
    gt: Sequence[Tuple[int, object]],
    pred: Sequence[Tuple[int, object]],
    iou_fn,
    match_iou: float,
) -> MatchStats:
    # Greedy matching by best IoU per-GT among same-class predictions.
    used_pred = [False] * len(pred)
    matched_ious: List[float] = []

    tp = 0
    fn = 0

    for gt_cls, gt_box in gt:
        best_iou = 0.0
        best_j = -1
        for j, (p_cls, p_box) in enumerate(pred):
            if used_pred[j]:
                continue
            if p_cls != gt_cls:
                continue
            iou = float(iou_fn(gt_box, p_box))
            if iou > best_iou:
                best_iou = iou
                best_j = j

        if best_j >= 0 and best_iou >= match_iou:
            used_pred[best_j] = True
            tp += 1
            matched_ious.append(best_iou)
        else:
            fn += 1

    fp = sum(1 for u in used_pred if not u)
    mean_iou = (sum(matched_ious) / len(matched_ious)) if matched_ious else 1.0
    return MatchStats(tp=tp, fp=fp, fn=fn, mean_iou=mean_iou)


def _flag_large_diff_detect(stats: MatchStats, gt_count: int, th: CompareThresholds) -> bool:
    if gt_count == 0:
        return stats.fp > th.detect_max_fp_when_no_gt
    if stats.f1 < th.detect_min_f1:
        return True
    if stats.tp > 0 and stats.mean_iou < th.detect_min_mean_iou:
        return True
    return False


def _flag_large_diff_obb(stats: MatchStats, gt_count: int, th: CompareThresholds) -> bool:
    if gt_count == 0:
        return stats.fp > th.obb_max_fp_when_no_gt
    if stats.f1 < th.obb_min_f1:
        return True
    if stats.tp > 0 and stats.mean_iou < th.obb_min_mean_iou:
        return True
    return False


def _predict_detect_on_dir(model: YOLO, images_dir: str, device: str | None) -> Iterable[object]:
    # Stream results so we don't hold the full dataset in memory.
    return model.predict(
        source=images_dir,
        task="detect",
        stream=True,
        imgsz=960,
        device=device,
        max_det=50,
        verbose=False,
        half=True,
        save=False,
        save_txt=False,
        save_conf=False,
    )


def _predict_obb_on_image(model: YOLO, image_path: str, device: str | None) -> object:
    res = model.predict(
        source=image_path,
        task="obb",
        stream=False,
        imgsz=960,
        device=device,
        max_det=50,
        verbose=False,
        half=True,
        save=False,
        save_txt=False,
        save_conf=False,
    )
    return res[0]


def compare_dataset(
    original_dataset_dir: str,
    detect_model_path: str,
    obb_model_path: str,
    detect_output_txt_path: str,
    obb_output_txt_path: str,
    thresholds: Optional[CompareThresholds] = None,
    device: str | None = "0",
    progress_every: int = 200,
) -> None:
    th = thresholds or CompareThresholds()

    detect_model = YOLO(detect_model_path)
    obb_model = YOLO(obb_model_path)

    os.makedirs(os.path.dirname(os.path.abspath(detect_output_txt_path)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(obb_output_txt_path)), exist_ok=True)

    processed = 0
    detect_bad = 0
    obb_bad = 0

    # Line-buffered output for near-real-time streaming writes.
    with (
        open(detect_output_txt_path, "a", encoding="utf-8", buffering=1) as detect_out,
        open(obb_output_txt_path, "a", encoding="utf-8", buffering=1) as obb_out,
    ):
        for group_id, group_dir in _iter_group_dirs(original_dataset_dir):
            images_dir = os.path.join(group_dir, "images")
            labels_detect_dir = os.path.join(group_dir, "labels_detect")
            labels_obb_dir = os.path.join(group_dir, "labels_obb")

            if not os.path.isdir(images_dir):
                continue

            # detect model streams across the images dir
            for det_res in _predict_detect_on_dir(detect_model, images_dir, device=device):
                processed += 1

                # ultralytics result has .path and .orig_shape
                image_path = getattr(det_res, "path", None)
                if not image_path:
                    continue

                h, w = det_res.orig_shape
                stem = os.path.splitext(os.path.basename(image_path))[0]

                gt_det_path = os.path.join(labels_detect_dir, f"{stem}.txt")
                gt_obb_path = os.path.join(labels_obb_dir, f"{stem}.txt")

                gt_det = _read_detect_gt(gt_det_path, w=w, h=h)
                gt_obb = _read_obb_gt(gt_obb_path, w=w, h=h)

                # Predictions: detect
                pred_det: List[Tuple[int, Tuple[float, float, float, float]]] = []
                if det_res.boxes is not None and len(det_res.boxes) > 0:
                    boxes = det_res.boxes.cpu().numpy()
                    xyxy = boxes.xyxy
                    cls = boxes.cls
                    for i in range(len(xyxy)):
                        pred_det.append(
                            (int(cls[i]), (float(xyxy[i, 0]), float(xyxy[i, 1]), float(xyxy[i, 2]), float(xyxy[i, 3])))
                        )

                # Predictions: obb
                obb_res = _predict_obb_on_image(obb_model, image_path, device=device)
                pred_obb: List[Tuple[int, "cv2.Mat"]] = []
                if obb_res.obb is not None and len(obb_res.obb) > 0:
                    obb = obb_res.obb.cpu().numpy()
                    xyxyxyxy = obb.xyxyxyxy  # (N, 4, 2) in pixels
                    cls = obb.cls
                    for i in range(len(xyxyxyxy)):
                        poly = xyxyxyxy[i].astype("float32")
                        pred_obb.append((int(cls[i]), poly))

                det_stats = _greedy_match(gt_det, pred_det, _iou_xyxy, match_iou=th.detect_match_iou)
                obb_stats = _greedy_match(gt_obb, pred_obb, _iou_poly, match_iou=th.obb_match_iou)

                detect_is_bad = _flag_large_diff_detect(det_stats, gt_count=len(gt_det), th=th)
                obb_is_bad = _flag_large_diff_obb(obb_stats, gt_count=len(gt_obb), th=th)

                if detect_is_bad or obb_is_bad:
                    inner_id = _inner_id_from_stem(stem)
                    out_line = f"{group_id}_{inner_id}\n"
                    if detect_is_bad:
                        detect_out.write(out_line)
                        detect_bad += 1
                    if obb_is_bad:
                        obb_out.write(out_line)
                        obb_bad += 1

                if progress_every > 0 and processed % progress_every == 0:
                    print(
                        " ".join(
                            [
                                f"processed={processed}, detect_bad={detect_bad}, obb_bad={obb_bad},",
                                f"group={group_id}, last={os.path.basename(image_path)}",
                            ]
                        ),
                        flush=True,
                    )

                # Ensure we don't accidentally keep big objects alive
                del det_res
                del obb_res

    print(
        " ".join(
            [
                f"Done. processed={processed}, detect_bad={detect_bad}, obb_bad={obb_bad},",
                f"detect_output={detect_output_txt_path}, obb_output={obb_output_txt_path}",
            ]
        )
    )


if __name__ == "__main__":

    HERE = Path(__file__).resolve().parent

    DETECT_PT_PATH = HERE / "detect.pt"
    OBB_PT_PATH = HERE / "obb.pt"
    DETECT_OUTPUT_TXT_PATH = HERE / "detect_bad_ids.txt"
    OBB_OUTPUT_TXT_PATH = HERE / "obb_bad_ids.txt"
    ORIGINAL_DATASET_DIR = HERE / "original_dataset"

    compare_dataset(
        original_dataset_dir=ORIGINAL_DATASET_DIR,
        detect_model_path=DETECT_PT_PATH,
        obb_model_path=OBB_PT_PATH,
        detect_output_txt_path=DETECT_OUTPUT_TXT_PATH,
        obb_output_txt_path=OBB_OUTPUT_TXT_PATH,
        thresholds=CompareThresholds(),
        device="0",
        progress_every=100,
    )
