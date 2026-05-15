from __future__ import annotations

import numpy as np
from filterpy.kalman import KalmanFilter


# ============================================================================
# 辅助函数 — 参考原版 OC-SORT (https://github.com/noahcao/OC_SORT)
# ============================================================================

def convert_bbox_to_z(bbox: np.ndarray) -> np.ndarray:
    """Takes a bounding box in the form [x1,y1,x2,y2] and returns z in the form
    [x,y,s,r] where x,y is the centre, s is scale/area and r is aspect ratio."""
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = bbox[0] + w / 2.0
    y = bbox[1] + h / 2.0
    s = w * h
    r = w / float(h + 1e-6)
    return np.array([x, y, s, r], dtype=np.float64).reshape((4, 1))


def convert_x_to_bbox(x: np.ndarray) -> np.ndarray:
    """Takes a state [x,y,s,r] and returns [x1,y1,x2,y2]."""
    w = np.sqrt(x[2] * x[3])
    h = x[2] / (w + 1e-6)
    return np.array(
        [x[0] - w / 2.0, x[1] - h / 2.0, x[0] + w / 2.0, x[1] + h / 2.0],
        dtype=np.float64,
    ).reshape((1, 4))


def k_previous_obs(
    observations: dict[int, np.ndarray], cur_age: int, k: int
) -> np.ndarray:
    """Return the observation from k steps ago, or the oldest if none."""
    if len(observations) == 0:
        return np.array([-1.0, -1.0, -1.0, -1.0, -1.0], dtype=np.float64)
    for i in range(k):
        dt = k - i
        if cur_age - dt in observations:
            return observations[cur_age - dt]
    max_age = max(observations.keys())
    return observations[max_age]


def speed_direction(bbox1: np.ndarray, bbox2: np.ndarray) -> np.ndarray:
    """Unit speed direction from bbox1 to bbox2, as (dy, dx)."""
    cx1 = (bbox1[0] + bbox1[2]) / 2.0
    cy1 = (bbox1[1] + bbox1[3]) / 2.0
    cx2 = (bbox2[0] + bbox2[2]) / 2.0
    cy2 = (bbox2[1] + bbox2[3]) / 2.0
    speed = np.array([cy2 - cy1, cx2 - cx1], dtype=np.float64)
    norm = np.sqrt((cy2 - cy1) ** 2 + (cx2 - cx1) ** 2) + 1e-6
    return speed / norm


# ============================================================================
# 10 维恒加速 (CA) KalmanBoxTracker10D
# ============================================================================

