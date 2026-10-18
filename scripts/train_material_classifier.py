"""
Train Material Classifier (YOLOv8n-cls)
Phase 2 - Step 2: Training on datasets_synth/cls_dataset (peanut, corn, sunflower)

Rules:
- 3 classes: peanut, corn, sunflower
- Mild augmentation: brightness, blur, small rotation, tiny hue shift only
- Save to models/material_cls.pt only (never overwrite models/best.pt)
"""

import os
import sys
import shutil
import time
from ultralytics import YOLO

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATASET_DIR = os.path.join(PROJECT_ROOT, 'datasets_synth', 'cls_dataset')
TARGET_MODEL_PATH = os.path.join(PROJECT_ROOT, 'models', 'material_cls.pt')
RUNS_DIR = os.path.join(PROJECT_ROOT, 'runs', 'classify')


def train_classifier():
    print("=" * 70)
    print("PHASE 2 - STEP 2: TRAINING MATERIAL CLASSIFIER (YOLOv8n-cls)")
    print(f"Dataset:       {DATASET_DIR}")
    print(f"Target Output: {TARGET_MODEL_PATH}")
    print("=" * 70)

    if not os.path.exists(DATASET_DIR):
        print(f"Error: Dataset directory not found: {DATASET_DIR}")
        sys.exit(1)

    # Load base pretrained model
    base_model_path = os.path.join(PROJECT_ROOT, 'yolov8n-cls.pt')
    if not os.path.exists(base_model_path):
        base_model_path = 'yolov8n-cls.pt'

    print(f"Loading pretrained weights from: {base_model_path}")
    model = YOLO(base_model_path)

    # Set up mild augmentation parameters as specified:
    # brightness (hsv_v=0.15), tiny hue shift (hsv_h=0.015), small rotation (degrees=15.0)
    # no heavy distortion, no mixup, no cutmix
    t0 = time.time()
    results = model.train(
        data=DATASET_DIR,
        epochs=8,
        imgsz=96,
        batch=64,
        device='cpu',
        workers=4,
        degrees=15.0,     # small rotation
        hsv_h=0.015,      # tiny hue shift
        hsv_v=0.15,       # brightness
        hsv_s=0.10,       # slight saturation
        fliplr=0.5,       # horizontal flip
        flipud=0.5,       # vertical flip
        translate=0.05,   # small shift
        scale=0.08,       # small scale
        erasing=0.0,      # no random erasing
        auto_augment=None,
        project=RUNS_DIR,
        name='material_cls_run',
        exist_ok=True,
        verbose=True
    )

    train_time = time.time() - t0
    print(f"\nTraining completed in {train_time/60.0:.2f} minutes.")

    # Find trained best.pt
    run_best_pt = os.path.join(RUNS_DIR, 'material_cls_run', 'weights', 'best.pt')
    if not os.path.exists(run_best_pt):
        print(f"Error: Trained weights not found at {run_best_pt}!")
        sys.exit(1)

    # Save to models/material_cls.pt ONLY (never touch models/best.pt)
    os.makedirs(os.path.dirname(TARGET_MODEL_PATH), exist_ok=True)
    shutil.copy2(run_best_pt, TARGET_MODEL_PATH)
    print(f"SUCCESS: Saved trained classifier model to: {TARGET_MODEL_PATH}")
    print(f"Model file size: {os.path.getsize(TARGET_MODEL_PATH) / 1024 / 1024:.2f} MB")

    # Sanity check: load and verify model classes
    test_m = YOLO(TARGET_MODEL_PATH)
    print(f"Verified Model Names: {test_m.names}")


if __name__ == '__main__':
    train_classifier()
