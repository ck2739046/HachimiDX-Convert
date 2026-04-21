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


def _filter_matches(
    matched_indices: np.ndarray,
    iou_matrix: np.ndarray,
    iou_threshold: float,
    num_dets: int,
    num_trks: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if matched_indices.shape[0] > 0:
        unmatched_dets = np.setdiff1d(np.arange(num_dets), matched_indices[:, 0])
        unmatched_trks = np.setdiff1d(np.arange(num_trks), matched_indices[:, 1])
        iou_vals = iou_matrix[matched_indices[:, 0], matched_indices[:, 1]]
        low_iou_mask = iou_vals < iou_threshold

        unmatched_dets = np.concatenate([unmatched_dets, matched_indices[low_iou_mask, 0]])
        unmatched_trks = np.concatenate([unmatched_trks, matched_indices[low_iou_mask, 1]])
        matches = matched_indices[~low_iou_mask]
    else:
        unmatched_dets = np.arange(num_dets)
        unmatched_trks = np.arange(num_trks)
        matches = np.empty((0, 2), dtype=int)

    return matches, unmatched_dets.astype(int), unmatched_trks.astype(int)


def associate(
    detections: np.ndarray,
    trackers: np.ndarray,
    iou_threshold: float,
    velocities: np.ndarray,
    previous_obs: np.ndarray,
    vdc_weight: float,
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

    iou_matrix = iou_batch(detections, trackers)
    scores = detections[:, -1][:, np.newaxis]
    valid_mask = valid_mask[:, np.newaxis]

    angle_diff_cost = (valid_mask * diff_angle) * vdc_weight
    angle_diff_cost = angle_diff_cost.T
    angle_diff_cost = angle_diff_cost * scores

    if min(iou_matrix.shape) > 0:
        binary_ok = (iou_matrix > iou_threshold).astype(np.int32)
        if binary_ok.sum(1).max() == 1 and binary_ok.sum(0).max() == 1:
            matched_indices = np.stack(np.where(binary_ok), axis=1)
        else:
            matched_indices = linear_assignment(-(iou_matrix + angle_diff_cost))
    else:
        matched_indices = np.empty((0, 2), dtype=int)

    return _filter_matches(matched_indices, iou_matrix, iou_threshold, len(detections), len(trackers))
