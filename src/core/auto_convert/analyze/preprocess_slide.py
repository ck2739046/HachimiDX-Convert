import numpy as np

from ..detect.note_definition import *
from .tool import *
from .shared_context import *


def preprocess_slide_data(shared_context: SharedContext):

    # 此处仅作基础的分类
    # 具体预处理交给底下的函数
    candidate_slide_head_data = {}
    candidate_slide_tail_data = {}

    for key, value in shared_context.track_data.items():

        track_id, note_type = key
        note_geometry_list = value

        if note_type != NoteType.SLIDE: continue
        if len(note_geometry_list) < 10: continue

        # 合法的星星头
        # 1. position一致
        # 2. 距离圆心递增
        # 3. 所有 dist 不在危险区 (judgeline_start * 0.85)

        # 合法的星星尾
        # 1. 开头在A区或者离A区判定点够近
        # 2. 结尾在A区或者离A区判定点够近
        # 离A区判定点够近的定义: note_travel_dist * 0.45
        # 选 45 是为了适配同头或者同尾星星，在A区附近会有重叠
        # 一般在移动了 30% 后才会分开，被识别成两个星星

        # 星星头尾可能是同一个星星轨迹，需要拆分
        # 从头开始到到达第一个A区，算星星头
        # 剩下部分算星星尾




        # 判断所有 pos 是否一致，因为星星尾是从一个A区移动到另一个A区的，所以 pos 一定不一致
        # yes: 可能是星星头，进一步检查，return
        # no:  进一步分类
        oct_positions = [calculate_oct_position(
                         shared_context.std_video_cx,
                         shared_context.std_video_cy,
                         note.cx, note.cy
                        ) for note in note_geometry_list]
        
        if len(set(oct_positions)) == 1:
            candidate_slide_head_data[key] = note_geometry_list
            continue
        
        # 看开头是否在A区或者离A区判定点够近
        # yes: 可能是星星尾，进一步检查，return
        # no: 可能是头+尾，进一步检查
        start_pos = oct_positions[0]
        start_in_a_zone = start_pos.startswith('A') or \
                          _is_close_to_a_zone_endpoint(shared_context,
                                                       note_geometry_list[0].cx,
                                                       note_geometry_list[0].cy)
        if start_in_a_zone:
            candidate_slide_tail_data[key] = note_geometry_list
            continue

        # 是否到达A区
        # yes: 按第一个A区分割，第一段视为星星头，第二段视为星星尾，进一步检查，return
        # no:  可能是异常数据，丢弃, return
        all_postions = [calculate_all_position(
                        shared_context.touch_areas,
                        note.cx, note.cy
                       ) for note in note_geometry_list]
        if any(pos.startswith('A') for pos in all_postions):
            split_idx = next(i for i, pos in enumerate(all_postions) if pos.startswith('A'))
            candidate_slide_head_data[key] = note_geometry_list[:split_idx]
            candidate_slide_tail_data[key] = note_geometry_list[split_idx:]
            continue
        # 没有任何一个点在A区，丢弃
        print(f"preprocess_slide_data: no A zone point for track_id {track_id}, discarding")

    
    # 交给下层函数进行更细致的检查和处理
    slide_head_data = preprocess_slide_head_data(shared_context)
    slide_tail_data = preprocess_slide_tail_data(shared_context)

    return slide_head_data, slide_tail_data






def _is_close_to_a_zone_endpoint(shared_context: SharedContext, cx: int, cy: int) -> bool:
    '''
    判断一个点是否接近A区判定点
    接近的定义: 距离小于 note_travel_dist * 0.45
    '''

    if not shared_context.a_zone_endpoint:
        return False

    for endpoint in shared_context.a_zone_endpoint.values():
        ex, ey = endpoint
        dist = np.sqrt((cx - ex)**2 + (cy - ey)**2)
        if dist < shared_context.note_travel_dist * 0.45:
            # 因为 note_travel_dist * 0.45 * 2 小于两个 A 区判定点之间的距离
            # 所以不可能同时接近两个点，直接返回就行
            return True
        
    return False







