import base64
import io
import os
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

# ---------------------------------------------------------------
# Image formats we can read and write
# ---------------------------------------------------------------
FORMATS = {            # name -> default extension
    "PNG": ".png", "JPG": ".jpg", "WEBP": ".webp", "BMP": ".bmp",
    "TIFF": ".tif", "GIF": ".gif", "ICO": ".ico", "PDF": ".pdf",
}
EXT_TO_FMT = {".png": "PNG", ".jpg": "JPG", ".jpeg": "JPG", ".webp": "WEBP", ".bmp": "BMP",
              ".tif": "TIFF", ".tiff": "TIFF", ".gif": "GIF", ".ico": "ICO", ".pdf": "PDF"}
IMAGE_TYPES = "*.jpg *.jpeg *.png *.bmp *.webp *.tif *.tiff *.gif *.ico"
SAVE_TYPES = [("PNG image", "*.png"), ("JPEG image", "*.jpg"), ("WEBP image", "*.webp"), ("BMP image", "*.bmp"),
              ("TIFF image", "*.tif"), ("GIF image", "*.gif"), ("Icon", "*.ico"), ("PDF document", "*.pdf")]


def flat_rgb(img):
    """RGB copy; transparent areas are filled with white (for formats without transparency)."""
    if img.mode in ("RGBA", "LA") or "transparency" in img.info:
        rgba = img.convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.getchannel("A"))
        return bg
    return img.convert("RGB")


def write_image(img, path, fmt=None, quality=90):
    """Save a PIL image in the given format (or the one the file extension says). Returns the format name."""
    fmt = fmt or EXT_TO_FMT.get(os.path.splitext(path)[1].lower(), "PNG")
    q = max(1, min(100, int(quality)))
    if fmt == "JPG":
        flat_rgb(img).save(path, "JPEG", quality=q, optimize=True)
    elif fmt == "WEBP":
        (img if img.mode in ("RGB", "RGBA") else img.convert("RGB")).save(path, "WEBP", quality=q)
    elif fmt == "PNG":
        img.save(path, "PNG", optimize=True)
    elif fmt == "BMP":
        flat_rgb(img).save(path, "BMP")
    elif fmt == "TIFF":
        img.save(path, "TIFF", compression="tiff_lzw")
    elif fmt == "GIF":
        flat_rgb(img).convert("P", palette=Image.Palette.ADAPTIVE, colors=256).save(path, "GIF")
    elif fmt == "ICO":
        side = max(img.size)
        canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        canvas.paste(img.convert("RGBA"), ((side - img.width) // 2, (side - img.height) // 2))
        sizes = [(s, s) for s in (16, 24, 32, 48, 64, 128, 256) if s <= side] or [(side, side)]
        canvas.save(path, "ICO", sizes=sizes)
    elif fmt == "PDF":
        flat_rgb(img).save(path, "PDF", resolution=100.0)
    else:
        raise ValueError(f"Unknown format: {fmt}")
    return fmt


def unique_path(folder, name, ext):
    path = os.path.join(folder, name + ext)
    n = 1
    while os.path.exists(path):
        path = os.path.join(folder, f"{name} ({n}){ext}")
        n += 1
    return path


def to_url(img, max_side=1400):
    """PIL image -> data URL the browser can show."""
    im = img.copy()
    im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=92)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def set_proc(img):
    S["proc"] = img.convert("RGB")
    small = S["proc"].copy()
    small.thumbnail((1400, 1400))  # working copy for live previews (same size as the picture shown on screen)
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
        filetypes=[("Image Files", IMAGE_TYPES), ("All Files", "*.*")],
    )
    if not path:
        return {"cancelled": True}
    try:
        with Image.open(path) as im:
            img = ImageOps.exif_transpose(im).convert("RGB").copy()
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
        filetypes=SAVE_TYPES,
    )
    if not path:
        return {"cancelled": True}
    try:
        fmt = write_image(S["proc"], path)
        return {"status": f"Saved: {path} ({fmt})"}
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


def apply_look(img, name):
    img = img.convert("RGB")
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
    return img


