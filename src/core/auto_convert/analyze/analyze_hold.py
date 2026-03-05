def analyze_hold_reach_time(self, hold_data):

    hold_info = {}

    end_tolerance = self.note_travel_dist * 0.1
    start_tolerance = self.note_travel_dist * 0.1
    valid_judgeline_start = self.judgeline_start + start_tolerance
    valid_judgeline_end = self.judgeline_end - end_tolerance

    for (track_id, class_id, direction), path in hold_data.items():

        head_times = []
        tail_times = []
        # 平均所有轨迹的到达时间
        for point in path:
            frame_num = point['frame']
            dist_head = point['dist-head']
            dist_tail = point['dist-tail']
            # 过滤 head 和 tail (10%-90%)
            if valid_judgeline_start <= dist_head <= valid_judgeline_end:
                reach_end_Msec_head = self.predict_note_reach_end_time(dist_head, frame_num)
                head_times.append(reach_end_Msec_head)
            if valid_judgeline_start <= dist_tail <= valid_judgeline_end:
                reach_end_Msec_tail = self.predict_note_reach_end_time(dist_tail, frame_num)
                tail_times.append(reach_end_Msec_tail)
        # 计算平均时间
        mean_head = np.mean(head_times)
        mean_tail = np.mean(tail_times)
        hold_info[(track_id, class_id, direction)] = (mean_head, mean_tail)

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
