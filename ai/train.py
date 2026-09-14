"""
YOLOv8 Model Training Script for Raw Material Visual Inspection.
Food Manufacturing System — AI Quality Control Module.

Usage:
    # Inspect dataset details without training:
    python ai/train.py --inspect-only

    # Train model (interactive confirmation prompt):
    python ai/train.py --epochs 25 --batch 16 --imgsz 640

    # Train model with direct confirmation flag:
    python ai/train.py --epochs 25 --batch 16 --imgsz 640 --yes
"""

import os
import sys
import shutil
import argparse
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("ai_train")

# Resolve project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_YAML = PROJECT_ROOT / "datasets" / "raw_materials" / "data.yaml"
DEFAULT_MODELS_DIR = PROJECT_ROOT / "models"
DEFAULT_BASE_MODEL = "yolov8n.pt"


def get_device():
    """Detect available accelerator or fall back to CPU."""
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            logger.info(f"CUDA GPU detected: {gpu_name}")
            return "0"
    except Exception:
        pass
    logger.info("Using CPU for execution.")
    return "cpu"


def inspect_dataset(data_yaml_path: Path) -> dict:
    """
    Inspects and validates the dataset structure and data.yaml.
    Returns dataset metadata dictionary.
    """
    if not data_yaml_path.exists():
        raise FileNotFoundError(f"Dataset configuration not found at: {data_yaml_path}")

    import yaml
    with open(data_yaml_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    dataset_root = data_yaml_path.parent
    
    # Handle relative paths in yaml
    train_rel = config.get("train", "train/images")
    val_rel = config.get("val", config.get("valid", "valid/images"))
    test_rel = config.get("test", "test/images")

    # Resolve paths
    train_dir = (dataset_root / train_rel).resolve()
    val_dir = (dataset_root / val_rel).resolve()
    test_dir = (dataset_root / test_rel).resolve() if test_rel else None

    # Count image files
    image_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}

    def count_images(dir_path):
        if not dir_path or not dir_path.exists():
            return 0
        return len([f for f in dir_path.iterdir() if f.is_file() and f.suffix.lower() in image_exts])

    def count_labels(dir_path):
        if not dir_path:
            return 0
        # Corresponding labels dir
        labels_dir = dir_path.parent / "labels"
        if not labels_dir.exists():
            return 0
        return len([f for f in labels_dir.iterdir() if f.is_file() and f.suffix.lower() == ".txt"])

    train_count = count_images(train_dir)
    val_count = count_images(val_dir)
    test_count = count_images(test_dir) if test_dir else 0

    train_lbl_count = count_labels(train_dir)
    val_lbl_count = count_labels(val_dir)
    test_lbl_count = count_labels(test_dir) if test_dir else 0

    classes = config.get("names", [])
    if isinstance(classes, dict):
        class_list = [classes[k] for k in sorted(classes.keys())]
    else:
        class_list = list(classes)

    nc = config.get("nc", len(class_list))

    meta = {
        "yaml_path": str(data_yaml_path),
        "dataset_root": str(dataset_root),
        "train_dir": str(train_dir),
        "val_dir": str(val_dir),
        "test_dir": str(test_dir) if test_dir else "None",
        "classes": class_list,
        "num_classes": nc,
        "train_images": train_count,
        "train_labels": train_lbl_count,
        "val_images": val_count,
        "val_labels": val_lbl_count,
        "test_images": test_count,
        "test_labels": test_lbl_count,
        "raw_config": config
    }
    return meta


def print_dataset_summary(meta: dict):
    """Prints a formatted report of dataset inspection."""
    print("=" * 70)
    print("AI VISUAL INSPECTION — DATASET CONFIGURATION SUMMARY")
    print("=" * 70)
    print(f"Dataset Path        : {meta['dataset_root']}")
    print(f"data.yaml Path      : {meta['yaml_path']}")
    print(f"Number of Classes   : {meta['num_classes']}")
    print(f"Dataset Classes     : {meta['classes']}")
    print("-" * 70)
    print(f"Training Images     : {meta['train_images']} (labels: {meta['train_labels']})")
    print(f"Validation Images   : {meta['val_images']} (labels: {meta['val_labels']})")
    print(f"Test Images         : {meta['test_images']} (labels: {meta['test_labels']})")
    print(f"Total Dataset Images: {meta['train_images'] + meta['val_images'] + meta['test_images']}")
    print("-" * 70)
    print("data.yaml content:")
    import yaml
    print(yaml.dump(meta['raw_config'], default_flow_style=False).strip())
    print("=" * 70)


