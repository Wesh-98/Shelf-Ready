# ShelfReady Unified GUI
import os, sys, subprocess, json, tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk

PY = sys.executable

# ── Palette ──────────────────────────────────────────────────────────────────
NAVY      = "#1a3a6b"
NAVY_DARK = "#0f2548"
NAVY_LT   = "#2b4c8c"
SLATE     = "#1e2d40"
SLATE_MD  = "#1e293b"
GREY      = "#cbd5e0"
GREY_LT   = "#edf2f7"
BG        = "#f0f2f5"
PANEL     = "#ffffff"
BLACK     = "#1a202c"
WHITE     = "#ffffff"
LOG_BG    = "#0d1117"
LOG_FG    = "#8b9db8"

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
    """Navy-header panel. Returns white body frame, auto-packed into parent."""
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
        preview_lbl.config(text=f"  {os.path.basename(path)}")
    except Exception as e:
        preview_lbl.config(text=f"  Error loading preview: {e}")


def pick(var, fn, is_input=False):
    p = fn()
    if p:
        var.set(p)
        if is_input and var is v_in_file:
            try:
                with Image.open(p) as im:
                    w, h = im.size
                v_size.set(f"{w} x {h} px")
                update_preview(p)
            except Exception:
                v_size.set("")


def pick_out_file():
    p = filedialog.asksaveasfilename(
        defaultextension=".jpg",
        filetypes=[("JPEG", "*.jpg"), ("PNG", "*.png"),
                   ("WebP", "*.webp"), ("All Files", "*.*")])
    if p:
        v_out_file.set(p)


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

    out_path = None
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
        if v_out_zip.get():
            args += ["--out_zip", v_out_zip.get()]
    else:
        messagebox.showerror("Error", "Select an input (file / folder / zip).")
        return

    code, output = run_cmd(args)

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

    log.config(state="disabled")
    log.see("end")

    if code == 0 and out_path and os.path.exists(out_path):
        update_preview(out_path)
        try:
            with Image.open(out_path) as im:
                v_size.set(f"Output: {im.size[0]} x {im.size[1]} px")
        except Exception:
            pass

    messagebox.showinfo(
        "ShelfReady",
        "Done!" if code == 0 else "Finished with errors — check the log.")


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

tk.Label(io, textvariable=v_size, bg=PANEL, fg=NAVY_LT,
         font=F_TINY).grid(row=3, column=2, sticky="w", padx=4, pady=(0, 4))

# ── PROCESSING OPTIONS ────────────────────────────────────────────────────────

ops = sec(left, "PROCESSING OPTIONS")

# Dropdowns
dd = tk.Frame(ops, bg=PANEL)
dd.pack(fill="x", padx=8, pady=(6, 2))
for i, (t, v, vals) in enumerate([
    ("Operation", v_op,   ["convert", "clean", "both"]),
    ("Work On",   v_work, ["image", "canvas"]),
    ("Fit Mode",  v_fit,  ["pad", "fit", "crop_fill"]),
    ("Mode",      v_mode, ["safe", "auto", "aggressive"]),
]):
    pad_left = 0 if i == 0 else 14
    mkl(dd, t + ":").grid(row=0, column=i * 2,     sticky="e", padx=(pad_left, 2))
    mko(dd, v, *vals).grid(row=0, column=i * 2 + 1, sticky="w", padx=(0, 2))

rule(ops)

# Numeric params — 3 per row
pf = tk.Frame(ops, bg=PANEL)
pf.pack(fill="x", padx=8, pady=2)
PARAMS = [
    ("Size px",    v_sz),    ("Margin %",   v_margin), ("Top Pad px", v_tpad),   ("V.Bias",     v_vbias),
    ("Contrast",   v_cont),  ("Shp.Radius", v_shr),    ("Shp.%",      v_shp),    ("Shp.Thr",    v_sht),
    ("Dehalo px",  v_deh),   ("EdgeFeath",  v_edge),   ("TopClean %", v_tcln),   ("White Floor",v_wfl),
    ("Neutrality", v_neut),  ("Fill Ratio", v_fill),   ("Quality",    v_qual),   ("Shdw Alpha", v_shdal),
    ("DPI Value",  v_dpival),
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
tk.Button(rf, text="  RUN PROCESSING", command=do_run,
          bg=NAVY, fg=WHITE,
          activebackground=NAVY_DARK, activeforeground=WHITE,
          font=F_RUN, relief="flat", height=2,
          cursor="hand2").pack(fill="x")

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

# ── PREVIEW ───────────────────────────────────────────────────────────────────

prev_hdr = tk.Frame(right, bg=SLATE)
prev_hdr.pack(fill="x")
preview_lbl = tk.Label(prev_hdr, text="  IMAGE PREVIEW",
                        bg=SLATE, fg=GREY_LT,
                        font=F_SEC, anchor="w", padx=4, pady=4)
preview_lbl.pack(side="left")

preview_canvas = tk.Canvas(right, bg=LOG_BG, relief="flat",
                            bd=0, highlightthickness=0)
preview_canvas.pack(fill="both", expand=True)

root.mainloop()
