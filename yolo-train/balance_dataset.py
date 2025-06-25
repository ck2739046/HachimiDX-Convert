
import os
import shutil
from collections import Counter
from pathlib import Path
import random

def get_class_distribution(labels_dir: Path, class_names: dict):
    """Calculates and prints the class distribution in a dataset."""
    class_counts = Counter()
    if not labels_dir.exists():
        print(f"Warning: Label directory not found at {labels_dir}")
        return class_counts

    for label_file in labels_dir.glob("*.txt"):
        with open(label_file, 'r') as f:
            for line in f:
                try:
                    class_id = int(line.split()[0])
                    class_counts[class_id] += 1
                except (ValueError, IndexError):
                    continue
    
    print("\n--- Class Distribution ---")
    total_instances = sum(class_counts.values())
    if total_instances == 0:
        print("No labels found.")
        return class_counts

    for class_id, count in sorted(class_counts.items()):
        name = class_names.get(class_id, f"Class_{class_id}")
        percentage = (count / total_instances) * 100
        print(f"{name} (ID: {class_id}): {count} instances ({percentage:.2f}%)")
    print(f"Total instances: {total_instances}")
    print("--------------------------\n")
    return class_counts

def balance_dataset(dataset_dir: Path, rare_classes: list, duplication_factor: int, class_names: dict):
    """
    Balances the dataset by oversampling images containing rare classes.
    
    Args:
        dataset_dir: Path to the root of the dataset (e.g., 'datasets/').
        rare_classes: A list of class IDs to oversample.
        duplication_factor: The total number of times each rare image should exist. 
                            A factor of 2 means 1 copy is made.
        class_names: A dictionary mapping class IDs to names.
    """
    train_images_dir = dataset_dir / "images" / "train"
    train_labels_dir = dataset_dir / "labels" / "train"

    if not train_images_dir.exists() or not train_labels_dir.exists():
        print(f"Error: Training directories not found in {dataset_dir}.")
        print("Please generate the dataset first.")
        return

    print("--- Before Balancing ---")
    get_class_distribution(train_labels_dir, class_names)

    if duplication_factor <= 1:
        print("Duplication factor must be greater than 1. No changes made.")
        return

    # Find all files containing at least one rare class
    files_to_duplicate = set()
    for label_file in train_labels_dir.glob("*.txt"):
        with open(label_file, 'r') as f:
            for line in f:
                try:
                    class_id = int(line.split()[0])
                    if class_id in rare_classes:
                        files_to_duplicate.add(label_file.stem)
                        break
                except (ValueError, IndexError):
                    continue
    
    if not files_to_duplicate:
        print("No images found containing the specified rare classes. No changes made.")
        return

    print(f"Found {len(files_to_duplicate)} images containing rare classes {rare_classes}.")
    print(f"Creating {duplication_factor - 1} copies of each...")

    # Duplicate the files
    copy_count = 0
    for i in range(1, duplication_factor):
        for stem in files_to_duplicate:
            # Source paths
            src_image_path = train_images_dir / f"{stem}.jpg"
            src_label_path = train_labels_dir / f"{stem}.txt"

            # Destination paths
            dst_image_path = train_images_dir / f"{stem}_bal_{i}.jpg"
            dst_label_path = train_labels_dir / f"{stem}_bal_{i}.txt"

            if src_image_path.exists() and src_label_path.exists():
                shutil.copy(src_image_path, dst_image_path)
                shutil.copy(src_label_path, dst_label_path)
                copy_count += 1

    print(f"Successfully created {copy_count} new image-label pairs.")

    print("--- After Balancing ---")
    get_class_distribution(train_labels_dir, class_names)


if __name__ == "__main__":
    # --- Configuration ---
    # This should point to your 'datasets' directory inside 'yolo-train'
    DATASET_DIR = Path(__file__).parent / "datasets"

    # Class names from your 'data.yaml'
    CLASS_NAMES = {
        0: "tap_note",
        1: "slide_note",
        2: "hold_note",
        3: "touch_note"
    }

    # Define which classes are "rare" and need to be oversampled.
    # Based on your description, 'touch_note' (3) and likely 'hold_note' (2) are rare.
    RARE_CLASSES_TO_OVERSAMPLE = [3]

    # Set the desired number of copies. A factor of 5 means each original image
    # will have 4 new copies, for a total of 5 instances.
    # Adjust this factor based on the initial imbalance.
    DUPLICATION_FACTOR = 4

    # --- End of Configuration ---

    balance_dataset(DATASET_DIR, RARE_CLASSES_TO_OVERSAMPLE, DUPLICATION_FACTOR, CLASS_NAMES)