class KalmanBoxTracker10D:
    """10 维恒加速 Kalman: [cx,cy,s,r, vx,vy,vs, ax,ay,as].
    观测: [cx,cy,s,r] (4 维)."""

    count = 0

    # 状态转移矩阵 F (10×10, dt=1)
    _F = np.eye(10, dtype=np.float64)
    # pos += velocity
    _F[0, 4] = 1.0  # cx += vx
    _F[1, 5] = 1.0  # cy += vy
    _F[2, 6] = 1.0  # s  += vs
    # pos += 0.5 * acceleration
    _F[0, 7] = 0.5  # cx += 0.5*ax
    _F[1, 8] = 0.5  # cy += 0.5*ay
    _F[2, 9] = 0.5  # s  += 0.5*as
    # velocity += acceleration
    _F[4, 7] = 1.0  # vx += ax
    _F[5, 8] = 1.0  # vy += ay
    _F[6, 9] = 1.0  # vs += as

    # 观测矩阵 H (4×10): 直读前 4 维
    _H = np.hstack([np.eye(4, dtype=np.float64), np.zeros((4, 6), dtype=np.float64)])

    def __init__(self, bbox: np.ndarray, delta_t: int = 3):
        self.kf = KalmanFilter(dim_x=10, dim_z=4)
        self.kf.F = KalmanBoxTracker10D._F.copy()
        self.kf.H = KalmanBoxTracker10D._H.copy()

        # 观测噪声 R — 位置低噪声，尺度和纵横比高噪声
        self.kf.R[2:, 2:] *= 10.0

        # 初始状态协方差 P
        # 速度完全未知
        self.kf.P[4:7, 4:7] *= 1000.0
        # 加速度中等不确定
        self.kf.P[7:10, 7:10] *= 100.0
        self.kf.P *= 10.0

        # 过程噪声 Q（小值 — 后续调参）
        self.kf.Q[6, 6] *= 0.01    # vs
        self.kf.Q[4:7, 4:7] *= 0.01   # vx,vy,vs
        self.kf.Q[7:10, 7:10] *= 0.001  # ax,ay,as（加速度应更稳定）

        self.kf.x[:4] = convert_bbox_to_z(bbox[:4])

        self.time_since_update = 0
        self.id = KalmanBoxTracker10D.count
        KalmanBoxTracker10D.count += 1

        self.hit_streak = 0
        self.age = 0

        self.last_observation = np.array(
            [-1.0, -1.0, -1.0, -1.0, -1.0], dtype=np.float64
        )
        self.observations: dict[int, np.ndarray] = {}
        self.history_observations: list[np.ndarray] = []
        self.velocity: np.ndarray | None = None
        self.delta_t = delta_t

        # --- freeze/unfreeze 状态机（原版 OC-SORT 在线平滑） ---
        self._history_obs_z: list[np.ndarray | None] = [
            convert_bbox_to_z(bbox[:4])
        ]  # z-format 观测历史（含 None 表示缺失帧）
        self._observed: bool = True  # 是否有有效观测
        self._frozen_state: dict | None = None  # freeze 时保存的 KF 快照

        self.score = float(bbox[4]) if len(bbox) > 4 else 0.0
        self.cls = int(bbox[5]) if len(bbox) > 5 else 0
        self.idx = int(bbox[6]) if len(bbox) > 6 else -1
        self.history_scores: list[float] = [self.score]
        self.history_classes: list[int] = [self.cls]
        self.history_indices: list[int] = [self.idx]

    def update(self, bbox: np.ndarray | None) -> None:
        # ====== 记录 z-format 观测（原版 KalmanFilterNew.history_obs） ======
        if bbox is not None:
            self._history_obs_z.append(convert_bbox_to_z(bbox[:4]))
        else:
            self._history_obs_z.append(None)

        # ====== freeze / unfreeze 状态机（原版 OC-SORT 在线平滑） ======
        if bbox is None:
            if self._observed:
                self._freeze_kf()
            self._observed = False
            return

        # bbox is not None
        if not self._observed:
            self._unfreeze_kf()
        # unfreeze 内部已将 _observed 置 True

        # ====== 正常 tracker 级更新 ======
        bbox = np.asarray(bbox, dtype=np.float64)
        obs = np.array(
            [bbox[0], bbox[1], bbox[2], bbox[3], bbox[4]], dtype=np.float64
        )

        if self.last_observation.sum() >= 0:
            previous_box = None
            for i in range(self.delta_t):
                dt = self.delta_t - i
                if self.age - dt in self.observations:
                    previous_box = self.observations[self.age - dt]
                    break
            if previous_box is None:
                previous_box = self.last_observation
            self.velocity = speed_direction(previous_box, obs)

        self.last_observation = obs
        self.observations[self.age] = obs
        self.history_observations.append(obs)

        self.time_since_update = 0
        self.hit_streak += 1

        self.kf.update(convert_bbox_to_z(obs[:4]))

        self.score = float(bbox[4]) if len(bbox) > 4 else self.score
        self.cls = int(bbox[5]) if len(bbox) > 5 else self.cls
        self.idx = int(bbox[6]) if len(bbox) > 6 else self.idx
        self.history_scores.append(self.score)
        self.history_classes.append(self.cls)
        self.history_indices.append(self.idx)

    # ========================================================================
    # freeze / unfreeze — 原版 OC-SORT 在线平滑 (Observation-Centric Re-Update)
    # 适配标准 filterpy.kalman.KalmanFilter
    # ========================================================================

    def _freeze_kf(self) -> None:
        """第一个 update(None) 时保存全部 KF 状态以备后续恢复。"""
        self._frozen_state = {
            'x': self.kf.x.copy(),
            'P': self.kf.P.copy(),
            'K': self.kf.K.copy(),
            '_alpha_sq': self.kf._alpha_sq,
            '_history_obs_z': list(self._history_obs_z),
        }

    def _unfreeze_kf(self) -> None:
        """gap 后第一个真实观测到来时：恢复冻结状态 + 虚拟轨迹填充 gap。"""
        if self._frozen_state is None:
            self._observed = True
            return

        # 1. 快照当前 history（含刚 append 的 z_real）
        new_history = list(self._history_obs_z)

        # 2. 恢复冻结时的 KF 内部状态
        fs = self._frozen_state
        self.kf.x = fs['x'].copy()
        self.kf.P = fs['P'].copy()
        self.kf.K = fs['K'].copy()
        self.kf._alpha_sq = fs['_alpha_sq']
        self._frozen_state = None

        # 3. 恢复冻结时的 history，并去掉最后一项（该帧观测已在原版 update(None) 时不写入 KF）
        self._history_obs_z = list(fs['_history_obs_z'])
        self._history_obs_z = self._history_obs_z[:-1]

        # 4. 找 new_history 最后两个非 None 项用于线性插值
        non_none_indices = [
            i for i, z in enumerate(new_history) if z is not None
        ]
        if len(non_none_indices) < 2:
            self._observed = True
            return  # 不够两个非 None → 无法插值

        i1, i2 = non_none_indices[-2], non_none_indices[-1]
        gap = i2 - i1
        if gap <= 1:
            self._observed = True
            return  # 无 gap

        # 5. 线性插值 + predict-update 循环填充 gap（原版恒速假设）
        box1 = new_history[i1].flatten()  # [cx,cy,s,r]
        box2 = new_history[i2].flatten()
        x1, y1, s1, r1 = box1
        w1 = np.sqrt(max(s1 * r1, 1e-12))
        h1 = s1 / (w1 + 1e-6)
        x2, y2, s2, r2 = box2
        w2 = np.sqrt(max(s2 * r2, 1e-12))
        h2 = s2 / (w2 + 1e-6)
        dx = (x2 - x1) / gap
        dy = (y2 - y1) / gap
        dw = (w2 - w1) / gap
        dh = (h2 - h1) / gap

        for j in range(1, gap):  # gap-1 个虚拟帧
            x = x1 + j * dx
            y = y1 + j * dy
            w = w1 + j * dw
            h = h1 + j * dh
            s = w * h
            r = w / float(h + 1e-6)
            z_virtual = np.array([x, y, s, r], dtype=np.float64).reshape((4, 1))
            self._history_obs_z.append(z_virtual)
            self.kf.update(z_virtual)
            self.kf.predict()

        # 追加真实观测（恢复 frozen 状态时被覆盖了）
        self._history_obs_z.append(new_history[i2])

        self._observed = True

    def predict(self) -> np.ndarray:
        if (self.kf.x[6] + self.kf.x[2]) <= 0:
            self.kf.x[6] *= 0.0

        self.kf.predict()
        self.age += 1

        if self.time_since_update > 0:
            self.hit_streak = 0
        self.time_since_update += 1

        return convert_x_to_bbox(self.kf.x)

    def get_state(self) -> np.ndarray:
        return convert_x_to_bbox(self.kf.x)


