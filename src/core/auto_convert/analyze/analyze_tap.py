def analyze_tap_reach_time(self, tap_data):

    tap_info = {}
    for (track_id, class_id, direction), path in tap_data.items():
        # 平均所有轨迹的到达时间
        times = []
        for point in path:
            frame_num = point['frame']
            dist = point['dist']
            reach_end_Msec = self.predict_note_reach_end_time(dist, frame_num)
            times.append(reach_end_Msec)
        mean = np.mean(times)
        tap_info[(track_id, class_id, direction)] = mean

        
        # min = np.min(times)
        # max = np.max(times)
        # median = np.median(times)
        # std_dev = np.std(times)
        # if max - min > 4:
        #     print(f"Tap ID {track_id} Direction {direction}:")
        #     print(f"  Mean {mean:.3f}, Min {min:.3f}, Max {max:.3f}, Median {median:.3f}, Std Dev {std_dev:.3f}")


    return tap_info




def predict_note_reach_end_time(self, cur_dist, cur_frame):
    '''
    正向:
    [dist_offset] = -1/120 * 总距离 * (OptionNotespeed/150f -1)
    [time_offset] = (OptionNotespeed/150f -1) * (-0.5 / (OptionNotespeed/150f -1)) * 1.6 * 1000 / 60
    高速的dist和time偏移都是负值 (实测后取消应用 time_offset)

    时间进度 = (current_Msec - leave_start_Msec + time_offset) / [DefaultMsec]
    travelled_dist = 时间进度 * [total_dist]
    current_dist = [startPos] + travelled_dist + [dist_offset]

    逆向:
    已知 current_dist, [dist_offset], [startPos]
    -> travelled_dist = current_dist - startPos - dist_offset
    已知 travelled_dist, [total_dist]
    -> 时间进度 = travelled_dist / total_dist
    已知 时间进度, [DefaultMsec], current_Msec, [time_offset]
    -> leave_start_Msec = current_Msec - 时间进度 * DefaultMsec + time_offset
    -> reach_end_Msec = leave_start_Msec + DefaultMsec
    '''

    cur_time = cur_frame / self.fps * 1000 # 转换为毫秒
    total_dist = self.note_travel_dist
    dist_offset = -1/120 * total_dist * (self.note_OptionNotespeed / 150 - 1)
    #time_offset = (self.note_OptionNotespeed / 150 - 1) * (-0.5 / (self.note_OptionNotespeed / 150 - 1)) * 1.6 * 1000 / 60
    start_pos = self.judgeline_start

    travelled_dist = cur_dist - start_pos - dist_offset
    time_progress = travelled_dist / total_dist
    leave_start_Msec = cur_time - time_progress * self.note_DefaultMsec # + time_offset
    reach_end_Msec = leave_start_Msec + self.note_DefaultMsec

    return reach_end_Msec
