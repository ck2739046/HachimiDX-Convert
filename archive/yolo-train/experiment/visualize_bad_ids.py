"""Visualize bad-ids by overlaying GT (green) and model predictions (red).

Input:
- bad_ids txt: each line is <group_id>_<inner_id>
- dataset layout:
    original_dataset/<group_id>/{images,labels_detect,labels_obb}/

Output:
- Writes annotated images to output dir.

Usage examples:
  python visualize_bad_ids.py \
    --task detect \
    --model detect.pt \
    --bad-ids detect_bad_ids.txt \
    --original-dataset ../original_dataset \
    --output-dir ./viz_detect

  python visualize_bad_ids.py \
    --task obb \
    --model obb.pt \
    --bad-ids obb_bad_ids.txt \
    --original-dataset ../original_dataset \
    --output-dir ./viz_obb
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import cv2
import numpy as np
from ultralytics import YOLO


_LAST_INT_RE = re.compile(r"(\d+)$")


@dataclass(frozen=True)
class Paths:
    group_dir: Path
    images_dir: Path
    labels_detect_dir: Path
    labels_obb_dir: Path


def _inner_id_from_stem(stem: str) -> str:
    m = _LAST_INT_RE.search(stem)
    return m.group(1) if m else stem


def _iter_bad_ids(bad_ids_path: Path) -> Iterable[Tuple[str, str]]:
    with bad_ids_path.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            if "_" not in s:
                continue
            group_id, inner_id = s.split("_", 1)
            yield group_id, inner_id


def _resolve_group_paths(original_dataset: Path, group_id: str) -> Paths:
    group_dir = original_dataset / group_id
    return Paths(
        group_dir=group_dir,
        images_dir=group_dir / "images",
        labels_detect_dir=group_dir / "labels_detect",
        labels_obb_dir=group_dir / "labels_obb",
    )


def _build_inner_id_index(images_dir: Path) -> Dict[str, Path]:
    index: Dict[str, Path] = {}
    if not images_dir.is_dir():
        return index

    for p in images_dir.iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
            continue
        inner_id = _inner_id_from_stem(p.stem)
        # If collisions happen, keep the first and warn later when resolving.
        index.setdefault(inner_id, p)
    return index


def _read_detect_gt(label_path: Path, w: int, h: int) -> List[Tuple[int, Tuple[float, float, float, float]]]:
    if not label_path.exists():
        return []

    out: List[Tuple[int, Tuple[float, float, float, float]]] = []
    for raw in label_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
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
        out.append((cls, (x1, y1, x2, y2)))
    return out


def _read_obb_gt(label_path: Path, w: int, h: int) -> List[Tuple[int, np.ndarray]]:
    if not label_path.exists():
        return []

    out: List[Tuple[int, np.ndarray]] = []
    for raw in label_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
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
        out.append((cls, poly))
    return out


def _draw_detect_boxes(img: np.ndarray, boxes: Sequence[Tuple[int, Tuple[float, float, float, float]]], color: Tuple[int, int, int]) -> None:
    for cls, (x1, y1, x2, y2) in boxes:
        p1 = (int(round(x1)), int(round(y1)))
        p2 = (int(round(x2)), int(round(y2)))
        cv2.rectangle(img, p1, p2, color, 4)
        cv2.putText(
            img,
            str(cls),
            (p1[0], max(0, p1[1] - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            3,
            cv2.LINE_AA,
        )


def _draw_obb_polys(img: np.ndarray, polys: Sequence[Tuple[int, np.ndarray]], color: Tuple[int, int, int]) -> None:
    for cls, poly in polys:
        pts = poly.reshape(-1, 1, 2).astype(np.int32)
        cv2.polylines(img, [pts], isClosed=True, color=color, thickness=4)
        # label at first point
        x0, y0 = int(pts[0, 0, 0]), int(pts[0, 0, 1])
        cv2.putText(
            img,
            str(cls),
            (x0, max(0, y0 - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            3,
            cv2.LINE_AA,
        )


def _predict_detect(model: YOLO, image_path: Path, device: Optional[str], imgsz: int, half: bool) -> List[Tuple[int, Tuple[float, float, float, float]]]:
    res = model.predict(
        source=str(image_path),
        task="detect",
        stream=False,
        imgsz=imgsz,
        device=device,
        verbose=False,
        half=half,
        save=False,
        save_txt=False,
        save_conf=False,
        max_det=50,
    )[0]

    pred: List[Tuple[int, Tuple[float, float, float, float]]] = []
    if res.boxes is None or len(res.boxes) == 0:
        return pred

    boxes = res.boxes.cpu().numpy()
    xyxy = boxes.xyxy
    cls = boxes.cls
    for i in range(len(xyxy)):
        pred.append(
            (int(cls[i]), (float(xyxy[i, 0]), float(xyxy[i, 1]), float(xyxy[i, 2]), float(xyxy[i, 3])))
        )
    return pred


def _predict_obb(model: YOLO, image_path: Path, device: Optional[str], imgsz: int, half: bool) -> List[Tuple[int, np.ndarray]]:
    res = model.predict(
        source=str(image_path),
        task="obb",
        stream=False,
        imgsz=imgsz,
        device=device,
        verbose=False,
        half=half,
        save=False,
        save_txt=False,
        save_conf=False,
        max_det=50,
    )[0]

    pred: List[Tuple[int, np.ndarray]] = []
    if res.obb is None or len(res.obb) == 0:
        return pred

    obb = res.obb.cpu().numpy()
    polys = obb.xyxyxyxy  # (N, 4, 2) pixels
    cls = obb.cls
    for i in range(len(polys)):
        pred.append((int(cls[i]), polys[i].astype(np.float32)))
    return pred


def visualize_bad_ids(
    *,
    task: str,
    model_path: Path,
    bad_ids_path: Path,
    original_dataset: Path,
    output_dir: Path,
    device: Optional[str] = "0",
    imgsz: int = 960,
    half: bool = False,
    limit: int = 0,
) -> int:
    if task not in {"detect", "obb"}:
        raise ValueError(f"task must be 'detect' or 'obb', got: {task}")

    if not bad_ids_path.exists():
        raise FileNotFoundError(f"bad_ids not found: {bad_ids_path}")
    if not original_dataset.exists():
        raise FileNotFoundError(f"original_dataset not found: {original_dataset}")

    output_dir.mkdir(parents=True, exist_ok=True)

    device = None if (device is None or str(device).strip() == "") else str(device)
    model = YOLO(str(model_path))

    current_group: Optional[str] = None
    current_index: Dict[str, Path] = {}

    total = 0
    saved = 0
    missing = 0

    for group_id, inner_id in _iter_bad_ids(bad_ids_path):
        total += 1
        if limit and total > limit:
            break

        if current_group != group_id:
            current_group = group_id
            paths = _resolve_group_paths(original_dataset, group_id)
            current_index = _build_inner_id_index(paths.images_dir)

        img_path = current_index.get(inner_id)
        if img_path is None:
            missing += 1
            continue

        img = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
        if img is None:
            missing += 1
            continue

        h, w = img.shape[:2]
        paths = _resolve_group_paths(original_dataset, group_id)

        if task == "detect":
            gt = _read_detect_gt(paths.labels_detect_dir / f"{img_path.stem}.txt", w=w, h=h)
            pred = _predict_detect(model, img_path, device=device, imgsz=imgsz, half=half)
            vis = img.copy()
            _draw_detect_boxes(vis, gt, (0, 255, 0))
            _draw_detect_boxes(vis, pred, (0, 0, 255))
        else:
            gt = _read_obb_gt(paths.labels_obb_dir / f"{img_path.stem}.txt", w=w, h=h)
            pred = _predict_obb(model, img_path, device=device, imgsz=imgsz, half=half)
            vis = img.copy()
            _draw_obb_polys(vis, gt, (0, 255, 0))
            _draw_obb_polys(vis, pred, (0, 0, 255))

        # put a header
        cv2.putText(
            vis,
            f"{group_id}_{inner_id}  task={task}  GT(green) Pred(red)",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            3,
            cv2.LINE_AA,
        )

        out_group_dir = output_dir / group_id
        out_group_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_group_dir / f"{img_path.stem}_viz.jpg"
        ok = cv2.imwrite(str(out_path), vis)
        if ok:
            saved += 1

        if total % 50 == 0:
            print(f"processed={total} saved={saved} missing={missing}", flush=True)

    print(f"Done. processed={total} saved={saved} missing={missing} output_dir={output_dir}")
    return 0


if __name__ == "__main__":
    HERE = Path(__file__).resolve().parent


    TASK = "obb"  # "detect" or "obb"
    MODEL_PATH = HERE / ("detect.pt" if TASK == "detect" else "obb.pt")
    BAD_IDS_PATH = HERE / ("detect_bad_ids.txt" if TASK == "detect" else "obb_bad_ids.txt")
    ORIGINAL_DATASET_DIR = HERE / "original_dataset"
    OUTPUT_DIR = HERE / ("viz_detect" if TASK == "detect" else "viz_obb")

    DEVICE = "0"  # e.g. "0" or "cpu". Use "" to auto-select.
    IMGSZ = 640
    HALF = True  # GPU only; set False for CPU
    LIMIT = 0  # 0 means no limit

    raise SystemExit(
        visualize_bad_ids(
            task=TASK,
            model_path=MODEL_PATH,
            bad_ids_path=BAD_IDS_PATH,
            original_dataset=ORIGINAL_DATASET_DIR,
            output_dir=OUTPUT_DIR,
            device=DEVICE,
            imgsz=IMGSZ,
            half=HALF,
            limit=LIMIT,
        )
    )
