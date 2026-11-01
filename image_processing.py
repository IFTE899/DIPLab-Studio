
import cv2
import numpy as np
from PIL import Image


def process_image(image, operation, threshold=127):
    """
    Accept a PIL image, apply processing,
    and return the processed PIL image.
    """

    rgb = np.array(image.convert("RGB"))

    if operation == "Grayscale":
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        result = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)

    elif operation == "Black & White":
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        _, binary = cv2.threshold(
            gray, threshold, 255, cv2.THRESH_BINARY
        )
        result = cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)

    elif operation == "Negative":
        result = 255 - rgb

    elif operation == "Flip Horizontal":
        result = cv2.flip(rgb, 1)

    elif operation == "Flip Vertical":
        result = cv2.flip(rgb, 0)

    elif operation == "Contrast Stretch":
        low = int(rgb.min())
        high = int(rgb.max())

        if high == low:
            result = rgb.copy()
        else:
            result = np.clip(
                (rgb.astype(np.float32) - low)
                * 255 / (high - low),
                0, 255
            ).astype(np.uint8)

    elif operation == "Resize Image":
        height, width = rgb.shape[:2]
        result = cv2.resize(
            rgb,
            (max(1, width // 2), max(1, height // 2)),
            interpolation=cv2.INTER_AREA
        )

    elif operation == "RGB Channels":
        # Display red channel only for initial demo
        result = np.zeros_like(rgb)
        result[:, :, 0] = rgb[:, :, 0]

    else:
        result = rgb.copy()

    return Image.fromarray(result)


def adjust_brightness(image, value):
    rgb = np.array(image.convert("RGB"))
    result = np.clip(
        rgb.astype(np.int16) + int(value),
        0, 255
    ).astype(np.uint8)
    return Image.fromarray(result)
