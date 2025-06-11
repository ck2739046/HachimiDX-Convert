# filepath: d:\git\mai-chart-analyse\ca_modules\NoteDetector.py
import cv2
import numpy as np
import os

class NoteDetector:
    def __init__(self):
        self.tap_template_path = "static/template/tap.png"
        self.tap_template = None
        self.tap_contours = None
        
    def load_tap_template(self):
        """Load tap template and process it with alpha thresholding and edge detection
        ret: processed template and contours
        """
        try:
            print("Note Detector...Loading tap template...", end="\r")
            
            # Get full path to template
            template_path_full = os.path.join(os.path.dirname(os.path.dirname(__file__)), self.tap_template_path)
            if not os.path.exists(template_path_full):
                raise Exception("load_tap_template: Template tap.png not found")
            
            # Load image with alpha channel
            template_bgra = cv2.imread(template_path_full, cv2.IMREAD_UNCHANGED)
            if template_bgra is None:
                raise Exception("load_tap_template: Cannot load tap.png")
            
            # Check if image has alpha channel
            if template_bgra.shape[2] != 4:
                raise Exception("load_tap_template: tap.png must have alpha channel")
            
            # Extract alpha channel
            alpha_channel = template_bgra[:, :, 3]
            
            # Apply threshold to alpha channel (threshold = 200)
            _, binary_alpha = cv2.threshold(alpha_channel, 200, 255, cv2.THRESH_BINARY)
            
            # Apply edge detection (Canny)
            edges = cv2.Canny(binary_alpha, 50, 150)
            
            # Find contours from edge detection
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                raise Exception("load_tap_template: No contours found in tap template")
            
            # Store the original template (BGR) and contours
            self.tap_template = cv2.cvtColor(template_bgra[:, :, :3], cv2.COLOR_BGR2RGB)  # Convert to RGB for matplotlib
            self.tap_contours = contours
            print("Note Detector...Loading tap template...Done                    ")
            print(f"  Found {len(contours)} contour(s) in tap template")
            
            return self.tap_template, self.tap_contours
            
        except Exception as e:
            raise Exception(f"Error in load_tap_template: {e}")
    
    def visualize_tap_template(self):
        """Visualize the tap template with contours in a new window
        """
        try:
            if self.tap_template is None or self.tap_contours is None:
                print("Note Detector: Loading template first...")
                self.load_tap_template()
            
            print("Note Detector...Visualizing tap template...", end="\r")
            
            # Convert RGB back to BGR for OpenCV display
            template_bgr = cv2.cvtColor(self.tap_template, cv2.COLOR_RGB2BGR)
            
            # Create a copy for drawing contours
            template_with_contours = template_bgr.copy()
            
            # Draw contours on the template
            cv2.drawContours(template_with_contours, self.tap_contours, -1, (0, 0, 255), 2)
            
            # Create side-by-side display
            height = max(template_bgr.shape[0], template_with_contours.shape[0])
            width = template_bgr.shape[1] + template_with_contours.shape[1] + 20  # Add gap
            
            # Create combined image
            combined = np.zeros((height, width, 3), dtype=np.uint8)
            
            # Place original template on the left
            combined[:template_bgr.shape[0], :template_bgr.shape[1]] = template_bgr
            
            # Place template with contours on the right
            start_x = template_bgr.shape[1] + 20
            combined[:template_with_contours.shape[0], start_x:start_x+template_with_contours.shape[1]] = template_with_contours
            
            # Add text labels
            cv2.putText(combined, "Original", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(combined, f"With Contours ({len(self.tap_contours)} found)", 
                       (start_x + 10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            
            # Display the window
            window_name = "Tap Template Visualization"
            cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
            cv2.imshow(window_name, combined)
            
            print("Note Detector...Visualizing tap template...Done                    ")
            print("  Press any key to close the visualization window")
            
            # Wait for user input
            cv2.waitKey(0)
            cv2.destroyWindow(window_name)
            
        except Exception as e:
            raise Exception(f"Error in visualize_tap_template: {e}")
        
if __name__ == "__main__":
    detector = NoteDetector()
    try:
        detector.load_tap_template()
        detector.visualize_tap_template()
    except Exception as e:
        print(f"Error: {e}")