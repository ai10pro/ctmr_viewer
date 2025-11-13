import tkinter as tk
from tkinter import filedialog, messagebox, Menu, Scale, Toplevel, Text, Scrollbar, PanedWindow, Frame, Label
import pydicom
import os
from PIL import Image, ImageTk
import numpy as np

# Try to import tkinterdnd2, but make it optional
try:
    from tkinterdnd2 import DND_FILES, TkinterDND
    DND_SUPPORT = True
except ImportError:
    DND_SUPPORT = False

class DICOMViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Advanced DICOM Viewer v1.2")
        self.root.geometry("1200x800")

        self.files, self.ds = [], None
        self.index = 0
        self.pixel_min, self.pixel_max = 0, 4095

        self.ww = tk.DoubleVar(value=400)
        self.wl = tk.DoubleVar(value=40)
        self._last_x, self._last_y = 0, 0

        self.zoom_factor, self.pan_x, self.pan_y = 1.0, 0, 0

        self.create_menu()
        self.setup_ui()

        if DND_SUPPORT:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind('<<Drop>>', self.handle_drop)
        else:
            print("Notice: tkinterdnd2 not found. Drag and drop will be disabled.")

    def setup_ui(self):
        m = PanedWindow(self.root, sashrelief=tk.RAISED)
        m.pack(fill=tk.BOTH, expand=1)

        # --- Left Pane ---
        left_pane = Frame(m, width=350)
        m.add(left_pane, stretch="never")

        tk.Label(left_pane, text="Advanced DICOM Viewer", font=("Arial", 14, "bold")).pack(pady=10)
        
        info_frame = Frame(left_pane, height=200)
        info_frame.pack(fill=tk.X, padx=5, pady=5)
        info_frame.pack_propagate(False)
        self.info_text = Text(info_frame, wrap=tk.NONE, font=("Arial", 9))
        v_scroll = Scrollbar(info_frame, orient=tk.VERTICAL, command=self.info_text.yview)
        self.info_text.configure(yscrollcommand=v_scroll.set)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.info_text.pack(expand=True, fill=tk.BOTH)
        self.info_text.config(state=tk.DISABLED)

        control_frame = Frame(left_pane)
        control_frame.pack(fill=tk.X, padx=5, pady=10)
        tk.Button(control_frame, text="自動輝度調整", command=self.auto_adjust_wwl).pack(fill=tk.X, pady=5)
        
        Label(control_frame, text="ウィンドウ幅 (WW)").pack()
        self.ww_slider = Scale(control_frame, from_=1, to=4095, orient=tk.HORIZONTAL, variable=self.ww, command=self.on_wwl_change)
        self.ww_slider.pack(fill=tk.X)
        
        Label(control_frame, text="ウィンドウレベル (WL)").pack()
        self.wl_slider = Scale(control_frame, from_=-1024, to=3071, orient=tk.HORIZONTAL, variable=self.wl, command=self.on_wwl_change)
        self.wl_slider.pack(fill=tk.X)

        # --- Right Pane ---
        right_pane = Frame(m)
        m.add(right_pane)

        self.image_label = tk.Label(right_pane)
        self.image_label.pack(pady=5, expand=True, fill=tk.BOTH)
        self.image_label.bind("<ButtonPress-1>", self.start_drag_wwl)
        self.image_label.bind("<B1-Motion>", self.drag_image_wwl)
        self.image_label.bind("<ButtonPress-3>", self.start_drag_pan)
        self.image_label.bind("<B3-Motion>", self.drag_image_pan)
        self.image_label.bind("<MouseWheel>", self.zoom_image)
        self.image_label.bind("<Configure>", lambda e: self.update_image())

        self.slice_slider = Scale(right_pane, from_=0, to=0, orient=tk.HORIZONTAL, command=self.on_slider_change, showvalue=0)
        self.slice_slider.pack(fill=tk.X, padx=10, pady=2)
        self.create_buttons(right_pane)
        
        self.root.bind("<Left>", lambda e: self.prev_image())
        self.root.bind("<Right>", lambda e: self.next_image())

    def create_menu(self):
        menubar = Menu(self.root)
        filemenu = Menu(menubar, tearoff=0)
        filemenu.add_command(label="フォルダを開く...", command=self.load_dicom_folder_dialog)
        filemenu.add_separator()
        filemenu.add_command(label="終了", command=self.root.quit)
        menubar.add_cascade(label="ファイル", menu=filemenu)
        viewmenu = Menu(menubar, tearoff=0)
        viewmenu.add_command(label="DICOMヘッダ全体を表示", command=self.show_full_dicom_header)
        menubar.add_cascade(label="表示", menu=viewmenu)
        self.root.config(menu=menubar)

    def create_buttons(self, parent):
        button_frame = Frame(parent)
        button_frame.pack(pady=5)
        tk.Button(button_frame, text="← 前へ", command=self.prev_image).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="次へ →", command=self.next_image).pack(side=tk.LEFT, padx=5)

    def handle_drop(self, event):
        if not DND_SUPPORT: return
        path = event.data.strip("{} ")
        if os.path.isdir(path):
            self.load_dicom_folder(path)
        else:
            messagebox.showwarning("ドラッグ＆ドロップ", "フォルダをドロップしてください。")

    def load_dicom_folder_dialog(self):
        folder_path = filedialog.askdirectory(initialdir=".")
        if folder_path:
            self.load_dicom_folder(folder_path)

    def load_dicom_folder(self, folder_path):
        self.files = sorted([os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith('.dcm')])
        if not self.files:
            return messagebox.showerror("エラー", "DICOMファイルが見つかりませんでした。")
        self.index = 0
        self.slice_slider.config(from_=0, to=len(self.files) - 1)
        self.load_image(is_new_series=True)

    def load_image(self, is_new_series=False):
        if not self.files: return
        try:
            self.ds = pydicom.dcmread(self.files[self.index])
            pixel_array = self.ds.pixel_array.astype(float)
            if "RescaleSlope" in self.ds and "RescaleIntercept" in self.ds:
                pixel_array = pixel_array * self.ds.RescaleSlope + self.ds.RescaleIntercept
            
            if is_new_series:
                self.pixel_min = int(pixel_array.min())
                self.pixel_max = int(pixel_array.max())
                self.wl_slider.config(from_=self.pixel_min, to=self.pixel_max)
                self.ww_slider.config(to=self.pixel_max - self.pixel_min)
                self.auto_adjust_wwl()
            else:
                self.on_wwl_change()
            
            self.zoom_factor, self.pan_x, self.pan_y = 1.0, 0, 0
            self.slice_slider.set(self.index)
        except Exception as e:
            messagebox.showerror("読み込みエラー", f"ファイル '{os.path.basename(self.files[self.index])}' の読み込みエラー: {e}")

    def auto_adjust_wwl(self):
        if self.ds is None: return
        pixel_array = self.ds.pixel_array.astype(float)
        if "RescaleSlope" in self.ds and "RescaleIntercept" in self.ds:
            pixel_array = pixel_array * self.ds.RescaleSlope + self.ds.RescaleIntercept
        
        p1 = np.percentile(pixel_array, 1)
        p99 = np.percentile(pixel_array, 99)
        
        self.ww.set(p99 - p1)
        self.wl.set((p99 + p1) / 2)
        self.on_wwl_change()

    def on_wwl_change(self, _=None):
        self.update_image()
        self.update_info_panel()

    def update_image(self):
        if self.ds is None or self.image_label.winfo_width() <= 1: return
        try:
            pixel_array = self.ds.pixel_array.astype(float)
            if "RescaleSlope" in self.ds and "RescaleIntercept" in self.ds:
                pixel_array = pixel_array * self.ds.RescaleSlope + self.ds.RescaleIntercept

            ww, wl = self.ww.get(), self.wl.get()
            lower, upper = wl - ww / 2, wl + ww / 2
            
            np.clip(pixel_array, lower, upper, out=pixel_array)
            if upper > lower:
                pixel_array = (pixel_array - lower) / (upper - lower) * 255
            else:
                pixel_array.fill(0)
            img_data = pixel_array.astype(np.uint8)
            pil_img = Image.fromarray(img_data)

            container_w, container_h = self.image_label.winfo_width(), self.image_label.winfo_height()
            img_w, img_h = pil_img.size
            scale = min(container_w / img_w, container_h / img_h) if img_w > 0 and img_h > 0 else 1
            new_w, new_h = int(img_w * scale * self.zoom_factor), int(img_h * scale * self.zoom_factor)
            
            if new_w <= 0 or new_h <= 0: return
            resized_img = pil_img.resize((new_w, new_h), Image.LANCZOS)
            display_img = Image.new("L", (container_w, container_h), 0)
            paste_x = (container_w - new_w) // 2 + self.pan_x
            paste_y = (container_h - new_h) // 2 + self.pan_y
            display_img.paste(resized_img, (paste_x, paste_y))

            imgtk = ImageTk.PhotoImage(image=display_img)
            self.image_label.config(image=imgtk)
            self.image_label.image = imgtk
        except Exception:
            pass

    def update_info_panel(self):
        if self.ds is None: return
        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete(1.0, tk.END)
        info = {
            "ファイル名": os.path.basename(self.files[self.index]),
            "スライス": f"{self.index + 1}/{len(self.files)}",
            "患者名": getattr(self.ds, 'PatientName', 'N/A'),
            "患者ID": getattr(self.ds, 'PatientID', 'N/A'),
            "撮影日": getattr(self.ds, 'StudyDate', 'N/A'),
            "WW/WL": f"{int(self.ww.get())}/{int(self.wl.get())}",
            "ズーム": f"{self.zoom_factor:.2f}"
        }
        for key, value in info.items():
            self.info_text.insert(tk.END, f"{key}: {value}\n")
        self.info_text.config(state=tk.DISABLED)

    def show_full_dicom_header(self):
        if self.ds is None: return messagebox.showinfo("情報", "DICOMファイルが読み込まれていません。")
        header_window = Toplevel(self.root)
        header_window.title(f"DICOMヘッダ全体 - {os.path.basename(self.files[self.index])}")
        header_window.geometry("600x800")
        text_widget = Text(header_window, wrap=tk.NONE)
        v_scroll = Scrollbar(header_window, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=v_scroll.set)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        text_widget.pack(expand=True, fill=tk.BOTH)
        text_widget.insert(tk.END, str(self.ds))
        text_widget.config(state=tk.DISABLED)

    def on_slider_change(self, value):
        new_index = int(value)
        if new_index != self.index:
            self.index = new_index
            self.load_image()

    def start_drag_wwl(self, event): self._last_x, self._last_y = event.x, event.y
    def drag_image_wwl(self, event):
        dx, dy = event.x - self._last_x, event.y - self._last_y
        self.ww.set(self.ww.get() + dx)
        self.wl.set(self.wl.get() - dy)
        self._last_x, self._last_y = event.x, event.y
        self.on_wwl_change()

    def start_drag_pan(self, event): self._last_x, self._last_y = event.x, event.y
    def drag_image_pan(self, event):
        dx, dy = event.x - self._last_x, event.y - self._last_y
        self.pan_x += dx
        self.pan_y += dy
        self._last_x, self._last_y = event.x, event.y
        self.update_image()

    def zoom_image(self, event):
        if event.delta > 0: self.zoom_factor *= 1.1
        else: self.zoom_factor /= 1.1
        self.update_image()
        self.update_info_panel()

    def next_image(self):
        if self.index < len(self.files) - 1:
            self.index += 1
            self.load_image()

    def prev_image(self):
        if self.index > 0:
            self.index -= 1
            self.load_image()

if __name__ == "__main__":
    # Use regular Tk if DND is not supported
    root = TkinterDND.Tk() if DND_SUPPORT else tk.Tk()
    app = DICOMViewer(root)
    root.mainloop()