# 导出别名，兼容 export_track_video.py
_KalmanBoxTracker = KalmanBoxTracker10D


# ============================================================================
# 关联匹配函数 — 源自原版 OC-SORT association.py (Stage 1 仅 VDC+DIoU)
# ============================================================================

def diou_batch(bboxes1: np.ndarray, bboxes2: np.ndarray) -> np.ndarray:
    """Compute DIoU between two sets of bboxes in [x1,y1,x2,y2] form.

    DIoU = IoU - center_distance² / enclosing_diag², rescaled to (0,1).
    Ref: https://arxiv.org/abs/1911.08287
    """
    bboxes2 = np.expand_dims(bboxes2, 0)
    bboxes1 = np.expand_dims(bboxes1, 1)

    # intersection
    xx1 = np.maximum(bboxes1[..., 0], bboxes2[..., 0])
    yy1 = np.maximum(bboxes1[..., 1], bboxes2[..., 1])
    xx2 = np.minimum(bboxes1[..., 2], bboxes2[..., 2])
    yy2 = np.minimum(bboxes1[..., 3], bboxes2[..., 3])
    w = np.maximum(0.0, xx2 - xx1)
    h = np.maximum(0.0, yy2 - yy1)
    wh = w * h
    area1 = (bboxes1[..., 2] - bboxes1[..., 0]) * (bboxes1[..., 3] - bboxes1[..., 1])
    area2 = (bboxes2[..., 2] - bboxes2[..., 0]) * (bboxes2[..., 3] - bboxes2[..., 1])
    union = area1 + area2 - wh
    iou = wh / union

    # center distance
    centerx1 = (bboxes1[..., 0] + bboxes1[..., 2]) / 2.0
    centery1 = (bboxes1[..., 1] + bboxes1[..., 3]) / 2.0
    centerx2 = (bboxes2[..., 0] + bboxes2[..., 2]) / 2.0
    centery2 = (bboxes2[..., 1] + bboxes2[..., 3]) / 2.0
    inner_diag = (centerx1 - centerx2) ** 2 + (centery1 - centery2) ** 2

    # enclosing box diagonal
    xxc1 = np.minimum(bboxes1[..., 0], bboxes2[..., 0])
    yyc1 = np.minimum(bboxes1[..., 1], bboxes2[..., 1])
    xxc2 = np.maximum(bboxes1[..., 2], bboxes2[..., 2])
    yyc2 = np.maximum(bboxes1[..., 3], bboxes2[..., 3])
    outer_diag = (xxc2 - xxc1) ** 2 + (yyc2 - yyc1) ** 2

    diou = iou - inner_diag / (outer_diag + 1e-6)
    return (diou + 1.0) / 2.0  # rescale from (-1,1) to (0,1)


