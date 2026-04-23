# -*- coding: utf-8 -*-
# ShelfReady Unified GUI
import os, sys, subprocess, json, threading, tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk

PY = sys.executable

# ── Before/after state ────────────────────────────────────────────────────────
_orig_path = None
_proc_path = None
_showing_orig = False

# ── Queue state ───────────────────────────────────────────────────────────────
_queue_files = []

# ── Platform presets ──────────────────────────────────────────────────────────
PLATFORM_PRESETS = {
    "Custom":  {},
    "Amazon":  {"size": "2000", "quality": "95"},
    "Shopify": {"size": "2048", "quality": "90"},
    "eBay":    {"size": "1600", "quality": "85"},
    "Etsy":    {"size": "2000", "quality": "90"},
    "Walmart": {"size": "2000", "quality": "95"},
}

# ── Palette ───────────────────────────────────────────────────────────────────
NAVY      = "#1a3a6b"
NAVY_DARK = "#0f2548"
NAVY_LT   = "#2b4c8c"
SLATE     = "#111e2e"
SLATE_MD  = "#0e1929"
GREY      = "#b0bccb"
GREY_LT   = "#e2e8f0"
BG        = "#f0f2f5"
PANEL     = "#ffffff"
BLACK     = "#0d1117"
WHITE     = "#ffffff"
LOG_BG    = "#0d1117"
LOG_FG    = "#8b9db8"
TEAL      = "#2e9fa5"

# ── Fonts ─────────────────────────────────────────────────────────────────────
F_HEAD = ("Arial", 13, "bold")
F_SEC  = ("Arial",  9, "bold")
F_LBL  = ("Arial",  8)
F_TINY = ("Arial",  7)
F_ENT  = ("Arial",  9)
F_RUN  = ("Arial", 12, "bold")
F_MONO = ("Courier", 8)

# ── Widget helpers ────────────────────────────────────────────────────────────

def sec(parent, title):
    outer = tk.Frame(parent, bg=BG)
    outer.pack(fill="x", padx=6, pady=(5, 0))
    hdr = tk.Frame(outer, bg=NAVY)
    hdr.pack(fill="x")
    tk.Label(hdr, text=title, bg=NAVY, fg=WHITE,
             font=F_SEC, anchor="w", padx=10, pady=5).pack(side="left")
    body = tk.Frame(outer, bg=PANEL,
                    highlightbackground=GREY, highlightthickness=1)
    body.pack(fill="x")
    return body


def mkl(parent, text, small=False):
    return tk.Label(parent, text=text, bg=PANEL, fg=SLATE_MD,
                    font=F_TINY if small else F_LBL)


def mke(parent, var, width=20):
    return tk.Entry(parent, textvariable=var, width=width,
                    bg=PANEL, fg=BLACK, insertbackground=NAVY,
                    font=F_ENT, relief="flat",
                    highlightbackground=GREY, highlightthickness=1,
                    highlightcolor=NAVY)


def mkb(parent, text, cmd, emoji=False):
    return tk.Button(parent, text=text, command=cmd,
                     bg=GREY_LT, fg=SLATE,
                     activebackground=GREY, activeforeground=BLACK,
                     relief="flat", bd=0, cursor="hand2",
                     font=("Arial", 13) if emoji else F_LBL,
                     padx=4, pady=1)


def mkc(parent, text, var, accent=False):
    return tk.Checkbutton(parent, text=text, variable=var,
                          bg=PANEL, fg=NAVY if accent else SLATE,
                          activebackground=PANEL, selectcolor=PANEL,
                          font=(F_LBL[0], F_LBL[1], "bold") if accent else F_LBL)


def mko(parent, var, *vals):
    o = tk.OptionMenu(parent, var, *vals)
    o.config(bg=PANEL, fg=BLACK, activebackground=GREY_LT,
             relief="flat", font=F_ENT,
             highlightbackground=GREY, highlightthickness=1,
             highlightcolor=NAVY, padx=4)
    o["menu"].config(bg=PANEL, fg=BLACK, activebackground=NAVY,
                     activeforeground=WHITE, font=F_ENT)
    return o


