
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageEnhance, ImageFilter, ImageOps
import numpy as np
import cv2

from image_processing import process_image


class DIPLabStudio:
    def __init__(self, root):
        self.root = root
        self.root.title("DIPLab Studio | Professional Image Editor")
        self.root.geometry("1450x850")
        self.root.minsize(1100, 680)

        self.bg = "#0f172a"
        self.panel = "#1e293b"
        self.sidebar_bg = "#17243a"
        self.accent = "#2563eb"
        self.text = "#f8fafc"
        self.muted = "#94a3b8"

        self.root.configure(bg=self.bg)

        self.original_image = None
        self.processed_image = None
        self.history = []
        self.redo_history = []
        self.file_path = None
        self.compare_mode = False

        self.adjustments = {}
        self.preview_image = None

        self.build_ui()

    # -----------------------------------
    # UI HELPERS
    # -----------------------------------

    def label(self, parent, text, size=10, bold=False,
              color=None, bg=None):
        return tk.Label(
            parent,
            text=text,
            font=("Segoe UI", size, "bold" if bold else "normal"),
            fg=color or self.text,
            bg=bg or self.panel
        )

    def button(self, parent, text, command, color=None,
               side=None, padx=10):
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            bg=color or self.accent,
            fg="white",
            activebackground="#1d4ed8",
            activeforeground="white",
            relief="flat",
            bd=0,
            cursor="hand2",
            font=("Segoe UI", 10, "bold"),
            padx=padx,
            pady=9
        )

        if side:
            btn.pack(side=side, padx=5, pady=6)
        else:
            btn.pack(fill="x", padx=14, pady=4)

        return btn

    def section(self, parent, title):
        tk.Label(
            parent,
            text=title.upper(),
            bg=self.sidebar_bg,
            fg="#93c5fd",
            font=("Segoe UI", 10, "bold"),
            anchor="w"
        ).pack(fill="x", padx=14, pady=(20, 8))

    # -----------------------------------
    # MAIN INTERFACE
    # -----------------------------------

    def build_ui(self):

        # HEADER
        header = tk.Frame(self.root, bg=self.sidebar_bg, height=66)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header,
            text="DIPLab Studio",
            bg=self.sidebar_bg,
            fg="white",
            font=("Segoe UI", 23, "bold")
        ).pack(side="left", padx=(22, 16))

        tk.Label(
            header,
            text="PHOTO EDITING WORKSPACE",
            bg=self.sidebar_bg,
            fg=self.muted,
            font=("Segoe UI", 10)
        ).pack(side="left")

        # TOOLBAR
        toolbar = tk.Frame(self.root, bg=self.panel, height=56)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)

        self.button(toolbar, "Open Image", self.open_image, side="left")
        self.button(toolbar, "Save Image", self.save_image, side="left")
        self.button(toolbar, "Undo", self.undo, "#475569", "left")
        self.button(toolbar, "Redo", self.redo, "#475569", "left")
        self.button(toolbar, "Reset", self.reset_image, "#475569", "left")

        self.button(
            toolbar, "Before / After",
            self.toggle_comparison, "#334155", "left"
        )

        # WORKSPACE
        workspace = tk.Frame(self.root, bg=self.bg)
        workspace.pack(fill="both", expand=True, padx=10, pady=10)

        # LEFT SIDEBAR
        self.build_sidebar(workspace)

        # RIGHT SETTINGS PANEL
        self.build_settings(workspace)

        # CENTER IMAGE WORKSPACE
        center = tk.Frame(workspace, bg=self.bg)
        center.pack(
            side="left",
            fill="both",
            expand=True,
            padx=8
        )

        title_bar = tk.Frame(center, bg=self.panel, height=48)
        title_bar.pack(fill="x", pady=(0, 8))
        title_bar.pack_propagate(False)

        self.label(
            title_bar,
            "IMAGE WORKSPACE",
            12,
            True
        ).pack(side="left", padx=16, pady=12)

        self.image_info = self.label(
            title_bar, "No image loaded",
            9, color=self.muted
        )
        self.image_info.pack(side="right", padx=16)

        preview = tk.Frame(center, bg=self.bg)
        preview.pack(fill="both", expand=True)

        preview.grid_columnconfigure(0, weight=1)
        preview.grid_columnconfigure(1, weight=1)
        preview.grid_rowconfigure(0, weight=1)

        self.original_panel = self.create_preview(
            preview, "ORIGINAL IMAGE", 0
        )

        self.processed_panel = self.create_preview(
            preview, "EDITED IMAGE", 1
        )

        self.original_panel.bind(
            "<Configure>",
            lambda e: self.refresh_images()
        )
        self.processed_panel.bind(
            "<Configure>",
            lambda e: self.refresh_images()
        )

        # STATUS BAR
        self.status = tk.Label(
            self.root,
            text="Ready | DIPLab Studio v2.0 | Python + OpenCV",
            bg=self.sidebar_bg,
            fg=self.muted,
            anchor="w",
            padx=15,
            pady=7,
            font=("Segoe UI", 9)
        )
        self.status.pack(side="bottom", fill="x")

    # -----------------------------------
    # SCROLLABLE SIDEBAR
    # -----------------------------------

    def build_sidebar(self, parent):

        container = tk.Frame(
            parent, bg=self.sidebar_bg, width=220
        )
        container.pack(side="left", fill="y")
        container.pack_propagate(False)

        canvas = tk.Canvas(
            container,
            bg=self.sidebar_bg,
            highlightthickness=0
        )
        scrollbar = tk.Scrollbar(
            container, orient="vertical",
            command=canvas.yview
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=self.sidebar_bg)
        window_id = canvas.create_window(
            (0, 0), window=inner, anchor="nw"
        )

        inner.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfigure(
                window_id, width=e.width
            )
        )

        def scroll(event):
            canvas.yview_scroll(
                int(-event.delta / 120), "units"
            )

        def bind_wheel(event):
            canvas.bind_all("<MouseWheel>", scroll)

        def unbind_wheel(event):
            canvas.unbind_all("<MouseWheel>")

        container.bind("<Enter>", bind_wheel)
        container.bind("<Leave>", unbind_wheel)
        canvas.bind("<Enter>", bind_wheel)
        canvas.bind("<Leave>", unbind_wheel)

        tk.Label(
            inner,
            text="EDITING TOOLS",
            bg=self.sidebar_bg,
            fg="white",
            font=("Segoe UI", 13, "bold")
        ).pack(pady=18)

        self.section(inner, "Basic DIP")

        for name in [
            "Grayscale",
            "Black & White",
            "Negative",
            "Contrast Stretch",
            "RGB Channels"
        ]:
            self.button(
                inner, name,
                lambda n=name: self.apply_basic(n)
            )

        self.section(inner, "Transform")

        self.button(
            inner, "Rotate Left",
            lambda: self.transform("left")
        )
        self.button(
            inner, "Rotate Right",
            lambda: self.transform("right")
        )
        self.button(
            inner, "Flip Horizontal",
            lambda: self.transform("flip_h")
        )
        self.button(
            inner, "Flip Vertical",
            lambda: self.transform("flip_v")
        )
        self.button(
            inner, "Crop 1:1",
            lambda: self.transform("crop_square")
        )
        self.button(
            inner, "Crop 16:9",
            lambda: self.transform("crop_wide")
        )
        self.button(
            inner, "Resize 50%",
            lambda: self.transform("resize")
        )

        self.section(inner, "Looks & Filters")

        for name in [
            "Portrait",
            "Vintage",
            "Warm",
            "Cool",
            "Cinematic",
            "Black & White"
        ]:
            self.button(
                inner, name,
                lambda n=name: self.apply_filter(n)
            )

        self.section(inner, "Details")

        self.button(
            inner, "Sharpen",
            lambda: self.apply_effect("sharpen")
        )
        self.button(
            inner, "Gaussian Blur",
            lambda: self.apply_effect("blur")
        )
        self.button(
            inner, "Smooth Image",
            lambda: self.apply_effect("smooth")
        )
        self.button(
            inner, "Vignette",
            lambda: self.apply_effect("vignette")
        )

        self.section(inner, "Image Analysis")

        self.button(
            inner, "Show Histogram",
            self.show_histogram
        )
        self.button(
            inner, "Image Profile",
            self.show_profile
        )

        tk.Frame(
            inner, bg=self.sidebar_bg, height=20
        ).pack()

    # -----------------------------------
    # RIGHT SETTINGS PANEL
    # -----------------------------------

    def build_settings(self, parent):

        settings = tk.Frame(
            parent, bg=self.sidebar_bg, width=250
        )
        settings.pack(side="right", fill="y")
        settings.pack_propagate(False)

        tk.Label(
            settings,
            text="TUNE IMAGE",
            bg=self.sidebar_bg,
            fg="white",
            font=("Segoe UI", 13, "bold")
        ).pack(pady=(20, 8))

        tk.Label(
            settings,
            text="Adjust the photo using sliders",
            bg=self.sidebar_bg,
            fg=self.muted,
            font=("Segoe UI", 9)
        ).pack(pady=(0, 12))

        for name in [
            "Brightness",
            "Contrast",
            "Saturation",
            "Warmth",
            "Sharpness"
        ]:
            self.create_slider(settings, name)

        self.button(
            settings,
            "Apply Adjustments",
            self.apply_adjustments
        )

        self.button(
            settings,
            "Reset Sliders",
            self.reset_sliders,
            "#475569"
        )

        self.label(
            settings,
            "Changes preview before applying",
            9,
            color=self.muted,
            bg=self.sidebar_bg
        ).pack(pady=12)

    def create_slider(self, parent, name):

        frame = tk.Frame(parent, bg=self.sidebar_bg)
        frame.pack(fill="x", padx=14, pady=8)

        variable = tk.IntVar(value=0)
        self.adjustments[name] = variable

        tk.Label(
            frame,
            text=name,
            bg=self.sidebar_bg,
            fg="white",
            font=("Segoe UI", 10)
        ).pack(anchor="w")

        scale = tk.Scale(
            frame,
            from_=-100,
            to=100,
            orient="horizontal",
            variable=variable,
            command=lambda value: self.preview_adjustments(),
            bg=self.sidebar_bg,
            fg="#cbd5e1",
            troughcolor="#334155",
            highlightthickness=0,
            activebackground=self.accent,
            length=205
        )
        scale.pack(fill="x")

    # -----------------------------------
    # IMAGE PREVIEW
    # -----------------------------------

    def create_preview(self, parent, title, column):

        card = tk.Frame(parent, bg=self.panel)
        card.grid(
            row=0, column=column,
            sticky="nsew", padx=4
        )

        self.label(card, title, 11, True).pack(pady=14)

        image_label = tk.Label(
            card,
            text="Open an image to start editing",
            bg="#0b1324",
            fg=self.muted,
            font=("Segoe UI", 10)
        )
        image_label.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=(0, 10)
        )

        return image_label

    def display_image(self, image, panel):

        if image is None:
            panel.config(
                image="",
                text="Open an image to start editing"
            )
            panel.image = None
            return

        preview = image.copy()

        width = max(panel.winfo_width() - 20, 200)
        height = max(panel.winfo_height() - 20, 200)

        preview.thumbnail((width, height))

        photo = ImageTk.PhotoImage(preview)
        panel.configure(image=photo, text="")
        panel.image = photo

    def refresh_images(self):

        if self.original_image is None:
            return

        self.display_image(
            self.original_image,
            self.original_panel
        )

        if self.compare_mode:
            result = self.original_image
        elif self.preview_image is not None:
            result = self.preview_image
        else:
            result = self.processed_image

        self.display_image(result, self.processed_panel)

    # -----------------------------------
    # OPEN / SAVE
    # -----------------------------------

    def open_image(self):

        path = filedialog.askopenfilename(
            filetypes=[
                ("Image Files", "*.jpg *.jpeg *.png"),
                ("All Files", "*.*")
            ]
        )

        if not path:
            return

        try:
            with Image.open(path) as img:
                image = img.convert("RGB").copy()

            self.original_image = image.copy()
            self.processed_image = image.copy()
            self.preview_image = None
            self.compare_mode = False
            self.history.clear()
            self.redo_history.clear()
            self.file_path = path

            self.reset_sliders()
            self.refresh_images()

            w, h = image.size
            self.image_info.config(text=f"{w} x {h}")
            self.status.config(text=f"Loaded: {path}")

        except Exception as error:
            messagebox.showerror("Error", str(error))

    def save_image(self):

        if not self.check_image():
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[
                ("PNG Image", "*.png"),
                ("JPEG Image", "*.jpg")
            ]
        )

        if path:
            try:
                self.processed_image.save(path)
                self.status.config(text=f"Saved: {path}")
            except Exception as error:
                messagebox.showerror("Save Error", str(error))

    # -----------------------------------
    # HISTORY
    # -----------------------------------

    def check_image(self):

        if self.processed_image is None:
            messagebox.showwarning(
                "No Image",
                "Please open an image first."
            )
            return False

        return True

    def save_history(self):

        self.history.append(self.processed_image.copy())
        self.redo_history.clear()

        if len(self.history) > 20:
            self.history.pop(0)

    def commit(self, image, action):

        self.save_history()
        self.processed_image = image.convert("RGB")
        self.preview_image = None
        self.compare_mode = False

        self.reset_sliders()
        self.refresh_images()

        self.status.config(text=f"Applied: {action}")

        w, h = self.processed_image.size
        self.image_info.config(text=f"{w} x {h}")

    def undo(self):

        if self.history:
            self.redo_history.append(
                self.processed_image.copy()
            )
            self.processed_image = self.history.pop()
            self.preview_image = None
            self.reset_sliders()
            self.refresh_images()
            self.status.config(text="Undo completed")

    def redo(self):

        if self.redo_history:
            self.history.append(
                self.processed_image.copy()
            )
            self.processed_image = self.redo_history.pop()
            self.preview_image = None
            self.reset_sliders()
            self.refresh_images()
            self.status.config(text="Redo completed")

    def reset_image(self):

        if self.original_image is not None:
            self.commit(
                self.original_image.copy(),
                "Reset to Original"
            )

    def toggle_comparison(self):

        if not self.check_image():
            return

        self.compare_mode = not self.compare_mode
        self.refresh_images()

        self.status.config(
            text="Showing original" if self.compare_mode
            else "Showing edited result"
        )

    # -----------------------------------
    # BASIC PROCESSING
    # -----------------------------------

    def apply_basic(self, operation):

        if not self.check_image():
            return

        if operation == "RGB Channels":
            self.show_rgb_channels()
            return

        try:
            result = process_image(
                self.processed_image,
                operation,
                threshold=127
            )
            self.commit(result, operation)

        except Exception as error:
            messagebox.showerror(
                "Processing Error", str(error)
            )

    # -----------------------------------
    # LIVE ADJUSTMENTS
    # -----------------------------------

    def build_adjusted_image(self):

        img = self.processed_image.copy()
        values = {
            name: variable.get()
            for name, variable in self.adjustments.items()
        }

        brightness = max(0.01, 1 + values["Brightness"] / 100)
        contrast = max(0.01, 1 + values["Contrast"] / 100)
        saturation = max(0, 1 + values["Saturation"] / 100)
        sharpness = max(0, 1 + values["Sharpness"] / 50)

        img = ImageEnhance.Brightness(img).enhance(brightness)
        img = ImageEnhance.Contrast(img).enhance(contrast)
        img = ImageEnhance.Color(img).enhance(saturation)
        img = ImageEnhance.Sharpness(img).enhance(sharpness)

        warmth = values["Warmth"]

        if warmth != 0:
            data = np.array(img).astype(np.int16)
            data[:, :, 0] += warmth // 2
            data[:, :, 2] -= warmth // 2
            data = np.clip(data, 0, 255).astype(np.uint8)
            img = Image.fromarray(data)

        return img

    def preview_adjustments(self):

        if self.processed_image is None:
            return

        self.preview_image = self.build_adjusted_image()
        self.compare_mode = False
        self.refresh_images()

    def apply_adjustments(self):

        if not self.check_image():
            return

        result = self.build_adjusted_image()
        self.commit(result, "Tune Image")

    def reset_sliders(self):

        for variable in self.adjustments.values():
            variable.set(0)

        self.preview_image = None

        if self.processed_image is not None:
            self.refresh_images()

    # -----------------------------------
    # TRANSFORM
    # -----------------------------------

    def transform(self, action):

        if not self.check_image():
            return

        img = self.processed_image.copy()

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
                new_w = int(h * 16 / 9)
                box = ((w - new_w) // 2, 0,
                       (w + new_w) // 2, h)
            else:
                new_h = int(w * 9 / 16)
                box = (0, (h - new_h) // 2,
                       w, (h + new_h) // 2)
            img = img.crop(box)

        elif action == "resize":
            w, h = img.size
            img = img.resize(
                (max(1, w // 2), max(1, h // 2)),
                Image.Resampling.LANCZOS
            )

        self.commit(img, action)

    # -----------------------------------
    # FILTER PRESETS
    # -----------------------------------

    def apply_filter(self, name):

        if not self.check_image():
            return

        img = self.processed_image.copy()

        if name == "Portrait":
            img = ImageEnhance.Brightness(img).enhance(1.08)
            img = ImageEnhance.Color(img).enhance(0.92)

        elif name == "Vintage":
            img = ImageEnhance.Color(img).enhance(0.65)
            data = np.array(img).astype(np.int16)
            data[:, :, 0] += 18
            data[:, :, 1] += 8
            data[:, :, 2] -= 12
            img = Image.fromarray(
                np.clip(data, 0, 255).astype(np.uint8)
            )

        elif name == "Warm":
            data = np.array(img).astype(np.int16)
            data[:, :, 0] += 20
            data[:, :, 2] -= 14
            img = Image.fromarray(
                np.clip(data, 0, 255).astype(np.uint8)
            )

        elif name == "Cool":
            data = np.array(img).astype(np.int16)
            data[:, :, 0] -= 12
            data[:, :, 2] += 20
            img = Image.fromarray(
                np.clip(data, 0, 255).astype(np.uint8)
            )

        elif name == "Cinematic":
            img = ImageEnhance.Contrast(img).enhance(1.25)
            img = ImageEnhance.Color(img).enhance(0.8)

        elif name == "Black & White":
            img = ImageOps.grayscale(img).convert("RGB")

        self.commit(img, f"{name} Filter")

    # -----------------------------------
    # DETAILS & EFFECTS
    # -----------------------------------

    def apply_effect(self, effect):

        if not self.check_image():
            return

        img = self.processed_image.copy()

        if effect == "sharpen":
            img = img.filter(ImageFilter.UnsharpMask(
                radius=2, percent=150, threshold=3
            ))

        elif effect == "blur":
            img = img.filter(ImageFilter.GaussianBlur(3))

        elif effect == "smooth":
            img = img.filter(ImageFilter.MedianFilter(3))

        elif effect == "vignette":
            arr = np.array(img).astype(np.float32)
            h, w = arr.shape[:2]
            yy, xx = np.ogrid[-1:1:complex(h),
                              -1:1:complex(w)]
            distance = xx * xx + yy * yy
            mask = np.clip(1 - distance * 0.35, 0.35, 1)
            arr *= mask[:, :, None]
            img = Image.fromarray(
                np.clip(arr, 0, 255).astype(np.uint8)
            )

        self.commit(img, effect)

    # -----------------------------------
    # RGB CHANNELS
    # -----------------------------------

    def show_rgb_channels(self):

        if not self.check_image():
            return

        window = tk.Toplevel(self.root)
        window.title("RGB Channel Split")
        window.geometry("960x380")
        window.configure(bg=self.bg)

        data = np.array(self.processed_image)

        for index, name in enumerate(["Red", "Green", "Blue"]):
            channel = np.zeros_like(data)
            channel[:, :, index] = data[:, :, index]

            img = Image.fromarray(channel)
            img.thumbnail((280, 280))
            photo = ImageTk.PhotoImage(img)

            frame = tk.Frame(window, bg=self.panel)
            frame.pack(side="left", expand=True,
                       fill="both", padx=8, pady=12)

            tk.Label(
                frame, text=f"{name} Channel",
                fg="white", bg=self.panel
            ).pack(pady=10)

            label = tk.Label(frame, image=photo, bg=self.panel)
            label.image = photo
            label.pack(expand=True)

    # -----------------------------------
    # HISTOGRAM
    # -----------------------------------

    def show_histogram(self):

        if not self.check_image():
            return

        try:
            import matplotlib.pyplot as plt

            fig, axes = plt.subplots(1, 2, figsize=(11, 4))

            for ax, img, title in zip(
                axes,
                [self.original_image, self.processed_image],
                ["Original Histogram", "Processed Histogram"]
            ):
                array = np.array(img)

                for channel, color in enumerate(["red", "green", "blue"]):
                    hist = cv2.calcHist(
                        [array], [channel], None, [256], [0, 256]
                    )
                    ax.plot(hist, color=color, label=color.title())

                ax.set_title(title)
                ax.set_xlabel("Pixel Intensity")
                ax.set_ylabel("Pixel Count")
                ax.legend()

            fig.tight_layout()
            plt.show()

        except Exception as error:
            messagebox.showerror("Histogram Error", str(error))

    # -----------------------------------
    # IMAGE PROFILE
    # -----------------------------------

    def show_profile(self):

        if not self.check_image():
            return

        try:
            import matplotlib.pyplot as plt

            img = np.array(self.processed_image.convert("L"))
            middle_row = img[img.shape[0] // 2, :]

            plt.figure(figsize=(9, 4))
            plt.plot(middle_row, color="black")
            plt.title("Horizontal Pixel Intensity Profile")
            plt.xlabel("Pixel Position")
            plt.ylabel("Intensity")
            plt.ylim(0, 255)
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.show()

        except Exception as error:
            messagebox.showerror("Profile Error", str(error))


if __name__ == "__main__":
    root = tk.Tk()
    app = DIPLabStudio(root)
    root.mainloop()
