from __future__ import annotations

import numpy as np
from filterpy.kalman import KalmanFilter

from .oc_sort_association import associate, diou_batch, iou_batch, linear_assignment


def _k_previous_obs(observations: dict[int, np.ndarray], cur_age: int, k: int) -> np.ndarray:
    if len(observations) == 0:
        return np.array([-1.0, -1.0, -1.0, -1.0, -1.0], dtype=np.float64)

    for i in range(k):
        dt = k - i
        if cur_age - dt in observations:
            return observations[cur_age - dt]

    max_age = max(observations.keys())
    return observations[max_age]


def _convert_bbox_to_z(bbox: np.ndarray) -> np.ndarray:
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = bbox[0] + w / 2.0
    y = bbox[1] + h / 2.0
    s = w * h
    r = w / float(h + 1e-6)
    return np.array([x, y, s, r], dtype=np.float64).reshape((4, 1))


def _convert_x_to_bbox(x: np.ndarray) -> np.ndarray:
    w = np.sqrt(x[2] * x[3])
    h = x[2] / (w + 1e-6)
    return np.array([x[0] - w / 2.0, x[1] - h / 2.0, x[0] + w / 2.0, x[1] + h / 2.0], dtype=np.float64).reshape((1, 4))


def _speed_direction(bbox1: np.ndarray, bbox2: np.ndarray) -> np.ndarray:
    cx1 = (bbox1[0] + bbox1[2]) / 2.0
    cy1 = (bbox1[1] + bbox1[3]) / 2.0
    cx2 = (bbox2[0] + bbox2[2]) / 2.0
    cy2 = (bbox2[1] + bbox2[3]) / 2.0
    speed = np.array([cy2 - cy1, cx2 - cx1], dtype=np.float64)
    norm = np.sqrt((cy2 - cy1) ** 2 + (cx2 - cx1) ** 2) + 1e-6
    return speed / norm


class _KalmanBoxTracker:
    count = 0

    _F = np.array(
        [
            [1, 0, 0, 0, 1, 0, 0],
            [0, 1, 0, 0, 0, 1, 0],
            [0, 0, 1, 0, 0, 0, 1],
            [0, 0, 0, 1, 0, 0, 0],
            [0, 0, 0, 0, 1, 0, 0],
            [0, 0, 0, 0, 0, 1, 0],
            [0, 0, 0, 0, 0, 0, 1],
        ],
        dtype=np.float64,
    )
    _H = np.array(
        [
            [1, 0, 0, 0, 0, 0, 0],
            [0, 1, 0, 0, 0, 0, 0],
            [0, 0, 1, 0, 0, 0, 0],
            [0, 0, 0, 1, 0, 0, 0],
        ],
        dtype=np.float64,
    )

    def __init__(self, bbox: np.ndarray, delta_t: int = 3):
        self.kf = KalmanFilter(dim_x=7, dim_z=4)
        self.kf.F = _KalmanBoxTracker._F.copy()
        self.kf.H = _KalmanBoxTracker._H.copy()

        self.kf.R[2:, 2:] *= 10.0
        self.kf.P[4:, 4:] *= 1000.0
        self.kf.P *= 10.0
        self.kf.Q[-1, -1] *= 0.01
        self.kf.Q[4:, 4:] *= 0.01

        self.kf.x[:4] = _convert_bbox_to_z(bbox[:4])

        self.time_since_update = 0
        self.id = _KalmanBoxTracker.count
        _KalmanBoxTracker.count += 1

        self.hit_streak = 0
        self.age = 0

        self.last_observation = np.array([-1.0, -1.0, -1.0, -1.0, -1.0], dtype=np.float64)
        self.observations: dict[int, np.ndarray] = {}
        self.history_observations: list[np.ndarray] = []
        self.history_scores: list[float] = []
        self.history_classes: list[int] = []
        self.history_indices: list[int] = []
        self.velocity: np.ndarray | None = None
        self.delta_t = delta_t

        self.score = float(bbox[4]) if len(bbox) > 4 else 0.0
        self.cls = int(bbox[5]) if len(bbox) > 5 else 0
        self.idx = int(bbox[6]) if len(bbox) > 6 else -1

    def update(self, bbox: np.ndarray | None) -> None:
        if bbox is None:
            return

        bbox = np.asarray(bbox, dtype=np.float64)
        obs = np.array([bbox[0], bbox[1], bbox[2], bbox[3], bbox[4]], dtype=np.float64)

        if self.last_observation.sum() >= 0:
            previous_box = None
            for i in range(self.delta_t):
                dt = self.delta_t - i
                if self.age - dt in self.observations:
                    previous_box = self.observations[self.age - dt]
                    break
            if previous_box is None:
                previous_box = self.last_observation
            self.velocity = _speed_direction(previous_box, obs)

        self.last_observation = obs
        self.observations[self.age] = obs
        self.history_observations.append(obs)

        self.time_since_update = 0
        self.hit_streak += 1

        self.kf.update(_convert_bbox_to_z(obs[:4]))

        self.score = float(bbox[4]) if len(bbox) > 4 else self.score
        self.cls = int(bbox[5]) if len(bbox) > 5 else self.cls
        self.idx = int(bbox[6]) if len(bbox) > 6 else self.idx
        self.history_scores.append(self.score)
        self.history_classes.append(self.cls)
        self.history_indices.append(self.idx)

    def predict(self) -> np.ndarray:
        if (self.kf.x[6] + self.kf.x[2]) <= 0:
            self.kf.x[6] *= 0.0

        self.kf.predict()
        self.age += 1

        if self.time_since_update > 0:
            self.hit_streak = 0
        self.time_since_update += 1

        return _convert_x_to_bbox(self.kf.x)

    def get_state(self) -> np.ndarray:
        return _convert_x_to_bbox(self.kf.x)