def preprocess_slide_head_data(shared_context: SharedContext, candidate_slide_head_data: dict):
    '''
    返回格式:
    dict{
        key: (track_id, note_type, note_variant, note_position),
        value: note path
        [
            {
                'frame': frame_num,
                'dist': dist_to_center
            },
            ...
        ]
    }
    '''

    slide_data = {}

    end_tolerance = shared_context.note_travel_dist * 0.1
    start_tolerance = shared_context.note_travel_dist * 0.1
    valid_judgeline_start = shared_context.judgeline_start + start_tolerance
    valid_judgeline_end = shared_context.judgeline_end - end_tolerance
    danger_dist = shared_context.judgeline_start * 0.85

    # read track data
    for key, value in candidate_slide_head_data.items():

        track_id, note_type = key
        note_geometry_list = value

        if note_type != NoteType.SLIDE: continue
        if len(note_geometry_list) < 10: continue


        # read track path
        valid_track_path = []
        for note in note_geometry_list:

            # 计算距离圆心的距离
            dist_to_center = np.sqrt(((note.cx - shared_context.std_video_cx)**2 + (note.cy - shared_context.std_video_cy)**2))
            # 计算方向(1-8)
            position = calculate_oct_position(shared_context.std_video_cx, shared_context.std_video_cy, note.cx, note.cy)
            # 过滤10%-90%距离的数据
            if dist_to_center < valid_judgeline_start:
                continue # 掐头
            elif dist_to_center > valid_judgeline_end:
                continue # 去尾
            # 添加轨迹点
            valid_track_path.append((note.frame, position, dist_to_center))


        # 检查轨迹存在
        if not valid_track_path:
            print(f"preprocess_slide_head_data: no valid_track_path for track_id {track_id}")
            continue

        # 检验长度
        if len(valid_track_path) < 6:
            print(f"preprocess_slide_head_data: valid_track_path too short for track_id {track_id}, length: {len(valid_track_path)}")
            continue

        # 检验方位一致
        positions = [x[1] for x in valid_track_path]
        if len(set(positions)) != 1:
            print(f"preprocess_slide_head_data: positions not consistent for track_id {track_id}")
            continue

        # 按frame排序
        valid_track_path.sort(key=lambda x: x[0])

        dists = [x[2] for x in valid_track_path]
        
        # 检查 danger dist
        if any(dist < danger_dist for dist in dists):
            print(f"preprocess_slide_head_data: dist in danger zone for track_id {track_id}, dist: {dists}")
            continue

        # 检查dist是否递增 (允许微小回退 -0.5* start_tolerance)
        if not all(later - earlier > -0.5 * start_tolerance for earlier, later in zip(dists, dists[1:])):
            print(f"preprocess_slide_head_data: dist not increasing for track_id {track_id}")
            continue

        # 检查头尾dist是否覆盖全程 (25%-60%)
        big_head = valid_judgeline_start + 1.5*start_tolerance
        big_tail = valid_judgeline_end - 3*end_tolerance
        if dists[0] > big_head or dists[-1] < big_tail:
            print(f"preprocess_slide_head_data: dist out of range for track_id {track_id}, start_dist: {dists[0]}, end_dist: {dists[-1]}. Allowed range: {big_head} - {big_tail}")
            continue

        # 检查通过，添加到slide_data
        note_variant = note_geometry_list[0].note_variant
        position = positions[0]
        key = (track_id, note_type, note_variant, position)

        path = []
        for frame_num, position, dist_to_center in valid_track_path:
            path.append({
                'frame': frame_num,
                'dist': dist_to_center
            })

        slide_data[key] = path
        # self.draw_path_on_frame(track_id, path[0]['frame']+3, path)

    if not slide_data:
        print("preprocess_slide_head_data: no slide head data")
        return {}

    return slide_data




def preprocess_slide_tail_data(shared_context: SharedContext, candidate_slide_tail_data: dict):
    '''
    对所有轨迹点进行方位计算，形成移动路径
    只分离出移动阶段的星星，忽略星星头
    分离方法: 仅接受轨迹开头和结尾都在A区的音符

    返回格式:
    dict{
        key: (track_id, note_type, note_variant, start_position),
        value: note path
        [
            {
                'frame': frame_num,
                'cx': cx,
                'cy': cy,
                'dist': dist_to_center,
                'position': position
            },
            ...
        ]
    }
    '''

    slide_data = {}

    # read track data
    for key, value in candidate_slide_tail_data.items():

        track_id, note_type = key
        note_geometry_list = value

        if note_type != NoteType.SLIDE: continue
        if len(note_geometry_list) < 10: continue


        # 先检查开头和结尾
        all_postions = [calculate_all_position(
                        shared_context.touch_areas,
                        note.cx, note.cy
                       ) for note in note_geometry_list]
        start_in_a_zone = all_postions[0].startswith('A') or \
                          _is_close_to_a_zone_endpoint(shared_context,
                                                       note_geometry_list[0].cx,
                                                       note_geometry_list[0].cy)
        end_in_a_zone = all_postions[-1].startswith('A') or \
                        _is_close_to_a_zone_endpoint(shared_context,
                                                     note_geometry_list[-1].cx,
                                                     note_geometry_list[-1].cy)
        if not start_in_a_zone:
            print(f"preprocess_slide_tail_data: start point not in A zone for track_id {track_id}")
            continue
        if not end_in_a_zone:
            print(f"preprocess_slide_tail_data: end point not in A zone for track_id {track_id}")
            continue



        # read track path
        valid_track_path = []
        for note in note_geometry_list:

            # 计算距离圆心的距离
            dist_to_center = np.sqrt(((note.cx - shared_context.std_video_cx)**2 + (note.cy - shared_context.std_video_cy)**2))
            # 允许音符略微超出判定线范围(5%)，但更远的就忽略了
            if dist_to_center > shared_context.judgeline_end * 1.05: # 105%
                continue
            # 计算方位
            position = calculate_all_position(shared_context.touch_areas, note.cx, note.cy)
            # 添加轨迹点
            valid_track_path.append((note.frame, note.cx, note.cy, position, dist_to_center))


        # 检查轨迹存在
        if not valid_track_path:
            print(f"preprocess_slide_tail_data: no valid_track_path for track_id {track_id}")
            continue

        # 检验长度
        if len(valid_track_path) < 6:
            print(f"preprocess_slide_tail_data: valid_track_path too short for track_id {track_id}, length: {len(valid_track_path)}")
            continue

        # 按frame排序
        valid_track_path.sort(key=lambda x: x[0])
        
        # 检查通过，添加到slide_data
        note_variant = note_geometry_list[0].note_variant
        positions = [x[3] for x in valid_track_path]
        if not positions or len(positions[0]) < 2:
            continue
        position = positions[0][1] # A1 -> 1
        key = (track_id, note_type, note_variant, position)

        path = []
        for frame_num, cx, cy, position, dist_to_center in valid_track_path:
            path.append({
                'frame': frame_num,
                'cx': cx,
                'cy': cy,
                'dist': dist_to_center,
                'position': position
            })
        
        slide_data[key] = path
        # self.draw_path_on_frame(track_id, path[0]['frame']+3, path)

    if not slide_data:
        print("preprocess_slide_tail_data: no slide tail data")
        return {}

    return slide_data