@eel.expose
def look(name):
    if S["proc"] is None:
        return NO_IMAGE
    return commit(apply_look(S["proc"], name), f"{name} Filter")


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
# Tools that work like Crop: pick an option on the wheel, see a live preview, then Apply or Cancel
# Each function gets (image, option, amount, scale) and returns (new image, short explanation).
# "scale" = preview size / full size, so radii look the same in the small preview as in the final image.
# ---------------------------------------------------------------
CH = ("Red", "Green", "Blue")


def otsu_threshold(gray):
    hist = np.bincount(gray.ravel(), minlength=256).astype(np.float64)
    total, sum_all = hist.sum(), (np.arange(256) * hist).sum()
    wb = sum_b = best = 0.0
    th = 0
    for t in range(256):
        wb += hist[t]
        if wb == 0:
            continue
        wf = total - wb
        if wf == 0:
            break
        sum_b += t * hist[t]
        var = wb * wf * (sum_b / wb - (sum_all - sum_b) / wf) ** 2
        if var > best:
            best, th = var, t
    return th


def t_grayscale(img, opt, amt, s):
    rgb = img.convert("RGB")
    if opt == "Luminance":
        return ImageOps.grayscale(rgb).convert("RGB"), "Gray = 0.299 R + 0.587 G + 0.114 B"
    a = np.asarray(rgb, dtype=np.float32)
    if opt == "Average":
        g, info = a.mean(axis=2), "Gray = (R + G + B) / 3"
    elif opt == "Lightness":
        g, info = (a.max(axis=2) + a.min(axis=2)) / 2, "Gray = (max + min) / 2"
    else:
        g, info = a[:, :, CH.index(opt)], f"Gray = the {opt} channel"
    return Image.fromarray(np.repeat(g[:, :, None], 3, axis=2).astype(np.uint8)), info


def t_threshold(img, opt, amt, s):
    g = ImageOps.grayscale(img.convert("RGB"))
    gray = np.asarray(g, dtype=np.uint8)
    if opt == "Manual":
        th = int(amt)
        mask, info = gray > th, f"Threshold = {th}"
    elif opt.startswith("Otsu"):
        th = otsu_threshold(gray)
        mask, info = gray > th, f"Otsu's automatic threshold = {th}"
    else:
        radius = max(1, int(round(int(amt) * s / 2)))
        local = np.asarray(g.filter(ImageFilter.BoxBlur(radius)), dtype=np.float32)
        mask, info = gray > (local - 5), f"Compared with the local average (window {int(amt)} px)"
    return Image.fromarray((mask * 255).astype(np.uint8)).convert("RGB"), info


def t_negative(img, opt, amt, s):
    rgb = img.convert("RGB")
    if opt == "All":
        return ImageOps.invert(rgb), "Every channel: 255 - value"
    if opt == "Solarize":
        return ImageOps.solarize(rgb, int(amt)), f"Pixels brighter than {int(amt)} are inverted"
    a = np.asarray(rgb).copy()
    a[:, :, CH.index(opt)] = 255 - a[:, :, CH.index(opt)]
    return Image.fromarray(a), f"Only the {opt} channel is inverted"


def t_contrast(img, opt, amt, s):
    rgb = img.convert("RGB")
    if opt == "Min-Max":
        return ImageOps.autocontrast(rgb), "Darkest pixel -> 0, brightest -> 255"
    if opt == "Percentile":
        return ImageOps.autocontrast(rgb, cutoff=float(amt)), f"Ignores the darkest and brightest {float(amt):g}%"
    return ImageOps.equalize(rgb), "Histogram equalization (flatter histogram)"


def t_channels(img, opt, amt, s):
    a = np.asarray(img.convert("RGB"))
    i = CH.index(opt.split()[0])
    if opt.endswith("(gray)"):
        g = a[:, :, i]
        return Image.fromarray(np.stack([g, g, g], axis=2)), f"The {CH[i]} channel shown as gray levels"
    out = np.zeros_like(a)
    out[:, :, i] = a[:, :, i]
    return Image.fromarray(out), f"Only the {CH[i]} channel is kept"


