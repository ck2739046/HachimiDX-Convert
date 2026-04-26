import numpy as np


def iou_batch(bboxes1: np.ndarray, bboxes2: np.ndarray) -> np.ndarray:
    """Compute pairwise IoU for boxes in [x1, y1, x2, y2, ...] format."""
    bboxes1 = np.asarray(bboxes1)
    bboxes2 = np.asarray(bboxes2)

    if bboxes1.size == 0 or bboxes2.size == 0:
        return np.zeros((len(bboxes1), len(bboxes2)), dtype=np.float64)

    bboxes2 = np.expand_dims(bboxes2, 0)
    bboxes1 = np.expand_dims(bboxes1, 1)

    xx1 = np.maximum(bboxes1[..., 0], bboxes2[..., 0])
    yy1 = np.maximum(bboxes1[..., 1], bboxes2[..., 1])
    xx2 = np.minimum(bboxes1[..., 2], bboxes2[..., 2])
    yy2 = np.minimum(bboxes1[..., 3], bboxes2[..., 3])

    w = np.maximum(0.0, xx2 - xx1)
    h = np.maximum(0.0, yy2 - yy1)
    wh = w * h

    union = (
        (bboxes1[..., 2] - bboxes1[..., 0]) * (bboxes1[..., 3] - bboxes1[..., 1])
        + (bboxes2[..., 2] - bboxes2[..., 0]) * (bboxes2[..., 3] - bboxes2[..., 1])
        - wh
    )
    return wh / np.maximum(union, 1e-12)


def diou_batch(bboxes1: np.ndarray, bboxes2: np.ndarray) -> np.ndarray:
    """Compute pairwise DIoU (Distance-IoU) for boxes in [x1, y1, x2, y2, ...] format.

    DIoU = IoU - ρ²(b_d, b_t) / c², rescaled from [-1, 1] to [0, 1].

    当 IoU=0 时，中心距离 ρ 提供梯度，优先匹配距离较近的框。
    Ref: https://arxiv.org/abs/1902.09630
    """
    bboxes1 = np.asarray(bboxes1)
    bboxes2 = np.asarray(bboxes2)

    if bboxes1.size == 0 or bboxes2.size == 0:
        return np.zeros((len(bboxes1), len(bboxes2)), dtype=np.float64)

    bboxes2 = np.expand_dims(bboxes2, 0)
    bboxes1 = np.expand_dims(bboxes1, 1)

    # --- IoU part ---
    xx1 = np.maximum(bboxes1[..., 0], bboxes2[..., 0])
    yy1 = np.maximum(bboxes1[..., 1], bboxes2[..., 1])
    xx2 = np.minimum(bboxes1[..., 2], bboxes2[..., 2])
    yy2 = np.minimum(bboxes1[..., 3], bboxes2[..., 3])
    w = np.maximum(0.0, xx2 - xx1)
    h = np.maximum(0.0, yy2 - yy1)
    wh = w * h
    union = (
        (bboxes1[..., 2] - bboxes1[..., 0]) * (bboxes1[..., 3] - bboxes1[..., 1])
        + (bboxes2[..., 2] - bboxes2[..., 0]) * (bboxes2[..., 3] - bboxes2[..., 1])
        - wh
    )
    iou = wh / np.maximum(union, 1e-12)

    # --- Center distance part ---
    cx1 = (bboxes1[..., 0] + bboxes1[..., 2]) / 2.0
    cy1 = (bboxes1[..., 1] + bboxes1[..., 3]) / 2.0
    cx2 = (bboxes2[..., 0] + bboxes2[..., 2]) / 2.0
    cy2 = (bboxes2[..., 1] + bboxes2[..., 3]) / 2.0
    inner_diag = (cx1 - cx2) ** 2 + (cy1 - cy2) ** 2

    # --- Outer enclosing box diagonal ---
    xxc1 = np.minimum(bboxes1[..., 0], bboxes2[..., 0])
    yyc1 = np.minimum(bboxes1[..., 1], bboxes2[..., 1])
    xxc2 = np.maximum(bboxes1[..., 2], bboxes2[..., 2])
    yyc2 = np.maximum(bboxes1[..., 3], bboxes2[..., 3])
    outer_diag = (xxc2 - xxc1) ** 2 + (yyc2 - yyc1) ** 2 + 1e-12

    diou = iou - inner_diag / outer_diag
    return (diou + 1.0) / 2.0  # rescale [-1, 1] → [0, 1]