def train_yolo(args, meta: dict):
    """
    Executes YOLOv8 model training using Ultralytics.
    Exports the resulting best.pt weights into models/.
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        logger.error("Ultralytics package is not installed. Run: pip install ultralytics")
        sys.exit(1)

    device = args.device if args.device is not None else get_device()
    logger.info(f"Loading base architecture: {args.model}")
    model = YOLO(args.model)

    runs_dir = PROJECT_ROOT / "runs"
    
    logger.info("Starting YOLOv8 training:")
    logger.info(f"  - Dataset    : {meta['yaml_path']}")
    logger.info(f"  - Epochs     : {args.epochs}")
    logger.info(f"  - Batch Size : {args.batch}")
    logger.info(f"  - Image Size : {args.imgsz}")
    logger.info(f"  - Device     : {device}")
    logger.info(f"  - Output Dir : {runs_dir}")

    train_results = model.train(
        data=meta["yaml_path"],
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        device=device,
        name=args.name,
        exist_ok=True,
        workers=args.workers,
        pretrained=True,
        plots=True,
        verbose=True
    )

    logger.info("Training completed successfully.")

    # Find the trained best.pt
    save_dir = Path(train_results.save_dir) if hasattr(train_results, "save_dir") else runs_dir / args.name
    best_pt = save_dir / "weights" / "best.pt"
    last_pt = save_dir / "weights" / "last.pt"

    if not best_pt.exists():
        logger.warning(f"Could not locate best.pt at expected path: {best_pt}")
        return

    # Deploy best.pt into models/
    target_models_dir = Path(args.export_dir)
    target_models_dir.mkdir(parents=True, exist_ok=True)
    
    deployed_best = target_models_dir / "best.pt"
    deployed_alias = target_models_dir / "food_defect_yolov8.pt"

    shutil.copy2(best_pt, deployed_best)
    shutil.copy2(best_pt, deployed_alias)
    logger.info(f"Deployed model weights to: {deployed_best}")
    logger.info(f"Deployed model alias to  : {deployed_alias}")

    # Evaluate on test set if available
    if meta["test_images"] > 0:
        logger.info("Evaluating trained model on test split...")
        try:
            val_model = YOLO(str(deployed_best))
            metrics = val_model.val(data=meta["yaml_path"], split="test", device=device)
            logger.info("Test split evaluation completed.")
            if hasattr(metrics, "box"):
                logger.info(f"  - mAP50    : {metrics.box.map50:.4f}")
                logger.info(f"  - mAP50-95 : {metrics.box.map:.4f}")
        except Exception as e:
            logger.warning(f"Test split validation encountered warning: {e}")

    print("\n" + "=" * 70)
    print("YOLOV8 TRAINING & MODEL DEPLOYMENT COMPLETED")
    print("=" * 70)
    print(f"Trained Weights Exported: {deployed_best}")
    print(f"System Model Alias     : {deployed_alias}")
    print("The Food Manufacturing System AI module (ai/yolo_service.py) is now ready to detect defects!")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Food Manufacturing AI Inspection YOLOv8 Training Pipeline")
    parser.add_argument("--data", type=str, default=str(DEFAULT_DATA_YAML), help="Path to data.yaml")
    parser.add_argument("--model", type=str, default=DEFAULT_BASE_MODEL, help="Base YOLOv8 model (e.g. yolov8n.pt)")
    parser.add_argument("--epochs", type=int, default=10, help="Number of training epochs (default: 10)")
    parser.add_argument("--batch", type=int, default=8, help="Batch size (default: 8)")
    parser.add_argument("--imgsz", type=int, default=416, help="Image size in pixels (default: 416)")
    parser.add_argument("--device", type=str, default=None, help="Device to use ('cpu' or '0' for CUDA GPU)")
    parser.add_argument("--workers", type=int, default=0, help="Dataloader workers (default: 0 for Windows)")
    parser.add_argument("--export-dir", type=str, default=str(DEFAULT_MODELS_DIR), help="Target models/ directory")
    parser.add_argument("--name", type=str, default="raw_materials_yolov8", help="Experiment name")
    parser.add_argument("--inspect-only", action="store_true", help="Only inspect dataset and exit without training")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt and start training directly")

    args = parser.parse_args()

    yaml_path = Path(args.data).resolve()
    meta = inspect_dataset(yaml_path)
    print_dataset_summary(meta)

    if args.inspect_only:
        print("\nInspection mode only. No training performed.")
        return

    if not args.yes:
        print("\n" + "!" * 70)
        print("CONFIRMATION REQUIRED BEFORE STARTING TRAINING")
        print(f"Configuration: {args.epochs} epochs, batch {args.batch}, {args.model} on {args.device or 'auto-device'}")
        print("To run unattended, execute: python ai/train.py --yes")
        print("!" * 70)
        user_input = input("Do you want to proceed with training now? [y/N]: ").strip().lower()
        if user_input not in ["y", "yes"]:
            print("Training cancelled by user.")
            return

    train_yolo(args, meta)


if __name__ == "__main__":
    main()