def t_resize(img, opt, amt, s, full):
    pct = float(amt) if opt == "Custom" else float(opt.rstrip("%"))
    fw, fh = full
    nw, nh = max(1, round(fw * pct / 100)), max(1, round(fh * pct / 100))
    if nw * nh > 80_000_000:
        raise ValueError("The resized image would be too large")
    out = img.resize((max(1, round(img.width * pct / 100)), max(1, round(img.height * pct / 100))), Image.Resampling.LANCZOS)
    return out, f"{fw} x {fh}  ->  {nw} x {nh} px"


def t_rotate(img, opt, amt, s):
    if opt == "Left 90":
        return img.rotate(90, expand=True), "90 degrees counter-clockwise"
    if opt == "Right 90":
        return img.rotate(-90, expand=True), "90 degrees clockwise"
    if opt == "180":
        return img.rotate(180), "180 degrees"
    ang = float(amt)
    return img.rotate(-ang, expand=True, resample=Image.Resampling.BICUBIC, fillcolor=(0, 0, 0)), \
        f"{ang:g} degrees clockwise (corners filled black)"


def t_flip(img, opt, amt, s):
    if opt == "Horizontal":
        return ImageOps.mirror(img), "Left <-> right"
    if opt == "Vertical":
        return ImageOps.flip(img), "Top <-> bottom"
    return ImageOps.flip(ImageOps.mirror(img)), "Both directions"


def t_looks(img, opt, amt, s):
    rgb = img.convert("RGB")
    look_img = apply_look(rgb, opt)
    k = max(0.0, min(1.0, float(amt) / 100))
    return (look_img if k >= 1 else Image.blend(rgb, look_img, k)), f"{opt} look at {int(amt)}% strength"


def t_sharpen(img, opt, amt, s):
    rgb = img.convert("RGB")
    if opt == "Unsharp mask":
        return rgb.filter(ImageFilter.UnsharpMask(radius=max(0.3, 2 * s), percent=int(amt), threshold=3)), \
            f"Unsharp mask, amount {int(amt)}%"
    if opt == "Edge enhance":
        return rgb.filter(ImageFilter.EDGE_ENHANCE_MORE), "Edge-enhance kernel"
    return rgb.filter(ImageFilter.DETAIL), "Detail kernel"


def t_blur(img, opt, amt, s):
    rgb = img.convert("RGB")
    if opt == "Gaussian":
        return rgb.filter(ImageFilter.GaussianBlur(max(0.1, float(amt) * s))), f"Gaussian blur, radius {int(amt)} px"
    if opt == "Box":
        return rgb.filter(ImageFilter.BoxBlur(max(0.1, float(amt) * s))), f"Box blur, radius {int(amt)} px"
    size = 2 * int(amt) + 1
    return rgb.filter(ImageFilter.MedianFilter(size)), f"Median filter {size} x {size} (removes salt-and-pepper noise)"


def t_vignette(img, opt, amt, s):
    arr = np.asarray(img.convert("RGB"), dtype=np.float32)
    h, w = arr.shape[:2]
    yy, xx = np.ogrid[-1:1:complex(h), -1:1:complex(w)]
    d = xx * xx + yy * yy
    k = float(amt) / 100
    mask = np.clip(1 - d * k, 0.2, 1) if opt == "Dark" else 1 + d * k * 0.6
    return Image.fromarray(np.clip(arr * mask[:, :, None], 0, 255).astype(np.uint8)), f"{opt} edges, strength {int(amt)}%"


# ---- colour grading: looks that tint shadows and highlights, bend contrast and colour ----
GRADES = {                     # sh/hi = colour added to the shadows / highlights (0..1), con = contrast, sat = colour, fade = lifted blacks
    "Teal-Orange": dict(sh=(-0.05, 0.05, 0.09), hi=(0.11, 0.04, -0.09), con=1.12, sat=1.12, fade=0.0),
    "Golden":      dict(sh=(0.07, 0.03, -0.06), hi=(0.17, 0.09, -0.15), con=1.06, sat=1.2, fade=0.02),
    "Cold Blue":   dict(sh=(-0.06, 0.0, 0.12), hi=(-0.06, 0.03, 0.11), con=1.08, sat=0.92, fade=0.0),
    "Matte":       dict(sh=(0.03, 0.02, 0.04), hi=(0.0, 0.0, -0.01), con=0.94, sat=0.88, fade=0.14),
}
GRADE_NAMES = ["Teal-Orange", "Golden", "Cold Blue", "Bleach", "Matte", "Sepia", "Cross", "Noir"]