def rule(parent):
    tk.Frame(parent, bg=GREY_LT, height=1).pack(fill="x", padx=8, pady=2)


# ── Logic ─────────────────────────────────────────────────────────────────────

def run_cmd(args):
    try:
        r = subprocess.run(args, capture_output=True, text=True)
        out = (r.stdout or "") + ("\n" + r.stderr if r.stderr else "")
        return r.returncode, out.strip()
    except Exception as e:
        return 1, str(e)


def update_preview(path):
    try:
        img = Image.open(path)
        img.thumbnail((800, 800), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        cw = max(preview_canvas.winfo_width(), 400)
        ch = max(preview_canvas.winfo_height(), 400)
        preview_canvas.delete("all")
        preview_canvas.create_image(cw // 2, ch // 2, image=photo, anchor="center")
        preview_canvas.image = photo
        preview_name_lbl.config(text=f"  {os.path.basename(path)}")
    except Exception as e:
        preview_name_lbl.config(text=f"  Error loading preview: {e}")


def _toggle_btn_sync():
    if _orig_path and _proc_path:
        toggle_btn.config(state="normal")
    else:
        toggle_btn.config(state="disabled",
                          text="BEFORE", bg=SLATE_MD, fg=GREY)


def toggle_preview():
    global _showing_orig
    if _showing_orig:
        if _proc_path:
            update_preview(_proc_path)
            toggle_btn.config(text="BEFORE", bg=NAVY_LT, fg=WHITE)
            _showing_orig = False
    else:
        if _orig_path:
            update_preview(_orig_path)
            toggle_btn.config(text="AFTER", bg=TEAL, fg=WHITE)
            _showing_orig = True


def apply_platform(*_):
    p = PLATFORM_PRESETS.get(v_platform.get(), {})
    if "size"    in p: v_sz.set(p["size"])
    if "quality" in p: v_qual.set(p["quality"])


def pick(var, fn, is_input=False):
    global _orig_path, _proc_path, _showing_orig
    p = fn()
    if not p:
        return
    var.set(p)
    if is_input and var is v_in_file:
        try:
            with Image.open(p) as im:
                w, h = im.size
            v_size.set(f"Input: {w} × {h} px  |  Canvas: {v_sz.get()} px")
            update_preview(p)
        except Exception:
            v_size.set("")
        _orig_path = p
        _proc_path = None
        _showing_orig = False
        toggle_btn.config(text="BEFORE", bg=SLATE_MD, fg=GREY, state="disabled")
    elif is_input and var is v_in_dir:
        _populate_queue(p)
    elif is_input and var is v_in_zip:
        queue_count_lbl.config(text="ZIP selected — queue after processing")
        queue_frame.pack(fill="x", padx=0, pady=(4, 0))


def pick_out_file():
    p = filedialog.asksaveasfilename(
        defaultextension=".jpg",
        filetypes=[("JPEG", "*.jpg"), ("PNG", "*.png"),
                   ("WebP", "*.webp"), ("All Files", "*.*")])
    if p:
        v_out_file.set(p)


def _populate_queue(folder_path):
    global _queue_files
    exts = ('.jpg', '.jpeg', '.png', '.webp', '.bmp',
            '.gif', '.tif', '.tiff', '.heic', '.avif', '.jfif')
    _queue_files = sorted([
        os.path.join(folder_path, f)
        for f in os.listdir(folder_path)
        if os.path.isfile(os.path.join(folder_path, f))
        and f.lower().endswith(exts)
    ])
    queue_lb.delete(0, "end")
    for f in _queue_files:
        queue_lb.insert("end", os.path.basename(f))
    queue_count_lbl.config(text=f"{len(_queue_files)} image(s) queued")
    if _queue_files:
        queue_lb.selection_set(0)
        update_preview(_queue_files[0])
        preview_name_lbl.config(text=f"  {os.path.basename(_queue_files[0])}")
    queue_frame.pack(fill="x", padx=0, pady=(4, 0))


def _on_queue_select(event):
    sel = queue_lb.curselection()
    if sel:
        path = _queue_files[sel[0]]
        update_preview(path)


def do_run():
    script = os.path.join(os.path.dirname(__file__), "image_toolkit.py")
    if not os.path.exists(script):
        messagebox.showerror("Error", f"image_toolkit.py not found:\n{script}")
        return

    args = [PY, script,
            "--op",               v_op.get(),
            "--work_on",          v_work.get(),
            "--fit_mode",         v_fit.get(),
            "--size",             v_sz.get(),
            "--margin_pct",       v_margin.get(),
            "--min_top_pad_px",   v_tpad.get(),
            "--vertical_bias",    v_vbias.get(),
            "--product_contrast", v_cont.get(),
            "--sharpen_radius",   v_shr.get(),
            "--sharpen_percent",  v_shp.get(),
            "--sharpen_threshold",v_sht.get(),
            "--dehalo_px",        v_deh.get(),
            "--edge_feather",     v_edge.get(),
            "--top_clean_pct",    v_tcln.get(),
            "--white_floor",      v_wfl.get(),
            "--neutrality_tol",   v_neut.get(),
            "--target_fill",      v_fill.get(),
            "--quality",          v_qual.get(),
            "--mode",             v_mode.get(),
            ]

    if v_nd.get():   args.append("--no_downscale")
    if v_nbg.get():  args.append("--no_bg_clean")
    if v_up.get():   args.append("--allow_upscale")
    if v_nls.get():  args.append("--no_largest_scrub")
    if v_npr.get():  args.append("--no_progressive")
    if v_nop.get():  args.append("--no_optimize")
    if v_dpi.get():  args += ["--set_dpi", v_dpival.get()]
    if v_shd.get():  args += ["--add_shadow", "--shadow_alpha", v_shdal.get()]
    if v_qty.get() and v_qtytxt.get().strip():
        args += ["--qty_badge", v_qtytxt.get().strip()]
    if v_qc.get():
        args += ["--qc", "--qc_mode", v_qcmode.get()]

    # Batch rename
    if v_rename_prefix.get().strip():
        args += ["--out_prefix", v_rename_prefix.get().strip()]
    if v_rename_suffix.get().strip():
        args += ["--out_suffix", v_rename_suffix.get().strip()]

    out_path = None
    out_zip_result = None
    if v_in_file.get():
        args += ["--in", v_in_file.get()]
        if v_out_file.get():
            ov = v_out_file.get()
            if os.path.isdir(ov):
                name = os.path.splitext(os.path.basename(v_in_file.get()))[0]
                ov = os.path.join(ov, f"{name}_processed.jpg")
                v_out_file.set(ov)
            args += ["--out", ov]
            out_path = ov
    elif v_in_dir.get():
        args += ["--in_dir", v_in_dir.get()]
        if v_out_dir.get():
            args += ["--out_dir", v_out_dir.get()]
    elif v_in_zip.get():
        args += ["--in_zip", v_in_zip.get()]
        # Always resolve output ZIP path — default next to input if not set
        oz = v_out_zip.get().strip()
        if not oz:
            base = os.path.splitext(v_in_zip.get())[0]
            oz = base + "_processed.zip"
            v_out_zip.set(oz)
        args += ["--out_zip", oz]
        out_zip_result = oz
    else:
        messagebox.showerror("Error", "Select an input (file / folder / zip).")
        return

    run_btn.config(state="disabled", bg=SLATE_MD, cursor="",
                   text="  PROCESSING…")

    def worker():
        code, output = run_cmd(args)
        root.after(0, lambda: _finish(code, output, out_path, out_zip_result))

    threading.Thread(target=worker, daemon=True).start()


def _finish(code, output, out_path, out_zip=None):
    global _proc_path, _showing_orig

    log.config(state="normal")
    log.delete("1.0", "end")
    log.insert("end", "$ image_toolkit [args]\n\n", "cmd")
    log.insert("end", output)

    if v_qc.get() and "QC_RESULT:" in output:
        try:
            qs = output.index("QC_RESULT:") + 10
            qe = output.index(":END_QC_RESULT")
            qd = json.loads(output[qs:qe])
            passed = qd.get("passed", False)
            score  = qd.get("score", 0)
            log.insert("end", f"\n{'─' * 52}\n", "div")
            log.insert("end",
                       f"  QC {'PASSED' if passed else 'FAILED'}   "
                       f"Score: {score:.0f} / 100\n",
                       "qcpass" if passed else "qcfail")
            if qd.get("adjustments"):
                log.insert("end", "\n  Adaptive Adjustments:\n", "info")
                for a in qd["adjustments"]:
                    log.insert("end",
                               f"    {a['param']}: {a['from']} -> {a['to']}\n")
            if qd.get("issues"):
                log.insert("end",
                           f"\n  Issues ({len(qd['issues'])}):\n", "info")
                for i in qd["issues"]:
                    sv  = i.get("severity", "").upper()
                    tag = {"CRITICAL": "crit", "ERROR": "err",
                           "WARNING": "warn"}.get(sv, "")
                    log.insert("end",
                               f"    [{sv}] {i.get('code','')}: "
                               f"{i.get('message','')}\n", tag)
            log.insert("end", f"{'─' * 52}\n", "div")
        except Exception as e:
            log.insert("end", f"\n[QC parse error: {e}]\n")

    if code == 0 and out_zip and os.path.exists(out_zip):
        log.insert("end", f"\n{'─' * 52}\n", "div")
        log.insert("end", f"  ZIP saved → {out_zip}\n", "info")
        log.insert("end", f"{'─' * 52}\n", "div")

    log.config(state="disabled")
    log.see("end")

    if code == 0 and out_path and os.path.exists(out_path):
        _proc_path = out_path
        _showing_orig = False
        update_preview(out_path)
        toggle_btn.config(text="BEFORE", bg=NAVY_LT, fg=WHITE, state="normal")
        try:
            with Image.open(out_path) as im:
                in_txt = v_size.get().split("|")[0].strip()
                v_size.set(f"{in_txt}  |  Output: {im.size[0]} × {im.size[1]} px")
        except Exception:
            pass

    run_btn.config(state="normal", bg=NAVY, cursor="hand2",
                   text="  RUN PROCESSING")

    if code == 0 and out_zip:
        msg = f"Done!\n\nZIP saved to:\n{out_zip}"
    elif code == 0:
        msg = "Done!"
    else:
        msg = "Finished with errors — check the log."
    messagebox.showinfo("ShelfReady", msg)


# ── Window ────────────────────────────────────────────────────────────────────

root = tk.Tk()
root.title("ShelfReady")
root.geometry("1500x940")
root.configure(bg=BG)
root.minsize(1100, 700)

# Title bar
title_bar = tk.Frame(root, bg=NAVY_DARK)
title_bar.grid(row=0, column=0, columnspan=2, sticky="ew")
tk.Label(title_bar, text="  ShelfReady", bg=NAVY_DARK, fg=WHITE,
         font=F_HEAD, pady=10).pack(side="left")
tk.Label(title_bar, text="Product Image Toolkit",
         bg=NAVY_DARK, fg="#7ea7d8", font=("Arial", 9),
         pady=10).pack(side="left", padx=(8, 0))

# Columns
left  = tk.Frame(root, bg=BG)
right = tk.Frame(root, bg=BG)
left.grid( row=1, column=0, sticky="nsew", padx=(6, 3), pady=6)
right.grid(row=1, column=1, sticky="nsew", padx=(3, 6), pady=6)
root.grid_rowconfigure(1, weight=1)
root.grid_columnconfigure(0, weight=0, minsize=645)
root.grid_columnconfigure(1, weight=1)

# ── Variables ─────────────────────────────────────────────────────────────────

v_in_file  = tk.StringVar(); v_out_file = tk.StringVar()
v_in_dir   = tk.StringVar(); v_out_dir  = tk.StringVar()
v_in_zip   = tk.StringVar(); v_out_zip  = tk.StringVar()
v_size     = tk.StringVar(value="No file selected")

v_op   = tk.StringVar(value="both")
v_work = tk.StringVar(value="image")
v_fit  = tk.StringVar(value="pad")
v_mode = tk.StringVar(value="auto")

v_nd  = tk.BooleanVar()
v_nbg = tk.BooleanVar()
v_up  = tk.BooleanVar()
v_nls = tk.BooleanVar()
v_npr = tk.BooleanVar()
v_nop = tk.BooleanVar()
v_dpi = tk.BooleanVar()
v_shd = tk.BooleanVar()
v_qty = tk.BooleanVar()
v_qc  = tk.BooleanVar()

v_qtytxt  = tk.StringVar()
v_qcmode  = tk.StringVar(value="validate")
v_dpival  = tk.StringVar(value="300")
v_shdal   = tk.StringVar(value="70")

v_sz     = tk.StringVar(value="1500")
v_margin = tk.StringVar(value="0.015")
v_tpad   = tk.StringVar(value="120")
v_vbias  = tk.StringVar(value="0.58")
v_cont   = tk.StringVar(value="1.05")
v_shr    = tk.StringVar(value="1.3")
v_shp    = tk.StringVar(value="140")
v_sht    = tk.StringVar(value="2")
v_deh    = tk.StringVar(value="2")
v_edge   = tk.StringVar(value="1.0")
v_tcln   = tk.StringVar(value="0.08")
v_wfl    = tk.StringVar(value="245")
v_neut   = tk.StringVar(value="18")
v_fill   = tk.StringVar(value="0.84")
v_qual   = tk.StringVar(value="95")

v_platform      = tk.StringVar(value="Custom")
v_rename_prefix = tk.StringVar()
v_rename_suffix = tk.StringVar()

# ── PLATFORM PRESET ───────────────────────────────────────────────────────────

plat_bar = tk.Frame(left, bg=BG)
plat_bar.pack(fill="x", padx=6, pady=(6, 0))
tk.Label(plat_bar, text="Platform:", bg=BG, fg=SLATE_MD, font=F_LBL).pack(side="left", padx=(2, 4))
plat_menu = mko(plat_bar, v_platform, *PLATFORM_PRESETS.keys())
plat_menu.pack(side="left")
tk.Label(plat_bar, text="Canvas px:", bg=BG, fg=SLATE_MD, font=F_LBL).pack(side="left", padx=(14, 4))
sz_ent = tk.Entry(plat_bar, textvariable=v_sz, width=6,
                  bg=PANEL, fg=BLACK, font=F_ENT, relief="flat",
                  highlightbackground=GREY, highlightthickness=1,
                  highlightcolor=NAVY, insertbackground=NAVY)
sz_ent.pack(side="left")
tk.Label(plat_bar, text="Quality:", bg=BG, fg=SLATE_MD, font=F_LBL).pack(side="left", padx=(10, 4))
qual_ent = tk.Entry(plat_bar, textvariable=v_qual, width=4,
                    bg=PANEL, fg=BLACK, font=F_ENT, relief="flat",
                    highlightbackground=GREY, highlightthickness=1,
                    highlightcolor=NAVY, insertbackground=NAVY)
qual_ent.pack(side="left")
v_platform.trace_add("write", apply_platform)

# ── INPUT / OUTPUT ────────────────────────────────────────────────────────────

io = sec(left, "INPUT / OUTPUT")
io.grid_columnconfigure(2, weight=1)
io.grid_columnconfigure(5, weight=1)
P = {"padx": 4, "pady": 3}

_io_rows = [
    ("File",   v_in_file, lambda: pick(v_in_file, filedialog.askopenfilename, True),
               "💾", v_out_file, pick_out_file),
    ("Folder", v_in_dir,
               lambda: pick(v_in_dir, filedialog.askdirectory, True),
               "📁", v_out_dir,
               lambda: pick(v_out_dir, filedialog.askdirectory)),
    ("ZIP",    v_in_zip,
               lambda: pick(v_in_zip, lambda: filedialog.askopenfilename(
                   filetypes=[("ZIP", "*.zip")]), True),
               "🗜", v_out_zip,
               lambda: pick(v_out_zip, lambda: filedialog.asksaveasfilename(
                   defaultextension=".zip",
                   filetypes=[("ZIP", "*.zip")]))),
]
_icons = ["📄", "📁", "🗜"]

for r, (label, ivar, icmd, oicon, ovar, ocmd) in enumerate(_io_rows):
    mkb(io, _icons[r], icmd, emoji=True).grid(row=r, column=0, **P)
    mkl(io, label + ":").grid(row=r, column=1, sticky="e", **P)
    mke(io, ivar, 30).grid(row=r, column=2, sticky="ew", **P)
    tk.Label(io, text="->", bg=PANEL, fg=GREY,
             font=F_LBL).grid(row=r, column=3, **P)
    mkb(io, oicon, ocmd, emoji=True).grid(row=r, column=4, **P)
    mke(io, ovar, 24).grid(row=r, column=5, sticky="ew", **P)

# Rename row
rename_row = tk.Frame(io, bg=PANEL)
rename_row.grid(row=3, column=0, columnspan=6, sticky="ew", padx=4, pady=(2, 4))
tk.Label(rename_row, text="Batch rename — Prefix:", bg=PANEL, fg=SLATE_MD,
         font=F_LBL).pack(side="left", padx=(4, 2))
mke(rename_row, v_rename_prefix, 12).pack(side="left")
tk.Label(rename_row, text="Suffix:", bg=PANEL, fg=SLATE_MD,
         font=F_LBL).pack(side="left", padx=(10, 2))
mke(rename_row, v_rename_suffix, 12).pack(side="left")
tk.Label(rename_row, text="e.g. prefix=hero_  suffix=_clean  →  hero_name_clean.jpg",
         bg=PANEL, fg=GREY, font=F_TINY).pack(side="left", padx=(8, 0))

tk.Label(io, textvariable=v_size, bg=PANEL, fg=NAVY_LT,
         font=F_TINY).grid(row=4, column=0, columnspan=6, sticky="w", padx=8, pady=(0, 4))

# ── PROCESSING OPTIONS ────────────────────────────────────────────────────────

ops = sec(left, "PROCESSING OPTIONS")

# Auto-snap fill params when a fill mode is selected
def _on_fit_mode(*_):
    mode = v_fit.get()
    if mode == "fill_width":
        v_fill.set("0.99")
        v_margin.set("0.0")
        v_up.set(True)
    elif mode == "fill_height":
        v_fill.set("0.97")
        v_tpad.set("30")
        v_up.set(True)
    elif mode in ("pad", "fit"):
        v_fill.set("0.84")
        v_margin.set("0.015")
        v_tpad.set("120")
v_fit.trace_add("write", _on_fit_mode)

# Dropdowns
dd = tk.Frame(ops, bg=PANEL)
dd.pack(fill="x", padx=8, pady=(6, 2))
for i, (t, v, vals) in enumerate([
    ("Operation", v_op,   ["convert", "clean", "both"]),
    ("Work On",   v_work, ["image", "canvas"]),
    ("Fit Mode",  v_fit,  ["pad", "fit", "crop_fill", "fill_height", "fill_width"]),
    ("Mode",      v_mode, ["safe", "auto", "aggressive"]),
]):
    pad_left = 0 if i == 0 else 14
    mkl(dd, t + ":").grid(row=0, column=i * 2,     sticky="e", padx=(pad_left, 2))
    mko(dd, v, *vals).grid(row=0, column=i * 2 + 1, sticky="w", padx=(0, 2))

rule(ops)

# Numeric params — 4 per row (Size px removed; now in platform bar)
pf = tk.Frame(ops, bg=PANEL)
pf.pack(fill="x", padx=8, pady=2)
PARAMS = [
    ("Margin %",   v_margin), ("Top Pad px", v_tpad),   ("V.Bias",     v_vbias),  ("Contrast",   v_cont),
    ("Shp.Radius", v_shr),    ("Shp.%",      v_shp),    ("Shp.Thr",    v_sht),    ("Dehalo px",  v_deh),
    ("EdgeFeath",  v_edge),   ("TopClean %", v_tcln),   ("White Floor",v_wfl),    ("Neutrality", v_neut),
    ("Fill Ratio", v_fill),   ("Shdw Alpha", v_shdal),  ("DPI Value",  v_dpival),
]
for i, (t, v) in enumerate(PARAMS):
    c, row = (i % 4) * 2, i // 4
    mkl(pf, t + ":", small=True).grid(row=row, column=c,     sticky="e", padx=(4, 2), pady=1)
    mke(pf, v, 7).grid(          row=row, column=c + 1, sticky="w", padx=(0, 8),  pady=1)

rule(ops)

# Checkboxes — 4 per row
cf = tk.Frame(ops, bg=PANEL)
cf.pack(fill="x", padx=8, pady=2)
CHECKS = [
    ("No Downscale",     v_nd),  ("Skip BG Clean",  v_nbg),
    ("Allow Upscale",    v_up),  ("No Largest Scrub",v_nls),
    ("No Progressive",   v_npr), ("No Optimize",    v_nop),
    ("Set DPI",          v_dpi), ("Soft Shadow",    v_shd),
]
for i, (t, v) in enumerate(CHECKS):
    c, row = (i % 4) * 2, i // 4
    mkc(cf, t, v).grid(row=row, column=c, columnspan=2,
                       sticky="w", padx=2, pady=1)

rule(ops)

# Qty badge + QC
xf = tk.Frame(ops, bg=PANEL)
xf.pack(fill="x", padx=8, pady=(2, 6))

mkc(xf, "Quantity Badge", v_qty).grid(row=0, column=0, columnspan=2,
                                       sticky="w", pady=(0, 2))
mkl(xf, "Text:").grid(row=0, column=2, sticky="e", padx=(12, 2))
qty_ent = mke(xf, v_qtytxt, 10)
qty_ent.grid(row=0, column=3, sticky="w")
qty_ent.config(state="disabled")
mkl(xf, "e.g. 20 OZ", small=True).grid(row=0, column=4, sticky="w", padx=4)

def _toggle_qty(*_):
    qty_ent.config(state="normal" if v_qty.get() else "disabled")
v_qty.trace_add("write", _toggle_qty)

tk.Frame(xf, bg=GREY, height=1).grid(row=1, column=0, columnspan=6,
                                      sticky="ew", pady=(4, 3))

mkc(xf, "Enable QC Analysis", v_qc, accent=True).grid(
    row=2, column=0, columnspan=2, sticky="w")
mkl(xf, "Mode:").grid(row=2, column=2, sticky="e", padx=(12, 2))
mko(xf, v_qcmode, "validate", "adaptive", "strict").grid(
    row=2, column=3, sticky="w")
mkl(xf, "validate=report · adaptive=auto-fix · strict=fail",
    small=True).grid(row=2, column=4, sticky="w", padx=6)

# ── RUN ───────────────────────────────────────────────────────────────────────

rf = tk.Frame(left, bg=BG)
rf.pack(fill="x", padx=6, pady=8)
run_btn = tk.Button(rf, text="  RUN PROCESSING", command=do_run,
                    bg=NAVY, fg=WHITE,
                    activebackground=NAVY_DARK, activeforeground=WHITE,
                    font=F_RUN, relief="flat", height=2,
                    cursor="hand2")
run_btn.pack(fill="x")

# ── LOG ───────────────────────────────────────────────────────────────────────

log_outer = tk.Frame(left, bg=BG)
log_outer.pack(fill="both", expand=True, padx=6, pady=(0, 6))

log_hdr = tk.Frame(log_outer, bg=SLATE)
log_hdr.pack(fill="x")
tk.Label(log_hdr, text="PROCESSING LOG", bg=SLATE, fg=GREY_LT,
         font=F_SEC, anchor="w", padx=10, pady=4).pack(side="left")

log_body = tk.Frame(log_outer, bg=LOG_BG)
log_body.pack(fill="both", expand=True)

log = tk.Text(log_body, bg=LOG_BG, fg=LOG_FG, font=F_MONO,
              wrap="word", state="disabled", relief="flat",
              padx=8, pady=6,
              selectbackground=NAVY, selectforeground=WHITE,
              insertbackground=LOG_FG)
log_sb = tk.Scrollbar(log_body, command=log.yview, bg=SLATE,
                       troughcolor=LOG_BG)
log_sb.pack(side="right", fill="y")
log.config(yscrollcommand=log_sb.set)
log.pack(side="left", fill="both", expand=True)

log.tag_config("cmd",    foreground="#7ea7d8", font=("Courier", 8, "bold"))
log.tag_config("div",    foreground=SLATE_MD)
log.tag_config("info",   foreground="#7ea7d8")
log.tag_config("qcpass", foreground="#68d391", font=("Courier", 9, "bold"))
log.tag_config("qcfail", foreground="#fc8181", font=("Courier", 9, "bold"))
log.tag_config("crit",   foreground="#fc8181")
log.tag_config("err",    foreground="#f6ad55")
log.tag_config("warn",   foreground="#f6e05e")

# ── RIGHT: PREVIEW + QUEUE ────────────────────────────────────────────────────

right.grid_rowconfigure(1, weight=1)
right.grid_columnconfigure(0, weight=1)

# Preview header
prev_hdr = tk.Frame(right, bg=SLATE)
prev_hdr.grid(row=0, column=0, sticky="ew")

toggle_btn = tk.Button(prev_hdr, text="BEFORE",
                        command=toggle_preview,
                        bg=SLATE_MD, fg=GREY,
                        activebackground=NAVY_LT, activeforeground=WHITE,
                        relief="flat", bd=0, cursor="hand2",
                        font=("Arial", 8, "bold"), padx=8, pady=4,
                        state="disabled")
toggle_btn.pack(side="left", padx=(6, 2), pady=2)

preview_name_lbl = tk.Label(prev_hdr, text="  IMAGE PREVIEW",
                              bg=SLATE, fg=GREY_LT,
                              font=F_SEC, anchor="w", padx=4, pady=4)
preview_name_lbl.pack(side="left", fill="x", expand=True)

# Preview canvas
preview_canvas = tk.Canvas(right, bg=LOG_BG, relief="flat",
                             bd=0, highlightthickness=0)
preview_canvas.grid(row=1, column=0, sticky="nsew")

# Queue browser (hidden until folder/zip selected)
queue_frame = tk.Frame(right, bg=SLATE)

queue_hdr = tk.Frame(queue_frame, bg=SLATE)
queue_hdr.pack(fill="x")
tk.Label(queue_hdr, text="BATCH QUEUE", bg=SLATE, fg=GREY_LT,
         font=F_SEC, anchor="w", padx=10, pady=3).pack(side="left")
queue_count_lbl = tk.Label(queue_hdr, text="", bg=SLATE, fg=GREY,
                             font=F_TINY, padx=6)
queue_count_lbl.pack(side="left")

queue_body = tk.Frame(queue_frame, bg=LOG_BG)
queue_body.pack(fill="both", expand=True)

queue_sb = tk.Scrollbar(queue_body, bg=SLATE, troughcolor=LOG_BG)
queue_sb.pack(side="right", fill="y")

queue_lb = tk.Listbox(queue_body, bg=LOG_BG, fg=LOG_FG,
                       font=F_MONO, relief="flat", bd=0,
                       selectbackground=NAVY, selectforeground=WHITE,
                       activestyle="none", height=6,
                       yscrollcommand=queue_sb.set)
queue_lb.pack(side="left", fill="both", expand=True)
queue_sb.config(command=queue_lb.yview)
queue_lb.bind("<<ListboxSelect>>", _on_queue_select)

root.mainloop()
