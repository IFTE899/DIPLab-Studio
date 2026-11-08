import base64
import io
import tkinter as tk
from tkinter import filedialog

import eel
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

eel.init("web")

# ---------------------------------------------------------------
# App state (lives in Python, the UI only displays it)
# ---------------------------------------------------------------
S = {"orig": None, "proc": None, "small": None, "history": [], "redo": []}
NO_IMAGE = {"error": "Please open an image first."}


def to_url(img, max_side=1400):
    """PIL image -> data URL the browser can show."""
    im = img.copy()
    im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def set_proc(img):
    S["proc"] = img.convert("RGB")
    small = S["proc"].copy()
    small.thumbnail((900, 900))  # smaller copy = fast slider preview
    S["small"] = small


def state(msg, with_original=False):
    w, h = S["proc"].size
    out = {
        "processed": to_url(S["proc"]),
        "size": f"{w} x {h}",
        "status": msg,
    }
    if with_original:
        out["original"] = to_url(S["orig"])
    return out


def commit(img, action):
    S["history"].append(S["proc"].copy())
    if len(S["history"]) > 20:
        S["history"].pop(0)
    S["redo"].clear()
    set_proc(img)
    return state(f"Applied: {action}")


def dialog(fn, **kw):
    """Native Windows file dialog."""
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        return fn(parent=root, **kw)
    finally:
        root.destroy()


def shift_rgb(img, dr, dg, db):
    data = np.array(img).astype(np.int16)
    data[:, :, 0] += dr
    data[:, :, 1] += dg
    data[:, :, 2] += db
    return Image.fromarray(np.clip(data, 0, 255).astype(np.uint8))


# ---------------------------------------------------------------
# Open / Save
# ---------------------------------------------------------------
@eel.expose
def pick_open():
    path = dialog(
        filedialog.askopenfilename,
        filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp *.webp"), ("All Files", "*.*")],
    )
    if not path:
        return {"cancelled": True}
    try:
        with Image.open(path) as im:
            img = im.convert("RGB").copy()
    except Exception as e:
        return {"error": str(e)}
    S["orig"] = img.copy()
    S["history"].clear()
    S["redo"].clear()
    set_proc(img)
    return state(f"Loaded: {path}", with_original=True)


@eel.expose
def open_data(data_url, name="dropped image"):
    """Open an image that was dragged into the window (sent as a data URL)."""
    try:
        raw = base64.b64decode(data_url.split(",", 1)[1])
        with Image.open(io.BytesIO(raw)) as im:
            img = im.convert("RGB").copy()
    except Exception as e:
        return {"error": str(e)}
    S["orig"] = img.copy()
    S["history"].clear()
    S["redo"].clear()
    set_proc(img)
    return state(f"Loaded: {name}", with_original=True)


@eel.expose
def save_image():
    if S["proc"] is None:
        return NO_IMAGE
    path = dialog(
        filedialog.asksaveasfilename,
        defaultextension=".png",
        filetypes=[("PNG Image", "*.png"), ("JPEG Image", "*.jpg")],
    )
    if not path:
        return {"cancelled": True}
    try:
        S["proc"].save(path)
        return {"status": f"Saved: {path}"}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------
# Basic DIP
# ---------------------------------------------------------------
@eel.expose
def basic(op, threshold=127):
    if S["proc"] is None:
        return NO_IMAGE
    img = S["proc"]
    if op == "Grayscale":
        out = ImageOps.grayscale(img).convert("RGB")
    elif op == "Black & White":
        gray = np.array(ImageOps.grayscale(img))
        out = Image.fromarray(((gray > threshold) * 255).astype(np.uint8)).convert("RGB")
    elif op == "Negative":
        out = ImageOps.invert(img)
    elif op == "Contrast Stretch":
        out = ImageOps.autocontrast(img)
    else:
        return {"error": f"Unknown operation: {op}"}
    return commit(out, op)