def _lum(a):
    return (0.299 * a[:, :, 0] + 0.587 * a[:, :, 1] + 0.114 * a[:, :, 2])[:, :, None]


def apply_grade(img, name):
    a = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
    y = _lum(a)
    if name == "Sepia":
        m = np.array([[0.393, 0.769, 0.189], [0.349, 0.686, 0.168], [0.272, 0.534, 0.131]], dtype=np.float32)
        out = a @ m.T
    elif name == "Bleach":                                   # bleach bypass: half the colour, harder contrast
        out = (a * 0.45 + y * 0.55 - 0.5) * 1.4 + 0.5
    elif name == "Cross":                                    # cross process: each channel gets its own curve
        r = (a[:, :, 0] - 0.5) * 1.3 + 0.52
        g = (a[:, :, 1] - 0.5) * 1.08 + 0.5
        b = a[:, :, 2] * 0.78 + 0.12
        out = np.stack([r, g, b], axis=2)
        gray = _lum(out)
        out = gray + (out - gray) * 1.2
    elif name == "Noir":                                     # high-contrast black and white with cool shadows
        out = np.repeat((y - 0.45) * 1.5 + 0.45, 3, axis=2)
        out[:, :, 2] += (1 - y[:, :, 0]) * 0.05
    elif name in GRADES:
        g = GRADES[name]
        out = a + ((1 - y) ** 2) * np.array(g["sh"], np.float32) + (y ** 2) * np.array(g["hi"], np.float32)
        out = (out - 0.5) * g["con"] + 0.5
        gray = _lum(out)
        out = gray + (out - gray) * g["sat"]
        out = out * (1 - g["fade"]) + g["fade"] * 0.12
    else:
        raise ValueError(f"Unknown grade: {name}")
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))


def t_grading(img, opt, amt, s):
    rgb = img.convert("RGB")
    graded = apply_grade(rgb, opt)
    k = max(0.0, min(1.0, float(amt) / 100))
    return (graded if k >= 1 else Image.blend(rgb, graded, k)), f"{opt} grade at {int(amt)}% strength"


TOOL_FUNCS = {"grayscale": t_grayscale, "threshold": t_threshold, "negative": t_negative, "contrast": t_contrast,
              "channels": t_channels, "rotate": t_rotate, "flip": t_flip, "looks": t_looks, "grading": t_grading,
              "sharpen": t_sharpen, "blur": t_blur, "vignette": t_vignette}
TOOL_NAMES = {"grayscale": "Grayscale", "threshold": "Black & White", "negative": "Negative", "contrast": "Contrast Stretch",
              "channels": "RGB Channels", "resize": "Resize", "rotate": "Rotate", "flip": "Flip", "looks": "Looks", "grading": "Color Grading",
              "sharpen": "Sharpen", "blur": "Blur", "vignette": "Vignette"}


def run_tool(img, tool, opt, amt, full):
    s = img.width / full[0]
    if tool == "resize":
        return t_resize(img, opt, amt, s, full)
    if tool not in TOOL_FUNCS:
        raise ValueError(f"Unknown tool: {tool}")
    return TOOL_FUNCS[tool](img, opt, amt, s)


@eel.expose
def tool_preview(tool, opt, amt=0):
    if S["small"] is None:
        return NO_IMAGE
    try:
        out, info = run_tool(S["small"], tool, opt, amt, S["proc"].size)
        return {"preview": to_url(out), "info": info}
    except Exception as e:
        return {"error": str(e)}


@eel.expose
def tool_apply(tool, opt, amt=0):
    if S["proc"] is None:
        return NO_IMAGE
    try:
        out, _ = run_tool(S["proc"], tool, opt, amt, S["proc"].size)
    except Exception as e:
        return {"error": str(e)}
    return commit(out, f"{TOOL_NAMES.get(tool, tool)} ({opt})")


