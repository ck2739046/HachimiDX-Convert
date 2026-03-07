import numpy as np

from .shared_context import *
from .analyze_tap import predict_tap_reach_end_time



def analyze_hold_reach_time(shared_context, hold_data):
    """
    返回：
    dict{
        key: 同 preprocess_hold_data,
        value: (time, duration)
    }
    """

    hold_info = {}

    for key, path in hold_data.items():

        head_times = []
        tail_times = []

        # 平均所有轨迹的到达时间
        for point in path:
            frame_num = point['frame']
            dist_head = point['dist-head']
            dist_tail = point['dist-tail']

            reach_end_Msec_head = predict_tap_reach_end_time(shared_context, dist_head, frame_num)
            head_times.append(reach_end_Msec_head)

            reach_end_Msec_tail = predict_tap_reach_end_time(shared_context, dist_tail, frame_num)
            tail_times.append(reach_end_Msec_tail)
        
        # 计算平均时间
        mean_head = np.mean(head_times)
        mean_tail = np.mean(tail_times)

        duration = mean_tail - mean_head
        hold_info[key] = (mean_head, duration)

        # print(f"Hold ID {track_id} Direction {direction}:")
        # min1 = np.min(head_times)
        # max1 = np.max(head_times)
        # median1 = np.median(head_times)
        # std_dev1 = np.std(head_times)
        # print(f"  head - Mean {mean_head:.3f}, Min {min1:.3f}, Max {max1:.3f}, Median {median1:.3f}, Std Dev {std_dev1:.3f}")

        # min2 = np.min(tail_times)
        # max2 = np.max(tail_times)
        # median2 = np.median(tail_times)
        # std_dev2 = np.std(tail_times)
        # print(f"  tail - Mean {mean_tail:.3f}, Min {min2:.3f}, Max {max2:.3f}, Median {median2:.3f}, Std Dev {std_dev2:.3f}")

    return hold_info