def speed_direction_batch(
    dets: np.ndarray, tracks: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Batch speed direction: dets (N,4) vs tracks (M,5) → (dy, dx) of shape (M,N)."""
    tracks = tracks[..., np.newaxis]  # (M,5,1)
    cx1 = (dets[:, 0] + dets[:, 2]) / 2.0
    cy1 = (dets[:, 1] + dets[:, 3]) / 2.0
    cx2 = (tracks[:, 0, :] + tracks[:, 2, :]) / 2.0
    cy2 = (tracks[:, 1, :] + tracks[:, 3, :]) / 2.0
    dx = cx1 - cx2
    dy = cy1 - cy2
    norm = np.sqrt(dx ** 2 + dy ** 2) + 1e-6
    dx = dx / norm
    dy = dy / norm
    return dy, dx  # (M,N) each


def linear_assignment(cost_matrix: np.ndarray) -> np.ndarray:
    """Hungarian algorithm on cost_matrix; prefers `lap` if available."""
    try:
        import lap  # type: ignore

        _, x, y = lap.lapjv(cost_matrix, extend_cost=True)
        return np.array([[y[i], i] for i in x if i >= 0])
    except ImportError:
        from scipy.optimize import linear_sum_assignment

        x, y = linear_sum_assignment(cost_matrix)
        return np.array(list(zip(x, y)))


def associate(
    detections: np.ndarray,
    trackers: np.ndarray,
    iou_threshold: float,
    velocities: np.ndarray,
    previous_obs: np.ndarray,
    vdc_weight: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Stage 1: VDC + DIoU joint association.

    Args:
        detections: (N,5) [x1,y1,x2,y2,score]
        trackers: (M,5) predicted bboxes
        iou_threshold: minimum DIoU for a valid match
        velocities: (M,2) tracker velocity (dy,dx)
        previous_obs: (M,5) k_previous_obs for each tracker
        vdc_weight: inertia weight for velocity direction consistency

    Returns:
        matches: (K,2) [det_idx, trk_idx]
        unmatched_detections: (U,) indices
        unmatched_trackers: (V,) indices
    """
    if len(trackers) == 0:
        return (
            np.empty((0, 2), dtype=int),
            np.arange(len(detections)),
            np.empty((0, 5), dtype=int),
        )

    # 速度方向一致性代价
    Y, X = speed_direction_batch(detections, previous_obs)  # (M,N)
    inertia_Y, inertia_X = velocities[:, 0], velocities[:, 1]  # (M,)
    inertia_Y = inertia_Y[:, np.newaxis]
    inertia_X = inertia_X[:, np.newaxis]
    diff_angle_cos = inertia_X * X + inertia_Y * Y
    diff_angle_cos = np.clip(diff_angle_cos, a_min=-1, a_max=1)
    diff_angle = np.arccos(diff_angle_cos)
    diff_angle = (np.pi / 2.0 - np.abs(diff_angle)) / np.pi  # ∈ [-0.5, 0.5]

    valid_mask = np.ones(previous_obs.shape[0])
    valid_mask[previous_obs[:, 4] < 0] = 0  # 轨迹无有效观测 → 跳过 VDC

    diou_matrix = diou_batch(detections, trackers)
    scores = detections[:, -1][:, np.newaxis]        # (N,1)
    valid_mask = valid_mask[:, np.newaxis]            # (M,1)

    angle_diff_cost = (valid_mask * diff_angle) * vdc_weight  # (M,N)
    angle_diff_cost = angle_diff_cost.T * scores               # (N,M)

    # 一次性匹配
    if min(diou_matrix.shape) > 0:
        a = (diou_matrix > iou_threshold).astype(np.int32)
        if a.sum(1).max() == 1 and a.sum(0).max() == 1:
            matched_indices = np.stack(np.where(a), axis=1)
        else:
            matched_indices = linear_assignment(-(diou_matrix + angle_diff_cost))
    else:
        matched_indices = np.empty(shape=(0, 2))

    # 过滤低 DIoU 匹配
    if matched_indices.shape[0] > 0:
        unmatched_detections = np.setdiff1d(
            np.arange(len(detections)), matched_indices[:, 0]
        )
        unmatched_trackers = np.setdiff1d(
            np.arange(len(trackers)), matched_indices[:, 1]
        )
        diou_vals = diou_matrix[matched_indices[:, 0], matched_indices[:, 1]]
        low_diou_mask = diou_vals < iou_threshold
        unmatched_detections = np.concatenate(
            [unmatched_detections, matched_indices[low_diou_mask, 0]]
        )
        unmatched_trackers = np.concatenate(
            [unmatched_trackers, matched_indices[low_diou_mask, 1]]
        )
        matches = matched_indices[~low_diou_mask]
    else:
        unmatched_detections = np.arange(len(detections))
        unmatched_trackers = np.arange(len(trackers))
        matches = np.empty((0, 2), dtype=int)

    return matches, unmatched_detections.astype(int), unmatched_trackers.astype(int)


# ============================================================================
# 精简 OCSort — 仅 Stage 1 (VDC + DIoU)
# ============================================================================

class OCSort:
    def __init__(
        self,
        det_thresh: float,
        max_age: int = 30,
        min_hits: int = 3,
        iou_threshold: float = 0.3,
        delta_t: int = 3,
        inertia: float = 0.2,
    ):
        self.max_age = int(max_age)
        self.min_hits = int(min_hits)
        self.iou_threshold = float(iou_threshold)
        self.trackers: list[KalmanBoxTracker10D] = []
        self.frame_count = 0
        self.det_thresh = float(det_thresh)
        self.delta_t = int(delta_t)
        self.inertia = float(inertia)
        KalmanBoxTracker10D.count = 0

    @staticmethod
    def _to_obb_track_row(
        xyxy: np.ndarray,
        track_id: int,
        score: float,
        cls_id: int,
        idx: int,
        frame_offset: int = 0,
    ) -> np.ndarray:
        """Convert xyxy bbox → track.py 需要的 10 列格式."""
        x1, y1, x2, y2 = xyxy
        w = x2 - x1
        h = y2 - y1
        cx = x1 + w / 2.0
        cy = y1 + h / 2.0
        return np.array(
            [cx, cy, w, h, 0.0, track_id, score, cls_id, idx, frame_offset],
            dtype=np.float32,
        )

    def update(self, dets_all: np.ndarray | None) -> np.ndarray:
        """Stage-1-only update.

        Args:
            dets_all: (N,7) or (N,6) [x1,y1,x2,y2,score,cls,idx?]
        Returns:
            (M,10) [cx,cy,w,h,r,track_id,score,cls,idx,frame_offset]
        """
        if dets_all is None:
            dets_all = np.empty((0, 7), dtype=np.float64)

        if len(dets_all) == 0:
            dets_all = np.empty((0, 7), dtype=np.float64)
        else:
            dets_all = np.asarray(dets_all, dtype=np.float64)

        self.frame_count += 1

        # 高分框筛选
        scores = dets_all[:, 4] if len(dets_all) else np.empty((0,), dtype=np.float64)
        remain_inds = scores > self.det_thresh
        dets = dets_all[remain_inds]

        # ====== predict ======
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

        # ====== 轨迹速度和 k 步前观测 ======
        _zero_vel = np.array((0.0, 0.0), dtype=np.float64)
        velocities = np.array(
            [
                trk.velocity if trk.velocity is not None else _zero_vel
                for trk in self.trackers
            ]
        )
        k_observations = np.array(
            [
                k_previous_obs(trk.observations, trk.age, self.delta_t)
                for trk in self.trackers
            ]
        )

        # ====== Stage 1: VDC + IoU ======
        if len(dets) > 0 and len(trks) > 0:
            matched, unmatched_dets, unmatched_trks = associate(
                dets[:, :5],
                trks,
                self.iou_threshold,
                velocities,
                k_observations,
                self.inertia,
            )
        else:
            matched = np.empty((0, 2), dtype=int)
            unmatched_dets = np.arange(len(dets))
            unmatched_trks = np.arange(len(self.trackers))

        # ====== 更新 ======
        for m in matched:
            det_idx, trk_idx = m[0], m[1]
            self.trackers[trk_idx].update(dets[det_idx])

        for trk_idx in unmatched_trks:
            self.trackers[trk_idx].update(None)

        # 新建轨迹
        for det_idx in unmatched_dets:
            self.trackers.append(
                KalmanBoxTracker10D(dets[det_idx], delta_t=self.delta_t)
            )

        # ====== 输出 ======
        ret = []
        i = len(self.trackers)
        for trk in reversed(self.trackers):
            if trk.last_observation.sum() < 0:
                d = trk.get_state()[0]
            else:
                d = trk.last_observation[:4]

            if (trk.time_since_update < 1) and (
                trk.hit_streak >= self.min_hits or self.frame_count <= self.min_hits
            ):
                ret.append(
                    self._to_obb_track_row(
                        d, trk.id + 1, trk.score, trk.cls, trk.idx, frame_offset=0
                    )
                )

                # Head Padding: 轨迹首次达标时补回初始化阶段的历史观测
                if trk.hit_streak == self.min_hits:
                    pad_cnt = min(
                        self.min_hits - 1, len(trk.history_observations) - 1
                    )
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
