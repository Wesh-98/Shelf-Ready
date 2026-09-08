# -*- coding: utf-8 -*-
# ShelfReady Unified GUI
import os, sys, threading, tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk

from shelfready_ui import assets, presets, settings, theme
from shelfready_ui.version import __version__
from shelfready_ui.runner import run_toolkit

PY = sys.executable
FROZEN = getattr(sys, "frozen", False)
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# Launched with arguments, act as the command line tool instead of opening a
# window. Double-clicking passes none, so the GUI stays the default; in a
# frozen build this is what makes `ShelfReady.exe --in a.jpg --out b.jpg`
# work for scripted batches without a Python install.
if len(sys.argv) > 1:
    import image_toolkit
    sys.exit(image_toolkit.main() or 0)

# ── Before/after state ────────────────────────────────────────────────────────
_orig_path = None
_proc_path = None
_showing_orig = False

# ── Queue state ───────────────────────────────────────────────────────────────
_queue_files = []
# Where the last folder run wrote its results, so a queue selection can
# pair each input with its output for the before/after toggle.
_queue_out_dir = None
_queue_rename = ('', '')
# Which queued image the navigator is currently showing.
_queue_index = 0

# ── Palette ── themeable ───────────────────────
# Widget-creation code below references these bare module-level names
# (NAVY, PANEL, ACCENT, ...). The values come from shelfready_ui.theme;
# apply_theme() rebinds them AND walks the live widget tree to recolor
# everything already on screen.
THEMES = theme.THEMES
THEME_NAMES = theme.THEME_NAMES
_current_theme = theme.DEFAULT_THEME

_t = THEMES[_current_theme]
NAVY, NAVY_DARK, NAVY_LT     = _t["NAVY"], _t["NAVY_DARK"], _t["NAVY_LT"]
SLATE, SLATE_MD              = _t["SLATE"], _t["SLATE_MD"]
GREY, GREY_LT                = _t["GREY"], _t["GREY_LT"]
BG, PANEL                    = _t["BG"], _t["PANEL"]
BLACK, WHITE                 = _t["BLACK"], _t["WHITE"]
FIELD_BG, LOG_BG, LOG_FG     = _t["FIELD_BG"], _t["LOG_BG"], _t["LOG_FG"]
TEAL, ACCENT                 = _t["TEAL"], _t["ACCENT"]
ACCENT_HOVER, TEXT_ON_ACCENT = _t["ACCENT_HOVER"], _t["TEXT_ON_ACCENT"]
ON_BG, MUTED                 = _t["ON_BG"], _t["MUTED"]
CHECK_OFF, CHECK_ON          = _t["CHECK_OFF"], _t["CHECK_ON"]
CHECK_ON_ACCENT              = _t["CHECK_ON_ACCENT"]

# ── Fonts ─────────────────────────────────────────────────────────────────────
F_HEAD, F_SEC, F_LBL = theme.F_HEAD, theme.F_SEC, theme.F_LBL
F_TINY, F_ENT, F_RUN, F_MONO = theme.F_TINY, theme.F_ENT, theme.F_RUN, theme.F_MONO

# Title-bar brand mark, in pixels.
LOGO_PX = 26


