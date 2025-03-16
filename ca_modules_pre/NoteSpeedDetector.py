# tap speed, touch speed

import cv2
import numpy as np

class NoteSpeedDetector:
    def __init__(self):
        self.tap_template = None
        self.touch_template = None
        self.circle_center = None
        self.circle_radius = None
        self.touch_areas = None
        self.tap_speed = None
        self.touch_speed = None

    def process(self, cap, circle_info, touch_areas, state: dict) -> tuple:
        """Main process
        arg: cap, circle_info(center, radius), touch_areas{}, 
             state(video_width, video_height, debug)
        ret: tap_speed, touch_speed
        """
        pass

    def load_templates(self) -> None:
        """Load tap and touch note templates
        arg: None
        ret: None (sets self.tap_template and self.touch_template)
        """
        pass

    def detect_tap_notes(self, frame) -> list:
        """Detect tap notes in a single frame using template matching
        arg: frame
        ret: list of note positions [(x, y), ...]
        """
        pass

    def detect_touch_notes(self, frame) -> dict:
        """Detect touch notes in areas using template matching
        arg: frame
        ret: dict of notes in each area {area_label: [(x, y), ...], ...}
        """
        pass

    def track_tap_notes(self, frames_data) -> list:
        """Track tap notes across multiple frames
        arg: frames_data[{frame_id, notes[]}]
        ret: list of note tracks [{positions[], times[]}, ...]
        """
        pass

    def track_touch_notes(self, frames_data) -> dict:
        """Track touch notes across multiple frames
        arg: frames_data[{frame_id, area_notes{}}]
        ret: dict of note tracks by area {area: [{sizes[], times[]}, ...]}
        """
        pass

    def calculate_tap_speed(self, note_tracks) -> float:
        """Calculate average tap note speed (pixels/ms)
        arg: note_tracks[{positions[], times[]}]
        ret: average_speed
        """
        pass

    def calculate_touch_speed(self, note_tracks) -> float:
        """Calculate average touch note size change speed (pixels/ms)
        arg: note_tracks{area: [{sizes[], times[]}, ...]}
        ret: average_speed
        """
        pass

    def display_preview(self, cap, state) -> None:
        """Display preview with detected notes and speeds
        arg: cap, state
        ret: None
        """
        pass