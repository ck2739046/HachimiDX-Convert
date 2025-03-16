import cv2
import numpy as np
import os

class NoteSpeedDetector:
    def __init__(self):
        self.template_path = "static/template/01"
        self.tap_template = None
        self.touch_template = None
        self.circle_center = None
        self.circle_radius = None
        self.touch_areas = None
        self.tap_speed = None
        self.touch_speed = None

    def process(self, cap, state: dict):
        try:
            self.circle_center = state['circle_center']
            self.circle_radius = state['circle_radius']
            self.touch_areas = state['touch_areas']

            self.tap_template, self.touch_template = self.load_templates()


        except Exception as e:
            raise Exception(f"Error in NoteSpeedDetector: {e}")


    def load_templates(self):
        """Load and resize template image
        arg: self.template_path
        ret: (tap_template, touch_template)
        """
        tap_path = os.path.join(self.template_path, "Tap_01.png")
        touch_path = os.path.join(self.template_path, "UI_NOTES_Touch_01.png")
        tap_template = cv2.imread(tap_path, cv2.IMREAD_GRAYSCALE)
        touch_template = cv2.imread(touch_path, cv2.IMREAD_GRAYSCALE)
        if tap_template is None or touch_template is None:
            raise FileNotFoundError("load_templates: Cannot load template image")
        return tap_template, touch_template