@eel.expose
def tool_thumbs(tool, options):
    """A small picture of what every option of a tool does to the open image.
    options = [[option name, slider value], ...]; returns one data URL (or None) per option."""
    if S["small"] is None:
        return NO_IMAGE
    base = ImageOps.fit(S["small"].convert("RGB"), (96, 96), Image.Resampling.LANCZOS)
    urls = []
    for opt, amt in options:
        try:
            out, _ = run_tool(base, tool, opt, amt, base.size)      # base.size as "full size": radii are not scaled down
            urls.append(to_url(ImageOps.fit(out.convert("RGB"), (96, 96), Image.Resampling.LANCZOS), 96))
        except Exception:
            urls.append(None)
    return {"thumbs": urls}


# ---------------------------------------------------------------
# Resize: By Size / As Percentage / Social Media, and export with a maximum file size
# ---------------------------------------------------------------
MAX_PIXELS = 80_000_000


def resize_image(img, p):
    """p = {"mode": "size" | "percent" | "social", ...}  ->  (resized image, short explanation)"""
    w0, h0 = img.size
    mode = p.get("mode", "size")
    fit = "fill"
    if mode == "percent":
        pw = float(p.get("pw") or 100)
        ph = float(p.get("ph") or pw)
        w, h = round(w0 * pw / 100), round(h0 * ph / 100)
    elif mode == "social":
        w, h, fit = int(p["w"]), int(p["h"]), p.get("fit", "fill")
    else:
        w = int(round(float(p.get("w") or 0)))
        h = int(round(float(p.get("h") or 0)))
        if not w and not h:
            raise ValueError("Enter a width or a height")
        if p.get("lock", True):                         # keep the picture's shape
            if not h:
                h = round(h0 * w / w0)
            elif not w:
                w = round(w0 * h / h0)
        else:
            w, h = w or w0, h or h0
    if w < 1 or h < 1:
        raise ValueError("The size must be at least 1 px")
    if w * h > MAX_PIXELS:
        raise ValueError("The resized image would be too large (limit: 80 megapixels)")
    rgb = img.convert("RGB")
    lanczos = Image.Resampling.LANCZOS
    if mode == "social" and fit == "fill":
        out = ImageOps.fit(rgb, (w, h), lanczos)                      # crop the edges so the picture fills the frame
    elif mode == "social" and fit == "fit":
        inner = ImageOps.contain(rgb, (w, h), lanczos)                # whole picture, white bars where needed
        out = Image.new("RGB", (w, h), (255, 255, 255))
        out.paste(inner, ((w - inner.width) // 2, (h - inner.height) // 2))
    else:
        out = rgb.resize((w, h), lanczos)
    return out, f"{w0} x {h0} -> {w} x {h} px"


def fit_to_size(img, max_bytes):
    """JPEG data no bigger than max_bytes: use the best quality that fits, and shrink the picture only if even a low quality is too big."""
    flat = flat_rgb(img)
    scale = 1.0
    while True:
        cur = flat if scale == 1.0 else flat.resize((max(1, round(flat.width * scale)), max(1, round(flat.height * scale))), Image.Resampling.LANCZOS)
        lo, hi, best = 10, 95, None
        while lo <= hi:
            q = (lo + hi) // 2
            buf = io.BytesIO()
            cur.save(buf, "JPEG", quality=q, optimize=True)
            if buf.tell() <= max_bytes:
                best, lo = (buf.getvalue(), q), q + 1
            else:
                hi = q - 1
        if best:
            return best[0], best[1], cur.size
        scale *= 0.85
        if min(flat.width, flat.height) * scale < 16:
            raise ValueError("The file cannot be made that small")


@eel.expose
def resize_apply(p):
    if S["proc"] is None:
        return NO_IMAGE
    try:
        out, info = resize_image(S["proc"], p)
    except Exception as e:
        return {"error": str(e)}
    return commit(out, f"Resize ({info})")


@eel.expose
def resize_export(p, target_kb=None):
    """Save a resized copy as a file. The picture in the editor is not changed.
    With a target file size the copy is always a JPG that is no bigger than the target."""
    if S["proc"] is None:
        return NO_IMAGE
    try:
        out, info = resize_image(S["proc"], p)
    except Exception as e:
        return {"error": str(e)}
    if target_kb:
        path = dialog(filedialog.asksaveasfilename, defaultextension=".jpg", initialfile="resized.jpg",
                      filetypes=[("JPEG image", "*.jpg")])
        if not path:
            return {"cancelled": True}
        if not path.lower().endswith((".jpg", ".jpeg")):
            path = os.path.splitext(path)[0] + ".jpg"
        try:
            data, q, size = fit_to_size(out, int(float(target_kb) * 1024))
            with open(path, "wb") as f:
                f.write(data)
        except Exception as e:
            return {"error": str(e)}
        note = "" if size == out.size else f", shrunk to {size[0]} x {size[1]} px to fit"
        return {"status": f"Saved: {path} (JPG, {len(data) / 1024:.0f} KB, quality {q}{note})"}
    path = dialog(filedialog.asksaveasfilename, defaultextension=".png", initialfile="resized.png", filetypes=SAVE_TYPES)
    if not path:
        return {"cancelled": True}
    try:
        fmt = write_image(out, path)
        return {"status": f"Saved: {path} ({fmt}, {os.path.getsize(path) / 1024:.0f} KB, {out.width} x {out.height} px)"}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------
# Format conversion
# ---------------------------------------------------------------
@eel.expose
def convert_current(fmt, quality=90):
    """Save the image that is open in the editor in another format (the editor's image is not changed)."""
    if S["proc"] is None:
        return NO_IMAGE
    if fmt not in FORMATS:
        return {"error": f"Unknown format: {fmt}"}
    ext = FORMATS[fmt]
    path = dialog(filedialog.asksaveasfilename, defaultextension=ext, initialfile="converted" + ext,
                  filetypes=[(f"{fmt} image", "*" + ext)])
    if not path:
        return {"cancelled": True}
    if EXT_TO_FMT.get(os.path.splitext(path)[1].lower()) != fmt:
        path = os.path.splitext(path)[0] + ext
    try:
        write_image(S["proc"], path, fmt, quality)
        return {"status": f"Saved: {path} ({fmt}, {os.path.getsize(path) / 1024:.0f} KB)"}
    except Exception as e:
        return {"error": str(e)}


@eel.expose
def convert_files(fmt, quality=90):
    """Pick any number of image files and convert them all to one format."""
    if fmt not in FORMATS:
        return {"error": f"Unknown format: {fmt}"}
    files = dialog(filedialog.askopenfilenames, title="Choose the images to convert",
                   filetypes=[("Image files", IMAGE_TYPES), ("All files", "*.*")])
    if not files:
        return {"cancelled": True}
    folder = dialog(filedialog.askdirectory, title="Choose the folder for the converted files")
    if not folder:
        return {"cancelled": True}
    ext, ok, failed = FORMATS[fmt], 0, []
    for f in files:
        try:
            with Image.open(f) as im:
                im = ImageOps.exif_transpose(im)
                im = im.convert("RGBA") if (im.mode in ("RGBA", "LA", "P") and "transparency" in im.info) or im.mode in ("RGBA", "LA") else im.convert("RGB")
                write_image(im, unique_path(folder, os.path.splitext(os.path.basename(f))[0], ext), fmt, quality)
            ok += 1
        except Exception:
            failed.append(os.path.basename(f))
    msg = f"Converted {ok} file{'s' if ok != 1 else ''} to {fmt} in {folder}"
    if failed:
        msg += f" ({len(failed)} failed: {', '.join(failed[:3])}{'...' if len(failed) > 3 else ''})"
    return {"status": msg, "ok": ok, "failed": failed}


# ---------------------------------------------------------------
if __name__ == "__main__":
    try:
        eel.start("index.html", size=(1450, 850))
    except EnvironmentError:
        eel.start("index.html", size=(1450, 850), mode="edge")