class OCSort:
    def __init__(
        self,
        det_thresh: float,
        max_age: int = 30,
        min_hits: int = 3,
        iou_threshold: float = 0.3,
        delta_t: int = 3,
        inertia: float = 0.2,
        use_byte: bool = False,
    ):
        self.max_age = int(max_age)
        self.min_hits = int(min_hits)
        self.iou_threshold = float(iou_threshold)
        self.trackers: list[_KalmanBoxTracker] = []
        self.frame_count = 0
        self.det_thresh = float(det_thresh)
        self.delta_t = int(delta_t)
        self.inertia = float(inertia)
        self.use_byte = bool(use_byte)
        self.low_thresh = 0.1

        _KalmanBoxTracker.count = 0

    @staticmethod
    def _to_obb_track_row(
        xyxy: np.ndarray,
        track_id: int,
        score: float,
        cls_id: int,
        idx: int,
        frame_offset: int = 0,
    ) -> np.ndarray:
        # 返回 track.py 需要的格式
        x1, y1, x2, y2 = xyxy
        w = x2 - x1
        h = y2 - y1
        cx = x1 + w / 2.0
        cy = y1 + h / 2.0
        return np.array([cx, cy, w, h, 0.0, track_id, score, cls_id, idx, frame_offset], dtype=np.float32)

    def update(self, output_results: np.ndarray | None) -> np.ndarray:
        if output_results is None:
            output_results = np.empty((0, 7), dtype=np.float64)

        if len(output_results) == 0:
            dets_all = np.empty((0, 7), dtype=np.float64)
        else:
            dets_all = np.asarray(output_results, dtype=np.float64)

        self.frame_count += 1

        scores = dets_all[:, 4] if len(dets_all) else np.empty((0,), dtype=np.float64)
        remain_inds = scores > self.det_thresh
        inds_second = np.logical_and(scores > self.low_thresh, scores < self.det_thresh)

        dets = dets_all[remain_inds]
        dets_second = dets_all[inds_second]
        dets_assoc = dets[:, :5]
        dets_second_assoc = dets_second[:, :5]

        trks = np.zeros((len(self.trackers), 5), dtype=np.float64)
        to_del = []
        for t, trk in enumerate(trks):
            pos = self.trackers[t].predict()[0]
            trk[:] = [pos[0], pos[1], pos[2], pos[3], 0.0]
            if np.any(np.isnan(pos)):
                to_del.append(t)

        trks = np.ma.compress_rows(np.ma.masked_invalid(trks))
        for t in reversed(to_del):
            self.trackers.pop(t)

        if self.trackers:
            zero_vel = np.array((0.0, 0.0), dtype=np.float64)
            velocities = np.array([trk.velocity if trk.velocity is not None else zero_vel for trk in self.trackers])
            last_boxes = np.array([trk.last_observation for trk in self.trackers])
            k_observations = np.array([
                _k_previous_obs(trk.observations, trk.age, self.delta_t) for trk in self.trackers
            ])
        else:
            velocities = np.empty((0, 2), dtype=np.float64)
            last_boxes = np.empty((0, 5), dtype=np.float64)
            k_observations = np.empty((0, 5), dtype=np.float64)

        matched, unmatched_dets, unmatched_trks = associate(
            dets_assoc,
            trks,
            self.iou_threshold,
            velocities,
            k_observations,
            self.inertia,
        )

        for det_idx, trk_idx in matched:
            self.trackers[trk_idx].update(dets[det_idx])

        if self.use_byte and len(dets_second_assoc) > 0 and unmatched_trks.shape[0] > 0:
            u_trks = trks[unmatched_trks]
            diou_left = np.array(diou_batch(dets_second_assoc, u_trks))
            # DIoU 替代 IoU：零交集时中心距离提供梯度，优先选较近匹配
            if diou_left.size > 0 and diou_left.max() > 0:
                matched_indices = linear_assignment(-diou_left)
                to_remove = []
                for det_idx2, trk_pos in matched_indices:
                    trk_idx = unmatched_trks[trk_pos]
                    self.trackers[trk_idx].update(dets_second[det_idx2])
                    to_remove.append(trk_idx)
                if to_remove:
                    unmatched_trks = np.setdiff1d(unmatched_trks, np.array(to_remove, dtype=int))

        if unmatched_dets.shape[0] > 0 and unmatched_trks.shape[0] > 0:
            left_dets = dets_assoc[unmatched_dets]
            left_trks = last_boxes[unmatched_trks]
            diou_left = np.array(diou_batch(left_dets, left_trks))
            # DIoU 替代 IoU：零交集时中心距离提供梯度
            if diou_left.size > 0 and diou_left.max() > 0:
                rematched_indices = linear_assignment(-diou_left)
                to_remove_det_indices = []
                to_remove_trk_indices = []
                for det_pos, trk_pos in rematched_indices:
                    det_idx = unmatched_dets[det_pos]
                    trk_idx = unmatched_trks[trk_pos]
                    self.trackers[trk_idx].update(dets[det_idx])
                    to_remove_det_indices.append(det_idx)
                    to_remove_trk_indices.append(trk_idx)

                if to_remove_det_indices:
                    unmatched_dets = np.setdiff1d(unmatched_dets, np.array(to_remove_det_indices, dtype=int))
                if to_remove_trk_indices:
                    unmatched_trks = np.setdiff1d(unmatched_trks, np.array(to_remove_trk_indices, dtype=int))

        for trk_idx in unmatched_trks:
            self.trackers[trk_idx].update(None)

        for det_idx in unmatched_dets:
            self.trackers.append(_KalmanBoxTracker(dets[det_idx], delta_t=self.delta_t))

        ret = []
        i = len(self.trackers)
        for trk in reversed(self.trackers):
            if trk.last_observation.sum() < 0:
                d = trk.get_state()[0]
            else:
                d = trk.last_observation[:4]

            if (trk.time_since_update < 1) and (trk.hit_streak >= self.min_hits or self.frame_count <= self.min_hits):
                ret.append(self._to_obb_track_row(d, trk.id + 1, trk.score, trk.cls, trk.idx, frame_offset=0))

                # Head Padding: 在轨迹首次达标输出时，补回初始化阶段的历史观测。
                if trk.hit_streak == self.min_hits:
                    pad_cnt = min(self.min_hits - 1, len(trk.history_observations) - 1)
                    for prev_i in range(pad_cnt):
                        hist_pos = -(prev_i + 2)
                        prev_obs = trk.history_observations[hist_pos]
                        prev_score = trk.history_scores[hist_pos]
                        prev_cls = trk.history_classes[hist_pos]
                        prev_idx = trk.history_indices[hist_pos]
                        ret.append(
                            self._to_obb_track_row(
                                prev_obs[:4],
                                trk.id + 1,
                                prev_score,
                                prev_cls,
                                prev_idx,
                                frame_offset=-(prev_i + 1),
                            )
                        )

            i -= 1
            if trk.time_since_update > self.max_age:
                self.trackers.pop(i)

        if len(ret) > 0:
            return np.asarray(ret, dtype=np.float32)
        return np.empty((0, 10), dtype=np.float32)