def apply_theme(name):
    """Recolor every already-built widget in place (no rebuild), then
    update the module-level color names so anything created or
    reconfigured later — tooltips, button state changes, new previews —
    also picks up the new theme."""
    global _current_theme
    global NAVY, NAVY_DARK, NAVY_LT, SLATE, SLATE_MD, GREY, GREY_LT
    global BG, PANEL, BLACK, WHITE, FIELD_BG, LOG_BG, LOG_FG, TEAL
    global ACCENT, ACCENT_HOVER, TEXT_ON_ACCENT, ON_BG, MUTED
    global CHECK_OFF, CHECK_ON, CHECK_ON_ACCENT

    if name == _current_theme:
        return
    new = THEMES[name]
    recolor = theme.recolor_map(_current_theme, name)
    opts = ("bg", "fg", "activebackground", "activeforeground",
            "highlightbackground", "highlightcolor",
            "selectbackground", "selectforeground", "selectcolor",
            "troughcolor", "insertbackground", "disabledforeground")

    def recolor_widget(w):
        changes = {}
        for opt in opts:
            try:
                cur = str(w.cget(opt))
            except tk.TclError:
                continue
            if cur in recolor:
                changes[opt] = recolor[cur]
        if changes:
            try:
                w.config(**changes)
            except tk.TclError:
                pass
        if w.winfo_class() == "Menubutton":
            try:
                menu = w.nametowidget(w.cget("menu"))
                mchanges = {}
                for opt in ("bg", "fg", "activebackground", "activeforeground"):
                    cur = str(menu.cget(opt))
                    if cur in recolor:
                        mchanges[opt] = recolor[cur]
                if mchanges:
                    menu.config(**mchanges)
            except (tk.TclError, KeyError):
                pass
        for child in w.winfo_children():
            recolor_widget(child)

    recolor_widget(root)

    (NAVY, NAVY_DARK, NAVY_LT, SLATE, SLATE_MD, GREY, GREY_LT,
     BG, PANEL, BLACK, WHITE, FIELD_BG, LOG_BG, LOG_FG, TEAL,
     ACCENT, ACCENT_HOVER, TEXT_ON_ACCENT, ON_BG, MUTED) = (
        new["NAVY"], new["NAVY_DARK"], new["NAVY_LT"], new["SLATE"],
        new["SLATE_MD"], new["GREY"], new["GREY_LT"], new["BG"],
        new["PANEL"], new["BLACK"], new["WHITE"], new["FIELD_BG"],
        new["LOG_BG"], new["LOG_FG"], new["TEAL"], new["ACCENT"],
        new["ACCENT_HOVER"], new["TEXT_ON_ACCENT"],
        new["ON_BG"], new["MUTED"])
    CHECK_OFF, CHECK_ON, CHECK_ON_ACCENT = (
        new["CHECK_OFF"], new["CHECK_ON"], new["CHECK_ON_ACCENT"])

    log.tag_config("cmd",  foreground=new["LOG_CMD"])
    log.tag_config("info", foreground=new["LOG_CMD"])
    log.tag_config("div",  foreground=new["LOG_DIV"])

    _current_theme = name
    v_theme.set(name)
    theme_btn.config(text=_theme_btn_text(name))
    _set_logo(name)
    _sync_toggle()
    for _cb, _var, _accent in _checkboxes:
        try:
            _cb.config(selectcolor=_check_fill(_var, _accent))
        except tk.TclError:
            pass



# Every checkbox built by mkc, so a theme switch can re-derive the
# indicator fills from the new palette.
_checkboxes = []

# ── Widget helpers ────────────────────────────────────────────────────────────

def sec(parent, title):
    outer = tk.Frame(parent, bg=BG)
    outer.pack(fill="x", padx=6, pady=(5, 0))
    hdr = tk.Frame(outer, bg=NAVY)
    hdr.pack(fill="x")
    tk.Label(hdr, text=title, bg=NAVY, fg=ACCENT,
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
                    bg=FIELD_BG, fg=BLACK, insertbackground=ACCENT,
                    font=F_ENT, relief="flat",
                    highlightbackground=GREY, highlightthickness=1,
                    highlightcolor=ACCENT)


def mkb(parent, text, cmd, emoji=False):
    return tk.Button(parent, text=text, command=cmd,
                     bg=GREY_LT, fg=SLATE_MD,
                     activebackground=GREY, activeforeground=BLACK,
                     relief="flat", bd=0, cursor="hand2",
                     font=("Arial", 13) if emoji else F_LBL,
                     padx=4, pady=1)


def _check_fill(var, accent):
    """Indicator fill for a checkbox in its current state.

    Tk fills the indicator with selectcolor whether the box is on or
    off, so a single value makes both states look identical. Swapping
    it on toggle is what makes selection visible: clear when off,
    filled when on. The accent box needs its own ON fill because its
    checkmark is drawn in ACCENT, which vanishes on an accent fill."""
    if not var.get():
        return CHECK_OFF
    return CHECK_ON_ACCENT if accent else CHECK_ON


def mkc(parent, text, var, accent=False):
    cb = tk.Checkbutton(parent, text=text, variable=var,
                        bg=PANEL, fg=ACCENT if accent else SLATE_MD,
                        activebackground=PANEL,
                        selectcolor=_check_fill(var, accent),
                        font=(F_LBL[0], F_LBL[1], "bold") if accent else F_LBL)

    def _sync(*_):
        try:
            cb.config(selectcolor=_check_fill(var, accent))
        except tk.TclError:
            pass          # widget destroyed while the variable lived on

    var.trace_add("write", _sync)
    _checkboxes.append((cb, var, accent))
    return cb


def mko(parent, var, *vals):
    o = tk.OptionMenu(parent, var, *vals)
    o.config(bg=FIELD_BG, fg=BLACK, activebackground=GREY_LT,
             relief="flat", font=F_ENT,
             highlightbackground=GREY, highlightthickness=1,
             highlightcolor=ACCENT, padx=4)
    o["menu"].config(bg=PANEL, fg=BLACK, activebackground=NAVY,
                     activeforeground=ACCENT, font=F_ENT)
    return o


def rule(parent):
    tk.Frame(parent, bg=GREY_LT, height=1).pack(fill="x", padx=8, pady=2)