def speed_direction_batch(dets: np.ndarray, tracks: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    tracks = tracks[..., np.newaxis]
    cx1 = (dets[:, 0] + dets[:, 2]) / 2.0
    cy1 = (dets[:, 1] + dets[:, 3]) / 2.0
    cx2 = (tracks[:, 0] + tracks[:, 2]) / 2.0
    cy2 = (tracks[:, 1] + tracks[:, 3]) / 2.0

    dx = cx1 - cx2
    dy = cy1 - cy2
    norm = np.sqrt(dx ** 2 + dy ** 2) + 1e-6

    dx = dx / norm
    dy = dy / norm
    return dy, dx


def linear_assignment(cost_matrix: np.ndarray) -> np.ndarray:
    try:
        import lap

        _, x, y = lap.lapjv(cost_matrix, extend_cost=True)
        return np.array([[y[i], i] for i in x if i >= 0], dtype=int)
    except ImportError:
        from scipy.optimize import linear_sum_assignment

        x, y = linear_sum_assignment(cost_matrix)
        return np.array(list(zip(x, y)), dtype=int)


def _split_matches(
    matched_indices: np.ndarray,
    num_dets: int,
    num_trks: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """将 Hungarian 配对结果拆分为 matched / unmatched_dets / unmatched_trks。

    不按 IoU 硬门控过滤，完全信任代价矩阵 + Hungarian 的全局最优解。
    """
    if matched_indices.shape[0] > 0:
        unmatched_dets = np.setdiff1d(np.arange(num_dets), matched_indices[:, 0])
        unmatched_trks = np.setdiff1d(np.arange(num_trks), matched_indices[:, 1])
        matches = matched_indices
    else:
        unmatched_dets = np.arange(num_dets)
        unmatched_trks = np.arange(num_trks)
        matches = np.empty((0, 2), dtype=int)

    return matches, unmatched_dets.astype(int), unmatched_trks.astype(int)


def center_distance_gate(
    matched_indices: np.ndarray,
    det_boxes: np.ndarray,
    trk_boxes: np.ndarray,
    trk_last_boxes: np.ndarray,
    max_ratio: float = 2.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """过滤中心距离超过 max_ratio × 轨迹最后观测框 max(w,h) 的匹配。

    返回 (good_matches, rejected_det_indices, rejected_trk_indices)。
    rejected 索引会被加入 unmatched 集合。
    """
    if matched_indices.shape[0] == 0:
        return matched_indices, np.array([], dtype=int), np.array([], dtype=int)

    det_idx = matched_indices[:, 0]
    trk_idx = matched_indices[:, 1]

    det_cx = (det_boxes[det_idx, 0] + det_boxes[det_idx, 2]) / 2.0
    det_cy = (det_boxes[det_idx, 1] + det_boxes[det_idx, 3]) / 2.0
    trk_cx = (trk_boxes[trk_idx, 0] + trk_boxes[trk_idx, 2]) / 2.0
    trk_cy = (trk_boxes[trk_idx, 1] + trk_boxes[trk_idx, 3]) / 2.0
    center_dist = np.sqrt((det_cx - trk_cx) ** 2 + (det_cy - trk_cy) ** 2)

    trk_w = trk_last_boxes[trk_idx, 2] - trk_last_boxes[trk_idx, 0]
    trk_h = trk_last_boxes[trk_idx, 3] - trk_last_boxes[trk_idx, 1]
    max_side = np.maximum(trk_w, trk_h)

    # max_side ≤ 0 表示新轨迹尚无有效观测（last_observation 为占位值 [-1,-1,-1,-1,-1]），不设限
    ok = (max_side <= 0.0) | (center_dist <= max_ratio * max_side)
    return matched_indices[ok], matched_indices[~ok, 0], matched_indices[~ok, 1]


def associate(
    detections: np.ndarray,
    trackers: np.ndarray,
    iou_threshold: float,
    velocities: np.ndarray,
    previous_obs: np.ndarray,
    vdc_weight: float,
    trk_last_boxes: np.ndarray | None = None,
    max_ratio: float = 2.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if len(trackers) == 0:
        return np.empty((0, 2), dtype=int), np.arange(len(detections)), np.empty((0,), dtype=int)

    if len(detections) == 0:
        return np.empty((0, 2), dtype=int), np.empty((0,), dtype=int), np.arange(len(trackers))

    y_speed, x_speed = speed_direction_batch(detections, previous_obs)

    inertia_y = velocities[:, 0][:, np.newaxis]
    inertia_x = velocities[:, 1][:, np.newaxis]

    diff_angle_cos = inertia_x * x_speed + inertia_y * y_speed
    diff_angle_cos = np.clip(diff_angle_cos, a_min=-1.0, a_max=1.0)
    diff_angle = np.arccos(diff_angle_cos)
    diff_angle = (np.pi / 2.0 - np.abs(diff_angle)) / np.pi

    valid_mask = np.ones(previous_obs.shape[0])
    valid_mask[previous_obs[:, 4] < 0] = 0

    diou_matrix = diou_batch(detections, trackers)
    scores = detections[:, -1][:, np.newaxis]
    valid_mask = valid_mask[:, np.newaxis]

    angle_diff_cost = (valid_mask * diff_angle) * vdc_weight
    angle_diff_cost = angle_diff_cost.T
    angle_diff_cost = angle_diff_cost * scores

    if min(diou_matrix.shape) > 0:
        # DIoU + VDC 联合代价，IoU=0 时中心距离提供梯度，优先选较近匹配
        matched_indices = linear_assignment(-(diou_matrix + angle_diff_cost))
    else:
        matched_indices = np.empty((0, 2), dtype=int)

    # 中心距离硬门控：过滤距离超过 max_ratio × 轨迹最后框 max(w,h) 的匹配
    if trk_last_boxes is not None and matched_indices.shape[0] > 0:
        matched_indices, _, _ = center_distance_gate(
            matched_indices, detections, trackers, trk_last_boxes,
            max_ratio=max_ratio,
        )

    return _split_matches(matched_indices, len(detections), len(trackers))