# ---------------------------------------------------------------
# Transform
# ---------------------------------------------------------------
@eel.expose
def transform(action):
    if S["proc"] is None:
        return NO_IMAGE
    img = S["proc"].copy()
    if action == "left":
        img = img.rotate(90, expand=True)
    elif action == "right":
        img = img.rotate(-90, expand=True)
    elif action == "flip_h":
        img = ImageOps.mirror(img)
    elif action == "flip_v":
        img = ImageOps.flip(img)
    elif action == "crop_square":
        size = min(img.size)
        img = ImageOps.fit(img, (size, size))
    elif action == "crop_wide":
        w, h = img.size
        if w / h > 16 / 9:
            nw = int(h * 16 / 9)
            box = ((w - nw) // 2, 0, (w + nw) // 2, h)
        else:
            nh = int(w * 9 / 16)
            box = (0, (h - nh) // 2, w, (h + nh) // 2)
        img = img.crop(box)
    elif action == "resize":
        w, h = img.size
        img = img.resize((max(1, w // 2), max(1, h // 2)), Image.Resampling.LANCZOS)
    return commit(img, action)


# ---------------------------------------------------------------
# Looks & effects
# ---------------------------------------------------------------
@eel.expose
def crop(x0, y0, x1, y1):
    """Custom crop. Coordinates are fractions (0-1) of the current image."""
    if S["proc"] is None:
        return NO_IMAGE
    w, h = S["proc"].size
    left = max(0, int(round(x0 * w)))
    top = max(0, int(round(y0 * h)))
    right = min(w, int(round(x1 * w)))
    bottom = min(h, int(round(y1 * h)))
    if right - left < 2 or bottom - top < 2:
        return {"error": "Crop area is too small."}
    return commit(S["proc"].crop((left, top, right, bottom)), "Custom Crop")


@eel.expose
def look(name):
    if S["proc"] is None:
        return NO_IMAGE
    img = S["proc"].copy()
    if name == "Portrait":
        img = ImageEnhance.Brightness(img).enhance(1.08)
        img = ImageEnhance.Color(img).enhance(0.92)
    elif name == "Vintage":
        img = ImageEnhance.Color(img).enhance(0.65)
        img = shift_rgb(img, 18, 8, -12)
    elif name == "Warm":
        img = shift_rgb(img, 20, 0, -14)
    elif name == "Cool":
        img = shift_rgb(img, -12, 0, 20)
    elif name == "Cinematic":
        img = ImageEnhance.Contrast(img).enhance(1.25)
        img = ImageEnhance.Color(img).enhance(0.8)
    elif name == "Black & White":
        img = ImageOps.grayscale(img).convert("RGB")
    return commit(img, f"{name} Filter")


@eel.expose
def effect(name):
    if S["proc"] is None:
        return NO_IMAGE
    img = S["proc"].copy()
    if name == "sharpen":
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
    elif name == "blur":
        img = img.filter(ImageFilter.GaussianBlur(3))
    elif name == "smooth":
        img = img.filter(ImageFilter.MedianFilter(3))
    elif name == "vignette":
        arr = np.array(img).astype(np.float32)
        h, w = arr.shape[:2]
        yy, xx = np.ogrid[-1:1:complex(h), -1:1:complex(w)]
        mask = np.clip(1 - (xx * xx + yy * yy) * 0.35, 0.35, 1)
        arr *= mask[:, :, None]
        img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    return commit(img, name)


# ---------------------------------------------------------------
# Slider adjustments (live preview + apply)
# ---------------------------------------------------------------
def adjust(img, v):
    img = ImageEnhance.Brightness(img).enhance(max(0.01, 1 + v["Brightness"] / 100))
    img = ImageEnhance.Contrast(img).enhance(max(0.01, 1 + v["Contrast"] / 100))
    img = ImageEnhance.Color(img).enhance(max(0, 1 + v["Saturation"] / 100))
    img = ImageEnhance.Sharpness(img).enhance(max(0, 1 + v["Sharpness"] / 50))
    warmth = int(v["Warmth"])
    if warmth:
        img = shift_rgb(img, warmth // 2, 0, -(warmth // 2))
    return img


@eel.expose
def preview(values):
    if S["small"] is None:
        return NO_IMAGE
    return {"preview": to_url(adjust(S["small"], values))}


@eel.expose
def apply_adjust(values):
    if S["proc"] is None:
        return NO_IMAGE
    return commit(adjust(S["proc"], values), "Tune Image")


# ---------------------------------------------------------------
# History
# ---------------------------------------------------------------
@eel.expose
def undo():
    if S["proc"] is None:
        return NO_IMAGE
    if not S["history"]:
        return {"status": "Nothing to undo"}
    S["redo"].append(S["proc"].copy())
    set_proc(S["history"].pop())
    return state("Undo completed")


@eel.expose
def redo():
    if S["proc"] is None:
        return NO_IMAGE
    if not S["redo"]:
        return {"status": "Nothing to redo"}
    S["history"].append(S["proc"].copy())
    set_proc(S["redo"].pop())
    return state("Redo completed")


@eel.expose
def reset():
    if S["orig"] is None:
        return NO_IMAGE
    return commit(S["orig"].copy(), "Reset to Original")


# ---------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------
def hist(img):
    arr = np.array(img)
    return [np.bincount(arr[:, :, c].ravel(), minlength=256).tolist() for c in range(3)]


@eel.expose
def histogram():
    if S["proc"] is None:
        return NO_IMAGE
    return {"orig": hist(S["orig"]), "proc": hist(S["proc"])}


@eel.expose
def profile():
    if S["proc"] is None:
        return NO_IMAGE
    gray = np.array(S["proc"].convert("L"))
    return {"row": gray[gray.shape[0] // 2, :].tolist()}


@eel.expose
def rgb_channels():
    if S["proc"] is None:
        return NO_IMAGE
    data = np.array(S["proc"])
    out = []
    for i, name in enumerate(["Red", "Green", "Blue"]):
        ch = np.zeros_like(data)
        ch[:, :, i] = data[:, :, i]
        out.append({"name": name, "url": to_url(Image.fromarray(ch), 500)})
    return {"channels": out}


# ---------------------------------------------------------------
if __name__ == "__main__":
    try:
        eel.start("index.html", size=(1450, 850))
    except EnvironmentError:
        eel.start("index.html", size=(1450, 850), mode="edge")
