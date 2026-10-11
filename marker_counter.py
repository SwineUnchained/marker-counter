#!/usr/bin/env python3
"""
Marker Counter — count inventory by detecting colored markers, not objects.

The insight: don't try to detect boxes (edges, shadows, and overlapping
cardboard fool every algorithm). Instead, put one bright marker per box
and count the markers by color. Each marker = one unit. Simple, robust.

Usage:
    python marker_counter.py photo.jpg
    python marker_counter.py photo.jpg --color red --output annotated.jpg
    python marker_counter.py photo.jpg --color orange --min-area 50 --max-area 5000

Colors: red, orange, yellow, green, blue, pink (or specify custom HSV range)
"""

import argparse
import sys

try:
    import cv2
    import numpy as np
except ImportError:
    print("Need opencv-python and numpy: pip install opencv-python numpy", file=sys.stderr)
    sys.exit(1)


# Preset HSV ranges (H: 0-179, S: 0-255, V: 0-255 in OpenCV)
COLOR_PRESETS = {
    # Red wraps around hue 0, so we use two ranges
    "red": [
        (np.array([0, 100, 100]), np.array([10, 255, 255])),
        (np.array([160, 100, 100]), np.array([179, 255, 255])),
    ],
    "orange": [
        (np.array([8, 100, 100]), np.array([22, 255, 255])),
    ],
    # Red-orange: the sweet spot for bright tape markers on cardboard
    "red-orange": [
        (np.array([0, 80, 80]), np.array([15, 255, 255])),
        (np.array([165, 80, 80]), np.array([179, 255, 255])),
    ],
    "yellow": [
        (np.array([20, 100, 100]), np.array([35, 255, 255])),
    ],
    "green": [
        (np.array([35, 100, 100]), np.array([85, 255, 255])),
    ],
    "blue": [
        (np.array([90, 100, 100]), np.array([130, 255, 255])),
    ],
    "pink": [
        (np.array([140, 100, 100]), np.array([160, 255, 255])),
    ],
}


def count_markers(image_path, color="red-orange", min_area=20, max_area=2000,
                  min_circularity=0.2, output_path=None, verbose=True):
    """Count colored markers in an image. Returns (count, annotated_image)."""
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Build combined mask from all ranges for this color
    ranges = COLOR_PRESETS.get(color)
    if not ranges:
        raise ValueError(f"Unknown color '{color}'. Choose from: {list(COLOR_PRESETS)}")

    mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
    for lower, upper in ranges:
        mask = cv2.bitwise_or(mask, cv2.inRange(hsv, lower, upper))

    # Light cleanup: remove specks without merging nearby markers
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    # Find blobs
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    markers = []
    for c in contours:
        area = cv2.contourArea(c)
        if not (min_area <= area <= max_area):
            continue
        # Circularity filter: markers are roughly round dots
        peri = cv2.arcLength(c, True)
        if peri > 0:
            circularity = 4 * np.pi * area / (peri * peri)
            if circularity < min_circularity:
                continue
        M = cv2.moments(c)
        if M["m00"] > 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            markers.append((cx, cy, area))

    # Annotate
    annotated = img.copy()
    for i, (cx, cy, area) in enumerate(markers, 1):
        radius = int(np.sqrt(area / np.pi)) + 5
        cv2.circle(annotated, (cx, cy), radius, (0, 255, 0), 2)
        cv2.putText(annotated, str(i), (cx - 10, cy - radius - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    # Summary overlay
    cv2.putText(annotated, f"Count: {len(markers)}", (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)

    if output_path:
        cv2.imwrite(output_path, annotated)
        if verbose:
            print(f"Annotated image saved to: {output_path}")

    if verbose:
        print(f"Markers found: {len(markers)}")

    return len(markers), annotated


def main():
    p = argparse.ArgumentParser(
        description="Count inventory markers by color. Put one bright marker per item, photograph straight-on, count the markers.")
    p.add_argument("image", help="Input photo path")
    p.add_argument("--color", default="red-orange",
                   choices=list(COLOR_PRESETS),
                   help="Marker color (default: red-orange)")
    p.add_argument("--min-area", type=int, default=20,
                   help="Minimum blob area in px (default: 20)")
    p.add_argument("--max-area", type=int, default=2000,
                   help="Maximum blob area in px (default: 2000)")
    p.add_argument("--min-circularity", type=float, default=0.2,
                   help="Minimum circularity 0-1 (default: 0.2)")
    p.add_argument("--output", "-o", default=None,
                   help="Save annotated image to this path")
    args = p.parse_args()

    count, _ = count_markers(args.image, color=args.color,
                             min_area=args.min_area, max_area=args.max_area,
                             min_circularity=args.min_circularity,
                             output_path=args.output)
    # Print just the number last for easy scripting
    print(count)


if __name__ == "__main__":
    main()