class Tooltip:
    """Small hover tooltip so advanced/technical labels stay short but
    still explain themselves on hover — avoids showing 15 raw parameter
    names to a user who just wants to run a preset."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, _=None):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 6
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, bg=NAVY_DARK, fg=WHITE,
                 font=F_TINY, padx=6, pady=4, relief="flat",
                 wraplength=220, justify="left").pack()

    def hide(self, _=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


# ── Logic ─────────────────────────────────────────────────────────────────────

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


def _paint_view_btn(btn, active, available):
    """Highlight the view that is on screen; dim the alternative.

    A single button labelled with the action it performs cannot say
    which image you are looking at - the label reads equally well as a
    description of the current view. Two buttons, one lit, remove the
    ambiguity even when the two images look alike."""
    if not available:
        btn.config(state="disabled", bg=SLATE, cursor="")
    elif active:
        btn.config(state="normal", bg=ACCENT, fg=TEXT_ON_ACCENT,
                   cursor="hand2")
    else:
        btn.config(state="normal", bg=SLATE, fg=ACCENT, cursor="hand2")


def _sync_toggle():
    """Reflect which of the two images the preview is showing."""
    have_orig = bool(_orig_path)
    have_proc = bool(_proc_path)
    _paint_view_btn(before_btn, _showing_orig, have_orig)
    _paint_view_btn(after_btn, not _showing_orig and have_proc, have_proc)


def _show_view(show_original):
    """Put one of the two images on screen. Ignored if it does not exist."""
    global _showing_orig
    target = _orig_path if show_original else _proc_path
    if not target:
        return
    _showing_orig = show_original
    update_preview(target)
    _sync_toggle()


def toggle_preview():
    """Flip between the two views (used by the keyboard shortcut)."""
    if _orig_path and _proc_path:
        _show_view(not _showing_orig)


def apply_platform(*_):
    p = presets.PLATFORM_PRESETS.get(v_platform.get(), {})
    if "size"    in p: v_sz.set(p["size"])
    if "quality" in p: v_qual.set(p["quality"])


def pick(var, fn, is_input=False):
    global _orig_path, _proc_path, _showing_orig
    p = fn()
    if not p:
        return
    var.set(p)

    if is_input:
        # File, folder and ZIP are mutually exclusive, and build_args
        # resolves them in that order. Without clearing the others, a
        # folder chosen after a file is silently ignored at run time.
        for _other, _out in ((v_in_file, v_out_file), (v_in_dir, v_out_dir),
                             (v_in_zip, v_out_zip)):
            if _other is not var:
                _other.set('')
                _out.set('')

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
        _showing_orig = True    # the preview above is showing the source
        _sync_toggle()
        _hide_queue()
    elif is_input and var is v_in_dir:
        # Switching input mode must drop any result from the previous run,
        # or the toggle keeps offering the last file's before/after.
        _orig_path = _proc_path = None
        _showing_orig = False
        _sync_toggle()
        _populate_queue(p)
    elif is_input and var is v_in_zip:
        _orig_path = _proc_path = None
        _showing_orig = False
        _sync_toggle()
        queue_name_lbl.config(text="ZIP selected — queue after processing")
        queue_count_lbl.config(text="")
        queue_prev_btn.config(state="disabled", cursor="")
        queue_next_btn.config(state="disabled", cursor="")
        _show_queue()


def pick_out_file():
    p = filedialog.asksaveasfilename(
        defaultextension=".jpg",
        filetypes=[("JPEG", "*.jpg"), ("PNG", "*.png"),
                   ("WebP", "*.webp"), ("All Files", "*.*")])
    if p:
        v_out_file.set(p)


def _populate_queue(folder_path):
    global _queue_files, _queue_out_dir, _queue_index
    _queue_files = sorted([
        os.path.join(folder_path, f)
        for f in os.listdir(folder_path)
        if os.path.isfile(os.path.join(folder_path, f))
        and f.lower().endswith(presets.QUEUE_EXTS)
    ])
    _queue_out_dir = None      # results of any previous run no longer apply
    _queue_index = 0
    if _queue_files:
        _queue_show(0)
    else:
        _sync_queue_nav()
    _show_queue()


def _hide_queue():
    """Put the batch navigator away when the input is a single file."""
    global _queue_files, _queue_out_dir, _queue_index
    _queue_files = []
    _queue_out_dir = None
    _queue_index = 0
    queue_frame.grid_remove()


def _show_queue():
    """Reveal the batch queue pane (see the grid note at its creation)."""
    queue_frame.grid()


def _sync_queue_nav():
    """Refresh the name, counter and arrow availability."""
    total = len(_queue_files)
    if total:
        queue_name_lbl.config(
            text=os.path.basename(_queue_files[_queue_index]))
        queue_count_lbl.config(text=f"{_queue_index + 1} of {total}")
    else:
        queue_name_lbl.config(text="No images found")
        queue_count_lbl.config(text="")
    # Ends of the list are dead ends rather than wrapping, so the arrows
    # themselves show where you are in the run.
    queue_prev_btn.config(state="normal" if _queue_index > 0 else "disabled",
                          cursor="hand2" if _queue_index > 0 else "")
    more = _queue_index < total - 1
    queue_next_btn.config(state="normal" if more else "disabled",
                          cursor="hand2" if more else "")


def _queue_step(delta):
    _queue_show(_queue_index + delta)


def _queue_show(index):
    """Show one queued image, pairing it with its result if there is one."""
    global _orig_path, _proc_path, _showing_orig, _queue_index
    if not _queue_files:
        _sync_queue_nav()
        return
    _queue_index = max(0, min(index, len(_queue_files) - 1))
    path = _queue_files[_queue_index]
    _orig_path = path

    # After a folder run each input has a matching output; show it and
    # let the toggle flip back to the source.
    processed = None
    if _queue_out_dir:
        candidate = settings.output_for(path, _queue_out_dir,
                                        *_queue_rename)
        if os.path.exists(candidate):
            processed = candidate
    _proc_path = processed
    _showing_orig = processed is None
    update_preview(processed or path)
    _sync_toggle()
    _sync_queue_nav()


# Maps every tk variable to the settings key shelfready_ui.settings expects.
# One table instead of the old parallel lists, so adding a knob means adding
# one line here rather than editing both the validator and the arg builder.
SETTING_VARS = {}


def _register_setting_vars():
    """Populated after the tk variables exist (see the Variables section)."""
    SETTING_VARS.update({
        "op": v_op, "work_on": v_work, "fit_mode": v_fit, "mode": v_mode,
        "size": v_sz, "margin_pct": v_margin, "min_top_pad_px": v_tpad,
        "vertical_bias": v_vbias, "product_contrast": v_cont,
        "sharpen_radius": v_shr, "sharpen_percent": v_shp,
        "sharpen_threshold": v_sht, "dehalo_px": v_deh,
        "edge_feather": v_edge, "top_clean_pct": v_tcln,
        "white_floor": v_wfl, "neutrality_tol": v_neut,
        "target_fill": v_fill, "quality": v_qual,
        "no_downscale": v_nd, "no_bg_clean": v_nbg, "allow_upscale": v_up,
        "no_largest_scrub": v_nls, "no_progressive": v_npr,
        "no_optimize": v_nop, "auto_work_on": v_awo, "auto_enhance": v_aen,
        "set_dpi": v_dpi, "dpi_value": v_dpival,
        "add_shadow": v_shd, "shadow_alpha": v_shdal,
        "qty_badge": v_qty, "qty_badge_text": v_qtytxt,
        "out_prefix": v_rename_prefix, "out_suffix": v_rename_suffix,
        "in_file": v_in_file, "out_file": v_out_file,
        "in_dir": v_in_dir, "out_dir": v_out_dir,
        "in_zip": v_in_zip, "out_zip": v_out_zip,
    })


def collect_settings():
    """Snapshot the tk variables into a plain dict for shelfready_ui.settings."""
    return {key: var.get() for key, var in SETTING_VARS.items()}


def do_run():
    script = os.path.join(PROJECT_DIR, "image_toolkit.py")
    # A frozen build has no image_toolkit.py on disk - the module is bundled
    # and run in-process, so this path is only a label for the log line there.
    if not FROZEN and not os.path.exists(script):
        messagebox.showerror("Error", f"image_toolkit.py not found:\n{script}")
        return

    values = collect_settings()

    problems = settings.validate(values)
    if problems:
        bullet = "\n  - "
        messagebox.showerror("Invalid settings",
                             "Fix these before running:\n" +
                             bullet + bullet.join(problems))
        return

    try:
        cmd = settings.build_args(values, PY, script)
    except ValueError as e:
        messagebox.showerror("Error", str(e))
        return

    # build_args resolves blank output paths; echo them back into the fields
    # so the user sees where the result actually went.
    if cmd.out_path:
        v_out_file.set(cmd.out_path)
    if cmd.out_dir:
        v_out_dir.set(cmd.out_dir)
    if cmd.out_zip:
        v_out_zip.set(cmd.out_zip)

    run_btn.config(state="disabled", bg=SLATE, fg=GREY, cursor="",
                   text="  PROCESSING\u2026")

    def worker():
        code, output = run_toolkit(cmd.args)
        root.after(0, lambda: _finish(code, output, cmd.out_path,
                                      cmd.out_zip, cmd.out_dir))

    threading.Thread(target=worker, daemon=True).start()


def _finish(code, output, out_path, out_zip=None, out_dir=None):
    global _proc_path, _showing_orig, _queue_out_dir, _queue_rename

    log.config(state="normal")
    log.delete("1.0", "end")
    log.insert("end", "$ image_toolkit [args]\n\n", "cmd")
    log.insert("end", output)

    if code == 0 and out_zip and os.path.exists(out_zip):
        log.insert("end", f"\n{'─' * 52}\n", "div")
        log.insert("end", f"  ZIP saved → {out_zip}\n", "info")
        log.insert("end", f"{'─' * 52}\n", "div")

    log.config(state="disabled")
    log.see("end")

    if code == 0 and out_dir and os.path.isdir(out_dir):
        _queue_out_dir = out_dir
        _queue_rename = (v_rename_prefix.get().strip(),
                         v_rename_suffix.get().strip())
        _queue_show(_queue_index)   # pair what is on screen with its result

    if code == 0 and out_path and os.path.exists(out_path):
        _proc_path = out_path
        _showing_orig = False
        update_preview(out_path)
        _sync_toggle()
        try:
            with Image.open(out_path) as im:
                in_txt = v_size.get().split("|")[0].strip()
                v_size.set(f"{in_txt}  |  Output: {im.size[0]} × {im.size[1]} px")
        except Exception:
            pass

    run_btn.config(state="normal", bg=ACCENT, fg=TEXT_ON_ACCENT, cursor="hand2",
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
root.title(f"ShelfReady {__version__}")
root.geometry("1500x940")
root.configure(bg=BG)
root.minsize(1100, 700)
assets.set_window_icon(root)

# Title bar
title_bar = tk.Frame(root, bg=NAVY_DARK)
title_bar.grid(row=0, column=0, columnspan=2, sticky="ew")
logo_lbl = tk.Label(title_bar, bg=NAVY_DARK, bd=0)
logo_lbl.pack(side="left", padx=(10, 0))

tk.Label(title_bar, text="  ShelfReady", bg=NAVY_DARK, fg=ACCENT,
         font=F_HEAD, pady=10).pack(side="left")
tk.Label(title_bar, text="Product Image Toolkit",
         bg=NAVY_DARK, fg=LOG_FG, font=("Arial", 9),
         pady=10).pack(side="left", padx=(8, 0))

def _set_logo(name):
    """Swap the title-bar mark to the variant drawn for this theme."""
    photo = assets.load_mark(name, size=LOGO_PX)
    if photo is None:
        # No art available - let the wordmark stand on its own.
        logo_lbl.pack_forget()
        return
    logo_lbl.config(image=photo)
    logo_lbl.image = photo


def _theme_btn_text(name):
    return f"\u25d0 {THEME_NAMES.get(name, name)}  \u25be"


def _show_theme_menu(event=None):
    """Drop a list of every available theme under the button.

    Rebuilt on each click so its own colors match the theme in effect;
    a menu is not a child widget, so apply_theme's tree walk never
    reaches it."""
    menu = tk.Menu(theme_btn, tearoff=0,
                   bg=PANEL, fg=SLATE_MD,
                   activebackground=NAVY, activeforeground=ACCENT,
                   selectcolor=ACCENT, font=F_ENT,
                   relief="flat", bd=0)
    for key in THEMES:
        menu.add_radiobutton(
            label=THEME_NAMES.get(key, key),
            value=key, variable=v_theme,
            command=lambda k=key: apply_theme(k))
    try:
        menu.tk_popup(theme_btn.winfo_rootx(),
                      theme_btn.winfo_rooty() + theme_btn.winfo_height())
    finally:
        menu.grab_release()


v_theme = tk.StringVar(value=_current_theme)
theme_btn = tk.Button(title_bar, text=_theme_btn_text(_current_theme),
                       command=_show_theme_menu,
                       bg=NAVY_DARK, fg=ACCENT,
                       activebackground=NAVY_LT, activeforeground=ACCENT,
                       relief="flat", bd=0, cursor="hand2",
                       font=("Arial", 9, "bold"), padx=10, pady=6)
theme_btn.pack(side="right", padx=(0, 8))
Tooltip(theme_btn, "Switch color theme")
_set_logo(_current_theme)

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
v_awo = tk.BooleanVar()
v_aen = tk.BooleanVar()

v_qtytxt  = tk.StringVar()
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

_register_setting_vars()

# ── PLATFORM PRESET ───────────────────────────────────────────────────────────

plat_bar = tk.Frame(left, bg=BG)
plat_bar.pack(fill="x", padx=6, pady=(6, 0))
tk.Label(plat_bar, text="Platform:", bg=BG, fg=ON_BG, font=F_LBL).pack(side="left", padx=(2, 4))
plat_menu = mko(plat_bar, v_platform, *presets.PLATFORM_PRESETS.keys())
plat_menu.pack(side="left")
tk.Label(plat_bar, text="Canvas px:", bg=BG, fg=ON_BG, font=F_LBL).pack(side="left", padx=(14, 4))
sz_ent = tk.Entry(plat_bar, textvariable=v_sz, width=6,
                  bg=FIELD_BG, fg=BLACK, font=F_ENT, relief="flat",
                  highlightbackground=GREY, highlightthickness=1,
                  highlightcolor=ACCENT, insertbackground=ACCENT)
sz_ent.pack(side="left")
tk.Label(plat_bar, text="Quality:", bg=BG, fg=ON_BG, font=F_LBL).pack(side="left", padx=(10, 4))
qual_ent = tk.Entry(plat_bar, textvariable=v_qual, width=4,
                    bg=FIELD_BG, fg=BLACK, font=F_ENT, relief="flat",
                    highlightbackground=GREY, highlightthickness=1,
                    highlightcolor=ACCENT, insertbackground=ACCENT)
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
    tk.Label(io, text="->", bg=PANEL, fg=MUTED,
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
         bg=PANEL, fg=MUTED, font=F_TINY).pack(side="left", padx=(8, 0))

tk.Label(io, textvariable=v_size, bg=PANEL, fg=MUTED,
         font=F_TINY).grid(row=4, column=0, columnspan=6, sticky="w", padx=8, pady=(0, 4))

# ── PROCESSING OPTIONS ────────────────────────────────────────────────────────

ops = sec(left, "PROCESSING OPTIONS")

# Auto-snap fill params when a fill mode is selected
def _on_fit_mode(*_):
    snap = presets.FIT_MODE_SNAPS.get(v_fit.get())
    if not snap:
        return
    for key, var in (("fill", v_fill), ("margin", v_margin), ("tpad", v_tpad)):
        if snap[key] is not None:
            var.set(snap[key])
    if snap["upscale"] is not None:
        v_up.set(snap["upscale"])
v_fit.trace_add("write", _on_fit_mode)

# Dropdowns
DROPDOWN_TIPS = {
    "Operation": "convert = resize/canvas only · clean = background removal only · both = full pipeline",
    "Work On":   "Apply settings to the product image itself, or to the full canvas.",
    "Fit Mode":  "How the product is scaled onto the canvas (padding, cropping, fill).",
    "Mode":      "How cautious the automatic cleanup is: safe < auto < aggressive.",
}
dd = tk.Frame(ops, bg=PANEL)
dd.pack(fill="x", padx=8, pady=(6, 2))
for i, (t, v, vals) in enumerate([
    ("Operation", v_op,   presets.OP_CHOICES),
    ("Work On",   v_work, presets.WORK_ON_CHOICES),
    ("Fit Mode",  v_fit,  presets.FIT_MODE_CHOICES),
    ("Mode",      v_mode, presets.MODE_CHOICES),
]):
    pad_left = 0 if i == 0 else 14
    lbl = mkl(dd, t + ":")
    lbl.grid(row=0, column=i * 2, sticky="e", padx=(pad_left, 2))
    Tooltip(lbl, DROPDOWN_TIPS[t])
    mko(dd, v, *vals).grid(row=0, column=i * 2 + 1, sticky="w", padx=(0, 2))

rule(ops)

# Quick toggles — the handful people actually flip per-run.
# Everything else (15 numeric tuning fields + 5 rare flags) lives behind
# "Advanced settings" below, collapsed by default.
qt = tk.Frame(ops, bg=PANEL)
qt.pack(fill="x", padx=8, pady=(6, 2))
QUICK_CHECKS = [
    ("Allow Upscale",  v_up,  "Let small source images be scaled up to hit the target canvas."),
    ("Auto Work Mode", v_awo, "Automatically choose image vs. canvas mode per file."),
    ("Auto Enhance",   v_aen, "Automatically tune sharpen/contrast per image instead of using fixed values."),
]
for i, (t, v, tip) in enumerate(QUICK_CHECKS):
    cb = mkc(qt, t, v)
    cb.grid(row=0, column=i, sticky="w", padx=(0, 18), pady=1)
    Tooltip(cb, tip)

rule(ops)

# ── Advanced settings — collapsed by default ──────────────────────────────
FIELD_TIPS = {
    "Margin %":          "Empty space kept around the product, as a fraction of canvas size.",
    "Top Padding":        "Minimum pixels of empty space above the product.",
    "Vertical Bias":      "Where the product sits vertically — higher pushes it up.",
    "Fill Ratio":         "How much of the canvas the product should fill.",
    "Contrast":           "Contrast multiplier applied to the product.",
    "Top Clean %":        "Fraction of the top edge scrubbed of stray pixels/artifacts.",
    "White Floor":        "Minimum brightness treated as pure background white.",
    "Neutrality":         "Color tolerance for what still counts as neutral background.",
    "Sharpen Radius":     "Unsharp-mask radius — larger affects a wider band around edges.",
    "Sharpen Amount %":   "Strength of the sharpening effect.",
    "Sharpen Threshold":  "Minimum contrast difference before sharpening kicks in.",
    "Dehalo (px)":        "Cleans up sharpening halos near edges.",
    "Edge Feather":       "Softens the cutout edge around the product.",
}

def _adv_group(container, title, fields, cols=2):
    frame = tk.Frame(container, bg=PANEL)
    frame.pack(fill="x", padx=8, pady=(6, 2))
    tk.Label(frame, text=title, bg=PANEL, fg=ACCENT,
             font=(F_LBL[0], F_LBL[1], "bold")).grid(
        row=0, column=0, columnspan=cols * 2, sticky="w", pady=(0, 3))
    for i, (t, v) in enumerate(fields):
        c, row = (i % cols) * 2, i // cols + 1
        lbl = mkl(frame, t + ":", small=True)
        lbl.grid(row=row, column=c, sticky="e", padx=(4, 2), pady=1)
        if t in FIELD_TIPS:
            Tooltip(lbl, FIELD_TIPS[t])
        mke(frame, v, 7).grid(row=row, column=c + 1, sticky="w", padx=(0, 8), pady=1)

adv_state = {"open": False}
adv_container = tk.Frame(ops, bg=PANEL)

_adv_group(adv_container, "SIZING & FIT", [
    ("Margin %", v_margin), ("Top Padding", v_tpad),
    ("Vertical Bias", v_vbias), ("Fill Ratio", v_fill),
])
_adv_group(adv_container, "SHARPENING", [
    ("Sharpen Radius", v_shr), ("Sharpen Amount %", v_shp),
    ("Sharpen Threshold", v_sht), ("Dehalo (px)", v_deh),
    ("Edge Feather", v_edge),
])
_adv_group(adv_container, "COLOR & CLEANUP", [
    ("Contrast", v_cont), ("Top Clean %", v_tcln),
    ("White Floor", v_wfl), ("Neutrality", v_neut),
])

rule(adv_container)

# Rarely-touched flags, grouped inside Advanced
cf = tk.Frame(adv_container, bg=PANEL)
cf.pack(fill="x", padx=8, pady=(4, 2))
CHECKS = [
    ("No Downscale",    v_nd),
    ("Skip BG Clean",   v_nbg),
    ("No Largest Scrub",v_nls),
    ("No Progressive",  v_npr),
    ("No Optimize",     v_nop),
]
for i, (t, v) in enumerate(CHECKS):
    c, row = i % 3, i // 3
    mkc(cf, t, v).grid(row=row, column=c, sticky="w", padx=(2, 16), pady=1)

# DPI / Shadow — paired with the flag that actually uses them
dsf = tk.Frame(adv_container, bg=PANEL)
dsf.pack(fill="x", padx=8, pady=(4, 8))
mkc(dsf, "Set DPI", v_dpi).grid(row=0, column=0, sticky="w")
mke(dsf, v_dpival, 6).grid(row=0, column=1, sticky="w", padx=(4, 20))
mkc(dsf, "Soft Shadow", v_shd).grid(row=0, column=2, sticky="w")
mke(dsf, v_shdal, 6).grid(row=0, column=3, sticky="w", padx=(4, 4))
mkl(dsf, "alpha 0-100", small=True).grid(row=0, column=4, sticky="w")

def _toggle_advanced():
    if adv_state["open"]:
        adv_container.pack_forget()
        adv_toggle_btn.config(text="▸  Advanced settings")
    else:
        adv_container.pack(fill="x", padx=0, pady=(0, 0), before=xf)
        adv_toggle_btn.config(text="▾  Advanced settings")
    adv_state["open"] = not adv_state["open"]

adv_toggle_btn = tk.Button(ops, text="▸  Advanced settings",
                            command=_toggle_advanced,
                            bg=PANEL, fg=MUTED, activeforeground=ACCENT,
                            activebackground=PANEL, relief="flat", bd=0,
                            cursor="hand2", font=(F_LBL[0], F_LBL[1], "bold"),
                            anchor="w", padx=8, pady=4)
adv_toggle_btn.pack(fill="x", padx=0, pady=(0, 0))

rule(ops)

# Qty badge
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


# ── RUN ───────────────────────────────────────────────────────────────────────

rf = tk.Frame(left, bg=BG)
rf.pack(fill="x", padx=6, pady=8)
run_btn = tk.Button(rf, text="  RUN PROCESSING", command=do_run,
                    bg=ACCENT, fg=TEXT_ON_ACCENT,
                    activebackground=ACCENT_HOVER, activeforeground=TEXT_ON_ACCENT,
                    font=F_RUN, relief="flat", height=2,
                    cursor="hand2")
run_btn.pack(fill="x")

# ── LOG ───────────────────────────────────────────────────────────────────────

log_outer = tk.Frame(left, bg=BG)
log_outer.pack(fill="both", expand=True, padx=6, pady=(0, 6))

log_hdr = tk.Frame(log_outer, bg=SLATE)
log_hdr.pack(fill="x")
tk.Label(log_hdr, text="PROCESSING LOG", bg=SLATE, fg=ACCENT,
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

log.tag_config("cmd",    foreground="#5cd9a0", font=("Courier", 8, "bold"))
log.tag_config("div",    foreground=GREY)
log.tag_config("info",   foreground="#5cd9a0")
log.tag_config("crit",   foreground="#fc8181")
log.tag_config("err",    foreground="#f6ad55")
log.tag_config("warn",   foreground="#f6e05e")

# ── RIGHT: PREVIEW + QUEUE ────────────────────────────────────────────────────

right.grid_rowconfigure(1, weight=1)
right.grid_columnconfigure(0, weight=1)

# Preview header
prev_hdr = tk.Frame(right, bg=SLATE)
prev_hdr.grid(row=0, column=0, sticky="ew")

def _view_button(text, cmd):
    return tk.Button(prev_hdr, text=text, command=cmd,
                     bg=SLATE, fg=ACCENT,
                     activebackground=ACCENT_HOVER,
                     activeforeground=TEXT_ON_ACCENT,
                     disabledforeground=MUTED,
                     relief="flat", bd=0, highlightthickness=0,
                     font=("Arial", 8, "bold"), padx=10, pady=4,
                     state="disabled")


before_btn = _view_button("BEFORE", lambda: _show_view(True))
before_btn.pack(side="left", padx=(6, 1), pady=2)

after_btn = _view_button("AFTER", lambda: _show_view(False))
after_btn.pack(side="left", padx=(1, 6), pady=2)

Tooltip(before_btn, "Show the original image")
Tooltip(after_btn, "Show the processed result")

# toggle_btn kept as an alias so nothing that referenced the old single
# button breaks; it now points at the "after" half of the pair.
toggle_btn = after_btn

preview_name_lbl = tk.Label(prev_hdr, text="  IMAGE PREVIEW",
                              bg=SLATE, fg=ACCENT,
                              font=F_SEC, anchor="w", padx=4, pady=4)
preview_name_lbl.pack(side="left", fill="x", expand=True)

# Preview canvas
preview_canvas = tk.Canvas(right, bg=LOG_BG, relief="flat",
                             bd=0, highlightthickness=0)
preview_canvas.grid(row=1, column=0, sticky="nsew")

# Queue browser (hidden until folder/zip selected)
queue_frame = tk.Frame(right, bg=SLATE)
# Row 2 of the right column. Kept out of the layout until there is
# something to list; grid_remove() preserves its row assignment.
queue_frame.grid(row=2, column=0, sticky="ew", pady=(4, 0))
queue_frame.grid_remove()

queue_hdr = tk.Frame(queue_frame, bg=SLATE)
queue_hdr.pack(fill="x")
tk.Label(queue_hdr, text="BATCH QUEUE", bg=SLATE, fg=ACCENT,
         font=F_SEC, anchor="w", padx=10, pady=3).pack(side="left")
queue_count_lbl = tk.Label(queue_hdr, text="", bg=SLATE, fg=GREY,
                             font=F_TINY, padx=6)
queue_count_lbl.pack(side="left")

queue_body = tk.Frame(queue_frame, bg=LOG_BG)
queue_body.pack(fill="x")


def _nav_button(text, cmd):
    """Arrow button. Carries the theme accent, and greys out at the ends
    of the queue via disabledforeground, which the theme walk recolors."""
    return tk.Button(queue_body, text=text, command=cmd,
                     bg=LOG_BG, fg=ACCENT,
                     activebackground=LOG_BG, activeforeground=ACCENT_HOVER,
                     disabledforeground=MUTED,
                     relief="flat", bd=0, highlightthickness=0,
                     font=("Arial", 15, "bold"), padx=14, pady=2,
                     cursor="hand2")


queue_prev_btn = _nav_button("◀", lambda: _queue_step(-1))
queue_prev_btn.pack(side="left", padx=(6, 0), pady=4)

queue_next_btn = _nav_button("▶", lambda: _queue_step(1))
queue_next_btn.pack(side="right", padx=(0, 6), pady=4)

# The name of the image currently on screen, where the list used to be.
queue_name_lbl = tk.Label(queue_body, text="", bg=LOG_BG, fg=LOG_FG,
                          font=F_ENT, anchor="center")
queue_name_lbl.pack(side="left", fill="x", expand=True, pady=4)

Tooltip(queue_prev_btn, "Previous image")
Tooltip(queue_next_btn, "Next image")


def _queue_key(event):
    """Left/Right step through the queue, unless a text field has focus."""
    if not _queue_files or not queue_frame.winfo_ismapped():
        return
    if isinstance(root.focus_get(), (tk.Entry, tk.Text)):
        return
    _queue_step(-1 if event.keysym == "Left" else 1)


root.bind("<Left>", _queue_key)
root.bind("<Right>", _queue_key)

root.mainloop()