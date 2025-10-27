#!/usr/bin/env python3
"""
Subsample images for faster processing
Use this when you have too many images and want a quick preview orthomosaic
"""

import shutil
import argparse
from pathlib import Path

def subsample_images(input_dir: str, output_dir: str, keep_every_nth: int = 2):
    """
    Keep every Nth image, useful for reducing processing time

    Args:
        input_dir: Directory with all images
        output_dir: Directory to copy subsampled images to
        keep_every_nth: Keep every Nth image (2 = keep 50%, 3 = keep 33%, etc.)
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Get all images sorted by name
    image_extensions = ['.jpg', '.jpeg', '.JPG', '.JPEG', '.png', '.PNG']
    all_images = []
    for ext in image_extensions:
        all_images.extend(sorted(input_path.glob(f'*{ext}')))

    all_images = sorted(all_images)

    print(f"Found {len(all_images)} total images")

    # Keep every Nth image
    kept_images = all_images[::keep_every_nth]

    print(f"Keeping {len(kept_images)} images (every {keep_every_nth})")
    print(f"Reduction: {100 * (1 - len(kept_images)/len(all_images)):.1f}%")

    # Copy selected images
    for img in kept_images:
        shutil.copy2(img, output_path / img.name)

    print(f"\nSubsampled images saved to: {output_path}")
    print(f"\nTo process these:")
    print(f"  python image_processor.py {output_path} --output mapping_output --use-odm")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Subsample images for faster processing")
    parser.add_argument("input_dir", help="Directory containing all images")
    parser.add_argument("output_dir", help="Directory for subsampled images")
    parser.add_argument("--keep-every", type=int, default=2,
                       help="Keep every Nth image (2=50%%, 3=33%%, 4=25%%)")

    args = parser.parse_args()

    subsample_images(args.input_dir, args.output_dir, args.keep_every)
