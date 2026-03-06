import numpy as np

from ..detect.note_definition import *
from .tool import *
from .shared_context import *



def preprocess_slide_head_data(shared_context: SharedContext):
    '''
    返回格式:
    dict{
        key: (track_id, note_type, note_varient, note_position),
        value: note path
        [
            {
                'frame': frame_num,
                'cx': cx,
                'cy': cy,
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

    # read track data
    for key, value in shared_context.track_data.items():

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
            valid_track_path.append((note.frame, note.cx, note.cy, position, dist_to_center))


        # 检查轨迹存在
        if not valid_track_path:
            # print(f"preprocess_slide_head_data: no valid_track_path for track_id {track_id}")
            continue

        # 检验长度
        if len(valid_track_path) < 6:
            # print(f"preprocess_slide_head_data: valid_track_path too short for track_id {track_id}, length: {len(valid_track_path)}")
            continue

        # 检验方位一致
        positions = [x[3] for x in valid_track_path]
        if len(set(positions)) != 1:
            # print(f"preprocess_slide_head_data: positions not consistent for track_id {track_id}")
            continue

        # 按frame排序
        valid_track_path.sort(key=lambda x: x[0])
        
        # 检查dist是否递增 (允许微小回退 -0.5* start_tolerance)
        dists = [x[4] for x in valid_track_path]
        if not all(later - earlier > -0.5 * start_tolerance for earlier, later in zip(dists, dists[1:])):
            # print(f"preprocess_slide_head_data: dist not increasing for track_id {track_id}")
            continue

        # 检查头尾dist是否覆盖全程 (20%-80%)
        if dists[0] > valid_judgeline_start + start_tolerance or dists[-1] < valid_judgeline_end - end_tolerance:
            # print(f"preprocess_slide_head_data: dist out of range for track_id {track_id}, start_dist: {dists[0]}, end_dist: {dists[-1]}")
            continue

        # 检查通过，添加到slide_data
        note_varient = note_geometry_list[0].note_variant
        position = positions[0]
        key = (track_id, note_type, note_varient, position)

        path = []
        for frame_num, cx, cy, position, dist_to_center in valid_track_path:
            path.append({
                'frame': frame_num,
                'cx': cx,
                'cy': cy,
                'dist': dist_to_center
            })

        slide_data[key] = path
        # self.draw_path_on_frame(track_id, path[0]['frame']+3, path)

    if not slide_data:
        print("preprocess_slide_head_data: no slide head data")
        return {}

    return slide_data




def preprocess_slide_tail_data(shared_context: SharedContext):
    '''
    对所有轨迹点进行方位计算，形成移动路径
    只分离出移动阶段的星星，忽略星星头
    分离方法: 仅接受轨迹开头和结尾都在A区的音符

    返回格式:
    dict{
        key: (track_id, note_type, note_varient, start_position),
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
    for key, value in shared_context.track_data.items():

        track_id, note_type = key
        note_geometry_list = value

        if note_type != NoteType.SLIDE: continue
        if len(note_geometry_list) < 10: continue


        # 先检查开头和结尾
        start = note_geometry_list[0]
        position = calculate_all_position(shared_context.touch_areas, start.cx, start.cy)
        if not position.startswith('A'):
            continue # 忽视非A区开头音符
        end = note_geometry_list[-1]
        position = calculate_all_position(shared_context.touch_areas, end.cx, end.cy)
        if not position.startswith('A') and not position.startswith('D'):
            continue # 忽视非A区或D区结尾音符


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
            # print(f"preprocess_slide_tail_data: no valid_track_path for track_id {track_id}")
            continue

        # 检验长度
        if len(valid_track_path) < 6:
            # print(f"preprocess_slide_tail_data: valid_track_path too short for track_id {track_id}, length: {len(valid_track_path)}")
            continue

        # 按frame排序
        valid_track_path.sort(key=lambda x: x[0])
        
        # 检查通过，添加到slide_data
        note_varient = note_geometry_list[0].note_variant
        positions = [x[5] for x in valid_track_path]
        position = positions[0]
        key = (track_id, note_type, note_varient, position)

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
