/* ShelfReady web front end.
 *
 * The form is built from /api/config rather than written out in HTML, so the
 * fields, their ranges, the dropdown choices and the marketplace presets all
 * come from the same Python tables the desktop app and the validator use.
 * Adding a knob to image_toolkit.py and its settings table makes it appear
 * here with no change to this file.
 */

(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);

  const state = {
    config: null,
    file: null,        // the chosen File
    beforeUrl: null,   // object URL for the original
    afterUrl: null,    // object URL for the result
    busy: false,
  };

  /* ── Theme ────────────────────────────────────────────────────────── */
  // Persisted per browser; with nothing stored the OS preference decides,
  // which is why theme.css leaves :root unqualified for the default.
  const THEMES = ["green", "warm"];

  function applyTheme(name) {
    if (name) {
      document.documentElement.setAttribute("data-theme", name);
      try { localStorage.setItem("shelfready-theme", name); } catch (_) {}
    }
  }

  function initTheme() {
    let stored = null;
    try { stored = localStorage.getItem("shelfready-theme"); } catch (_) {}
    if (stored && THEMES.includes(stored)) applyTheme(stored);

    $("theme-btn").addEventListener("click", () => {
      const current = document.documentElement.getAttribute("data-theme");
      const next = THEMES[(THEMES.indexOf(current) + 1) % THEMES.length];
      applyTheme(next);
    });
  }

  /* ── Building the form ────────────────────────────────────────────── */
  function el(tag, attrs = {}, children = []) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (value === null || value === undefined) continue;
      if (key === "class") node.className = value;
      else if (key === "text") node.textContent = value;
      else node.setAttribute(key, value);
    }
    for (const child of children) node.appendChild(child);
    return node;
  }

  function numericField(key) {
    const spec = state.config.numeric_fields.find((f) => f.key === key);
    if (!spec) return null;
    const tip = state.config.tips[key] || "";
    const input = el("input", {
      type: "number", id: key, value: state.config.defaults[key],
      min: spec.min, max: spec.max,
      step: spec.type === "int" ? "1" : "any",
      title: tip,
    });
    const label = el("label", { for: key, text: spec.label, title: tip });
    return el("div", { class: "field" }, [label, input]);
  }

  function buildDropdowns() {
    const host = $("dropdowns");
    for (const dd of state.config.dropdowns) {
      const select = el("select", { id: dd.key, title: dd.tip });
      for (const choice of state.config.choices[dd.key]) {
        const option = el("option", { value: choice, text: choice });
        if (choice === state.config.defaults[dd.key]) option.selected = true;
        select.appendChild(option);
      }
      host.appendChild(el("div", { class: "field" }, [
        el("label", { for: dd.key, text: dd.label, title: dd.tip }),
        select,
      ]));
    }

    // Choosing a fit mode snaps the framing knobs to values that suit it —
    // the same courtesy the desktop app does, so nobody has to know which of
    // the fifteen fields matter for "fill_width".
    $("fit_mode").addEventListener("change", (event) => {
      const snap = state.config.fit_mode_snaps[event.target.value];
      if (!snap) return;
      const map = { fill: "target_fill", margin: "margin_pct", tpad: "min_top_pad_px" };
      for (const [from, to] of Object.entries(map)) {
        if (snap[from] !== null && snap[from] !== undefined && $(to)) $(to).value = snap[from];
      }
      if (snap.upscale !== null && snap.upscale !== undefined) {
        $("allow_upscale").checked = Boolean(snap.upscale);
      }
    });
  }

  function buildToggles() {
    const host = $("quick-toggles");
    for (const toggle of state.config.quick_toggles) {
      const input = el("input", { type: "checkbox", id: toggle.key });
      input.checked = Boolean(state.config.defaults[toggle.key]);
      host.appendChild(el("label", { class: "check", title: toggle.tip },
        [input, el("span", { text: toggle.label })]));
    }
  }

  function buildAdvanced() {
    const host = $("advanced");

    // Canvas size and quality lead: they are the two people actually change.
    const lead = el("div", { class: "adv-group" }, [
      el("h3", { text: "Output" }),
      el("div", { class: "grid-2" },
        ["size", "quality"].map(numericField).filter(Boolean)),
    ]);
    host.appendChild(lead);

    for (const group of state.config.advanced_groups) {
      const fields = group.keys.map(numericField).filter(Boolean);
      host.appendChild(el("div", { class: "adv-group" }, [
        el("h3", { text: group.title }),
        el("div", { class: "grid-2" }, fields),
      ]));
    }

    const flags = state.config.rare_flags.map((flag) => {
      const input = el("input", { type: "checkbox", id: flag.key });
      input.checked = Boolean(state.config.defaults[flag.key]);
      return el("label", { class: "check" }, [input, el("span", { text: flag.label })]);
    });
    host.appendChild(el("div", { class: "adv-group" }, [
      el("h3", { text: "Rarely needed" }),
      el("div", { class: "adv-flags" }, flags),
    ]));

    const toggle = $("adv-toggle");
    toggle.addEventListener("click", () => {
      const open = toggle.getAttribute("aria-expanded") === "true";
      toggle.setAttribute("aria-expanded", String(!open));
      host.hidden = open;
    });
  }

  function buildPlatforms() {
    const select = $("platform");
    for (const name of Object.keys(state.config.platform_presets)) {
      select.appendChild(el("option", { value: name, text: name }));
    }
    select.addEventListener("change", () => {
      const preset = state.config.platform_presets[select.value] || {};
      for (const [key, value] of Object.entries(preset)) {
        if ($(key)) $(key).value = value;
      }
      const summary = Object.entries(preset)
        .map(([key, value]) => `${key} ${value}`).join(" · ");
      $("platform-hint").textContent =
        summary ? `Applied: ${summary}` : "Sets canvas size and quality";
      // A preset only means anything once its fields are on screen.
      if (summary && $("advanced").hidden) $("adv-toggle").click();
    });
  }

  // The paired flag/value controls: the number is meaningless unless its
  // checkbox is on, so it stays disabled until then.
  function bindPairedControls() {
    const pairs = [["add_shadow", "shadow_alpha"], ["qty_badge", "qty_badge_text"],
                   ["set_dpi", "dpi_value"]];
    for (const [flag, value] of pairs) {
      const sync = () => { $(value).disabled = !$(flag).checked; };
      $(flag).addEventListener("change", sync);
      sync();
    }
    $("qty_badge_text").maxLength = state.config.max_badge_chars;
  }

  /* ── Collecting what the user set ─────────────────────────────────── */
  function collectSettings() {
    const values = {};
    for (const key of Object.keys(state.config.defaults)) {
      const node = $(key);
      if (!node) continue;
      values[key] = node.type === "checkbox" ? node.checked : node.value;
    }
    return values;
  }

  /* ── Choosing a file ──────────────────────────────────────────────── */
  function humanSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }

  function setFile(file) {
    if (!file) return;
    const cap = state.config.limits.max_upload_bytes;
    if (file.size > cap) {
      showErrors([`That image is ${humanSize(file.size)} — the limit is ${humanSize(cap)}.`]);
      return;
    }
    clearErrors();

    if (state.beforeUrl) URL.revokeObjectURL(state.beforeUrl);
    state.file = file;
    state.beforeUrl = URL.createObjectURL(file);

    $("filename").textContent = `${file.name} — ${humanSize(file.size)}`;
    $("filename").hidden = false;
    $("run-btn").disabled = false;

    const before = $("img-before");
    before.src = state.beforeUrl;
    showView("before");
    $("view-toggle").hidden = false;
    $("stage-empty").hidden = true;

    // A new source makes the previous result stale.
    if (state.afterUrl) {
      URL.revokeObjectURL(state.afterUrl);
      state.afterUrl = null;
    }
    $("img-after").hidden = true;
    $("result-bar").hidden = true;
    $("log-box").hidden = true;
  }

  function initDropzone() {
    const zone = $("dropzone");
    const input = $("file-input");

    zone.addEventListener("click", () => input.click());
    zone.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        input.click();
      }
    });
    input.addEventListener("change", () => setFile(input.files[0]));

    for (const name of ["dragenter", "dragover"]) {
      zone.addEventListener(name, (event) => {
        event.preventDefault();
        zone.classList.add("is-dragging");
      });
    }
    for (const name of ["dragleave", "drop"]) {
      zone.addEventListener(name, (event) => {
        event.preventDefault();
        zone.classList.remove("is-dragging");
      });
    }
    zone.addEventListener("drop", (event) => {
      const file = event.dataTransfer.files && event.dataTransfer.files[0];
      if (file) setFile(file);
    });

    // Pasting a screenshot is the fastest path from "I have this image" to
    // a result, and costs one listener.
    document.addEventListener("paste", (event) => {
      const item = [...(event.clipboardData?.items || [])]
        .find((i) => i.type.startsWith("image/"));
      if (item) setFile(item.getAsFile());
    });
  }

  /* ── Before / after ───────────────────────────────────────────────── */
  function showView(which) {
    const hasAfter = Boolean(state.afterUrl);
    const view = which === "after" && !hasAfter ? "before" : which;
    $("img-before").hidden = view !== "before";
    $("img-after").hidden = view !== "after";
    for (const button of document.querySelectorAll(".seg-btn")) {
      button.classList.toggle("is-active", button.dataset.view === view);
    }
  }

  function initViewToggle() {
    for (const button of document.querySelectorAll(".seg-btn")) {
      button.addEventListener("click", () => showView(button.dataset.view));
    }
  }

  /* ── Errors ───────────────────────────────────────────────────────── */
  function showErrors(messages) {
    const box = $("errors");
    box.replaceChildren(el("ul", {}, messages.map((m) => el("li", { text: m }))));
    box.hidden = false;
  }

  function clearErrors() {
    $("errors").hidden = true;
    $("errors").replaceChildren();
  }

  /* ── Running ──────────────────────────────────────────────────────── */
  async function run() {
    if (!state.file || state.busy) return;
    state.busy = true;
    clearErrors();
    $("run-btn").disabled = true;
    $("spinner").hidden = false;

    const body = new FormData();
    body.append("image", state.file, state.file.name);
    body.append("settings", JSON.stringify(collectSettings()));

    try {
      const response = await fetch("/api/process", { method: "POST", body });

      if (!response.ok) {
        let messages = [`Processing failed (${response.status}).`];
        const type = response.headers.get("Content-Type") || "";
        if (type.includes("json")) {
          const payload = await response.json().catch(() => null);
          if (payload?.errors?.length) messages = payload.errors;
          else if (payload?.detail) messages = [payload.detail];
          if (payload?.log) setLog(payload.log);
        } else {
          const text = await response.text().catch(() => "");
          if (text) messages = [text.slice(0, 400)];
        }
        showErrors(messages);
        return;
      }

      const blob = await response.blob();
      if (state.afterUrl) URL.revokeObjectURL(state.afterUrl);
      state.afterUrl = URL.createObjectURL(blob);

      $("img-after").src = state.afterUrl;
      showView("after");

      const link = $("download-btn");
      link.href = state.afterUrl;
      link.download = filenameFrom(response) || "shelfready.jpg";
      $("result-meta").textContent = humanSize(blob.size);
      $("result-bar").hidden = false;

      setLog(response.headers.get("X-ShelfReady-Log"));
    } catch (_) {
      showErrors(["Could not reach the server. Check your connection and try again."]);
    } finally {
      state.busy = false;
      state.file && ($("run-btn").disabled = false);
      $("spinner").hidden = true;
    }
  }

  function setLog(text) {
    if (!text) { $("log-box").hidden = true; return; }
    $("log-text").textContent = text;
    $("log-box").hidden = false;
  }

  function filenameFrom(response) {
    const header = response.headers.get("Content-Disposition") || "";
    const match = header.match(/filename="([^"]+)"/);
    return match ? match[1] : null;
  }

  /* ── Start ────────────────────────────────────────────────────────── */
  async function init() {
    initTheme();
    try {
      const response = await fetch("/api/config");
      state.config = await response.json();
    } catch (_) {
      showErrors(["Could not load the settings from the server. Reload to retry."]);
      return;
    }

    buildPlatforms();
    buildDropdowns();
    buildToggles();
    buildAdvanced();
    bindPairedControls();
    initDropzone();
    initViewToggle();

    $("run-btn").addEventListener("click", run);
    $("version").textContent = `v${state.config.version}`;

    // The credit is in the markup so it is there before any JavaScript runs;
    // this only keeps it true to the Python constants the desktop app reads.
    if (state.config.studio) {
      $("studio").href = state.config.studio.url;
      $("studio-name").textContent = state.config.studio.name;
    }

    const exts = state.config.limits.supported_extensions
      .map((e) => e.replace(".", "").toUpperCase()).join(" · ");
    $("dz-hint").textContent =
      `${exts} — up to ${humanSize(state.config.limits.max_upload_bytes)}`;
  }

  init();
})();
