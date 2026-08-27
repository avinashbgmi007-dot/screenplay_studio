/* ux2026 v3 kit — primitives & engines. Pages own layout, identity, page-specific logic. */
window.KIT = (function () {
  "use strict";
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const FINE = matchMedia("(pointer: fine)").matches;
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

  /* ---------- inline SVG sprite (zero external requests) ---------- */
  const ICONS = {
    spark:'<path d="M12 4l2.2 5.8L20 12l-5.8 2.2L12 20l-2.2-5.8L4 12l5.8-2.2z"/>',
    send:'<path d="M12 19V5"/><path d="M6 11l6-6 6 6"/>',
    pen:'<path d="M4 20l1.2-4.2L16.4 4.6a2.1 2.1 0 0 1 3 3L8.2 18.8 4 20z"/><path d="M14.5 6.5l3 3"/>',
    film:'<rect x="4" y="5" width="16" height="14" rx="2"/><path d="M8 5v14M16 5v14M4 9.5h4M16 9.5h4M4 14.5h4M16 14.5h4"/>',
    chart:'<path d="M4 20h16"/><path d="M7 16.5v-3M12 16.5V8M17 16.5V11"/>',
    bulb:'<path d="M9.5 18h5M10.5 21h3"/><path d="M12 3a6 6 0 0 1 3.9 10.6c-.7.6-.9 1.4-.9 2.4H9c0-1-.2-1.8-.9-2.4A6 6 0 0 1 12 3z"/>',
    book:'<path d="M7 3h12a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H7a3 3 0 0 1-3-3V6a3 3 0 0 1 3-3z"/><path d="M4 17a3 3 0 0 1 3-3h13"/>',
    folder:'<path d="M3 7a2 2 0 0 1 2-2h4l2 2.3h8a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"/>',
    gear:'<circle cx="12" cy="12" r="3.2"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M18.7 5.3l-2.1 2.1M7.4 16.6l-2.1 2.1"/>',
    sun:'<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5 5l1.4 1.4M17.6 17.6L19 19M19 5l-1.4 1.4M6.4 17.6L5 19"/>',
    moon:'<path d="M20 14.5A8.5 8.5 0 1 1 9.5 4 7 7 0 0 0 20 14.5z"/>',
    search:'<circle cx="11" cy="11" r="6.5"/><path d="M20.5 20.5L16 16"/>',
    undo:'<path d="M4.5 9.5H14a4.5 4.5 0 0 1 0 9h-4"/><path d="M8 5.5l-4 4 4 4"/>',
    redo:'<path d="M19.5 9.5H10a4.5 4.5 0 0 0 0 9h4"/><path d="M16 5.5l4 4-4 4"/>',
    download:'<path d="M12 4v11M7.5 10.5L12 15l4.5-4.5M5 19.5h14"/>',
    print:'<path d="M7 8V4h10v4"/><rect x="4" y="8" width="16" height="8" rx="1.5"/><path d="M7 13.5h10V21H7z"/>',
    x:'<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>',
    chevd:'<path d="M6.5 9.5l5.5 5.5 5.5-5.5"/>',
    more:'<circle cx="5.5" cy="12" r="1.4" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none"/><circle cx="18.5" cy="12" r="1.4" fill="currentColor" stroke="none"/>',
    check:'<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    alert:'<path d="M12 4l9 15.5H3L12 4z"/><path d="M12 10.5v4M12 17.2v.01"/>',
    clock:'<circle cx="12" cy="12" r="8"/><path d="M12 7.5V12l3 2"/>',
    branch:'<circle cx="7" cy="5.5" r="2"/><circle cx="7" cy="18.5" r="2"/><circle cx="17" cy="5.5" r="2"/><path d="M7 7.5v9M17 7.5v.8a4.2 4.2 0 0 1-4.2 4.2H10"/>',
    home:'<path d="M4.5 11L12 4.5 19.5 11"/><path d="M6.5 9.5V19.5h11V9.5"/>',
    plus:'<path d="M12 5.5v13M5.5 12h13"/>',
    minus:'<path d="M6 12h12"/>',
    fit:'<path d="M4 9.5V4h5.5M20 9.5V4h-5.5M4 14.5V20h5.5M20 14.5V20h-5.5"/>',
    list:'<path d="M9 6h11M9 12h11M9 18h11"/><path d="M4.5 6h.01M4.5 12h.01M4.5 18h.01"/>',
    board:'<rect x="4" y="4" width="7" height="8" rx="1.5"/><rect x="13" y="4" width="7" height="4.5" rx="1.5"/><rect x="13" y="10.5" width="7" height="9.5" rx="1.5"/><rect x="4" y="14" width="7" height="6" rx="1.5"/>',
    pin:'<path d="M12 21s-6.5-5.4-6.5-10.2A6.5 6.5 0 0 1 12 4.3a6.5 6.5 0 0 1 6.5 6.5C18.5 15.6 12 21 12 21z"/><circle cx="12" cy="10.8" r="2.3"/>',
    chat:'<path d="M20.5 7A2.5 2.5 0 0 0 18 4.5H6A2.5 2.5 0 0 0 3.5 7v7A2.5 2.5 0 0 0 6 16.5h1v4l5-4h6a2.5 2.5 0 0 0 2.5-2.5V7z"/>',
    user:'<circle cx="12" cy="8" r="3.8"/><path d="M4.5 20c1.6-3.6 4.3-5.4 7.5-5.4s5.9 1.8 7.5 5.4"/>',
    play:'<path d="M8 5.5l11 6.5-11 6.5v-13z"/>',
    refresh:'<path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3L20 9.5"/><path d="M20 4.5v5h-5"/>',
    file:'<path d="M6.5 3h7L18.5 8v13h-12V3z"/><path d="M13.5 3v5h5"/>',
    jump:'<path d="M7 17L17 7"/><path d="M9 7h8v8"/>',
    eye:'<path d="M2.5 12S6 5.8 12 5.8 21.5 12 21.5 12 18 18.2 12 18.2 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.6"/>',
    cut:'<circle cx="7" cy="7" r="2.4"/><circle cx="7" cy="17" r="2.4"/><path d="M9 8.6L20 19M9 15.4L20 5"/>',
    note:'<path d="M5 4h14v10.5L14.5 20H5V4z"/><path d="M14.5 20v-5.5H19"/>',
    compare:'<rect x="4" y="5" width="6.5" height="14" rx="1.5"/><rect x="13.5" y="5" width="6.5" height="14" rx="1.5"/><path d="M12 3.5v17"/>',
    zap:'<path d="M13 3L5 13.5h5.5L10 21l8-10.5h-5.5L13 3z"/>',
    quote:'<path d="M7.5 7H11v3.5c0 2.6-1 4.2-3 5.3l-1.2-1.6c1.3-.7 1.9-1.5 2.1-2.7H7.5V7z"/><path d="M15.5 7H19v3.5c0 2.6-1 4.2-3 5.3l-1.2-1.6c1.3-.7 1.9-1.5 2.1-2.7h-1.4V7z"/>',
    cmd:'<rect x="9.5" y="9.5" width="5" height="5" rx="1"/><path d="M9.5 9.5H8a2 2 0 1 1 1.5-1.93V9.5zM14.5 9.5H16a2 2 0 1 0-1.5-1.93V9.5zM9.5 14.5H8a2 2 0 1 0 1.5 1.93V14.5zM14.5 14.5H16a2 2 0 1 1-1.5 1.93V14.5z"/>',
    globe:'<circle cx="12" cy="12" r="8"/><path d="M4 12h16M12 4c2.3 2.2 3.4 5 3.4 8s-1.1 5.8-3.4 8c-2.3-2.2-3.4-5-3.4-8s1.1-5.8 3.4-8z"/>',
    grip:'<circle cx="9" cy="7" r="1.2" fill="currentColor" stroke="none"/><circle cx="15" cy="7" r="1.2" fill="currentColor" stroke="none"/><circle cx="9" cy="12" r="1.2" fill="currentColor" stroke="none"/><circle cx="15" cy="12" r="1.2" fill="currentColor" stroke="none"/><circle cx="9" cy="17" r="1.2" fill="currentColor" stroke="none"/><circle cx="15" cy="17" r="1.2" fill="currentColor" stroke="none"/>',
    aright:'<path d="M5 12h13"/><path d="M13 6.5l5.5 5.5-5.5 5.5"/>',
    up:'<path d="M12 19V5M6 11l6-6 6 6"/>',
    down:'<path d="M12 5v14M6 13l6 6 6-6"/>'
  };
  function icons() {
    if ($("#kit-sprite")) return;
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.id = "kit-sprite";
    svg.setAttribute("style", "display:none");
    svg.innerHTML = Object.entries(ICONS).map(([k, v]) =>
      `<symbol id="i-${k}" viewBox="0 0 24 24">${v}</symbol>`).join("");
    document.body.prepend(svg);
  }
  const ic = (name, cls) =>
    `<svg class="ic ${cls || ""}" aria-hidden="true"><use href="#i-${name}"/></svg>`;

  /* ---------- reveals & staggers ---------- */
  let io;
  function reveal(root) {
    io = io || new IntersectionObserver(es => es.forEach(e => {
      if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
    }), { threshold: .12 });
    $$("[data-reveal]", root).forEach(el => io.observe(el));
  }
  function stagger(root) {
    $$("[data-stagger]", root).forEach(p =>
      Array.from(p.children).forEach((c, i) => c.style.setProperty("--i", i)));
  }

  /* ---------- count-up ---------- */
  function countUp(el, to, dur) {
    dur = dur || 1100;
    if (REDUCED) { el.textContent = to; return; }
    const t0 = performance.now(), ease = x => 1 - Math.pow(1 - x, 4);
    (function f(t) {
      const p = clamp((t - t0) / dur, 0, 1);
      el.textContent = Math.round(to * ease(p));
      if (p < 1) requestAnimationFrame(f);
    })(t0);
  }

  /* ---------- R2: popovers (.pop toggled via [data-pop="#id"]) ---------- */
  function dismissAll(except) {
    $$(".pop.open").forEach(p => { if (p !== except) p.classList.remove("open"); });
  }
  function pops() {
    document.addEventListener("click", e => {
      const btn = e.target.closest("[data-pop]");
      if (btn) {
        const t = $(btn.dataset.pop);
        const was = t.classList.contains("open");
        dismissAll();
        t.classList.toggle("open", !was);
        e.stopPropagation();
        return;
      }
      if (!e.target.closest(".pop")) dismissAll();
    });
    document.addEventListener("keydown", e => { if (e.key === "Escape") dismissAll(); });
  }

  /* ---------- modals ([data-modal="#id"], [data-close]) ---------- */
  function modals() {
    document.addEventListener("click", e => {
      const opener = e.target.closest("[data-modal]");
      if (opener) { $(opener.dataset.modal).classList.add("open"); return; }
      const closer = e.target.closest("[data-close]");
      if (closer) { closer.closest(".modal-back").classList.remove("open"); return; }
      if (e.target.classList && e.target.classList.contains("modal-back"))
        e.target.classList.remove("open");
    });
    document.addEventListener("keydown", e => {
      if (e.key === "Escape") $$(".modal-back.open").forEach(m => m.classList.remove("open"));
    });
  }

  /* ---------- cursor spotlight ---------- */
  function spotlight(el) {
    if (REDUCED || !FINE) { el.style.display = "none"; return; }
    document.addEventListener("pointermove", e => {
      el.style.setProperty("--gx", e.clientX + "px");
      el.style.setProperty("--gy", e.clientY + "px");
    }, { passive: true });
  }

  /* ---------- view transitions ---------- */
  function vt(update) {
    if (document.startViewTransition && !REDUCED) document.startViewTransition(update);
    else update();
  }

  /* ---------- word streaming into a thread message ---------- */
  function stream(msgEl, text, done) {
    const words = text.split(" ");
    let i = 0;
    const caret = document.createElement("span");
    caret.className = "caret";
    msgEl.appendChild(caret);
    const tick = () => {
      const s = document.createElement("span");
      s.className = "w";
      s.textContent = words[i] + (i < words.length - 1 ? " " : "");
      msgEl.insertBefore(s, caret);
      i++;
      if (i < words.length) setTimeout(tick, REDUCED ? 0 : 34 + Math.random() * 60);
      else { caret.remove(); done && done(); }
    };
    REDUCED ? (msgEl.textContent = text, done && done()) : tick();
  }

  /* ---------- R3+R4 chat engine ----------
     opts: zone (gets .used after first send), thread, ta, sendBtn?, reply?,
           grounded?, onSend?(text), chips container uses [data-q] */
  function chat(o) {
    const ta = o.ta, thread = o.thread, zone = o.zone;
    function grow() {
      ta.style.height = "auto";
      ta.style.height = Math.min(ta.scrollHeight, Math.round(innerHeight * .4)) + "px";
      ta.style.overflowY = ta.scrollHeight > Math.round(innerHeight * .4) ? "auto" : "hidden";
    }
    ta.addEventListener("input", grow);
    ta.addEventListener("keydown", e => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
    });
    if (o.sendBtn) o.sendBtn.addEventListener("click", send);
    /* chips fill composer */
    $$("[data-q]", zone).forEach(c => c.addEventListener("click", () => {
      ta.value = c.dataset.q; grow(); ta.focus();
    }));
    /* rail restore ("···") */
    const restore = $(".rail-restore", zone);
    if (restore) restore.addEventListener("click", () => zone.classList.remove("used"));
    function bubble(cls, html) {
      const m = document.createElement("div");
      m.className = "msg " + cls;
      m.innerHTML = html;
      thread.appendChild(m);
      thread.scrollTop = thread.scrollHeight;
      return m;
    }
    function send() {
      const text = ta.value.trim();
      if (!text) return;
      zone.classList.add("used");               /* R3 lifecycle trigger */
      bubble("user", "").textContent = text;
      ta.value = ""; grow(); dismissAll();
      const ai = bubble("ai", "");
      o.onSend && o.onSend(text);
      stream(ai, o.reply || REPLY, () => {
        if (o.grounded !== false)
          ai.insertAdjacentHTML("beforeend",
            `<span class="grounded">${ic("check")} grounded · Scene 3 — INT. WRITER’S ROOM — DAWN</span>`);
        thread.scrollTop = thread.scrollHeight;
        o.onDone && o.onDone(ai);
      });
      thread.scrollTop = thread.scrollHeight;
    }
    return { send, bubble };
  }
  const REPLY = "Sameer here. Scene 3 earns its dawn — but Mara’s exit line lands twice: once as subtext at the window, then spelled out to Dev. Cut the second. The silence after “I kept the key” is your act break; don’t narrate over it.";

  /* ---------- command palette engine ----------
     opts: root (#palette wrapper), input, list, commands[{id,g,label,hint,icon,kbd,run}],
           recents? (array persisted per page) */
  function palette(o) {
    const root = o.root, input = o.input, list = o.list;
    const cmds = o.commands, groups = [];
    let active = 0, shown = [];
    cmds.forEach(c => { if (!groups.includes(c.g)) groups.push(c.g); });
    function render(q) {
      q = q.trim().toLowerCase();
      let pool = cmds;
      if (q) pool = cmds.filter(c =>
        (c.label + " " + (c.hint || "") + " " + c.g).toLowerCase().includes(q));
      let html = "", idx = 0; shown = [];
      const emit = (title, items) => {
        html += `<div class="pal-g">${title}</div>`;
        items.forEach(c => {
          const lab = q ? hl(c.label, q) : c.label;
          html += `<button class="pal-it${idx === active ? " on" : ""}" data-i="${idx}">
            ${c.icon ? ic(c.icon) : ic("aright")}<span class="pl">${lab}</span>
            ${c.hint ? `<span class="ph">${c.hint}</span>` : ""}
            ${c.kbd ? `<kbd>${c.kbd}</kbd>` : ""}</button>`;
          shown.push(c); idx++;
        });
      };
      if (!q && o.recents && o.recents.length) {
        const r = o.recents.map(id => cmds.find(c => c.id === id)).filter(Boolean).slice(0, 3);
        if (r.length) emit("Recent", r);
      }
      groups.forEach(g => {
        const items = pool.filter(c => c.g === g);
        if (items.length) emit(g, items);
      });
      list.innerHTML = html || `<div class="pal-empty">No matches — try “export”, “scene”, “analysis”…</div>`;
      list.querySelectorAll(".pal-it").forEach(b => {
        b.addEventListener("mouseenter", () => setActive(+b.dataset.i, false));
        b.addEventListener("click", () => run(shown[+b.dataset.i]));
      });
      list.scrollTop = 0;
    }
    function hl(label, q) {
      const i = label.toLowerCase().indexOf(q);
      if (i < 0) return label;
      return label.slice(0, i) + "<b>" + label.slice(i, i + q.length) + "</b>" +
        label.slice(i + q.length);
    }
    function setActive(i, scroll) {
      active = clamp(i, 0, shown.length - 1);
      list.querySelectorAll(".pal-it").forEach(b =>
        b.classList.toggle("on", +b.dataset.i === active));
      if (scroll) {
        const el = list.querySelector(`.pal-it[data-i="${active}"]`);
        el && el.scrollIntoView({ block: "nearest" });
      }
    }
    function run(c) {
      if (!c) return;
      close();
      if (o.recents) { o.recents.unshift(c.id); o.recents = [...new Set(o.recents)].slice(0, 5); }
      setTimeout(() => c.run(), REDUCED ? 0 : 60);
    }
    function open(preset) {
      root.classList.add("open");
      input.value = preset || "";
      active = 0;
      render(input.value);
      input.focus();
    }
    function close() { root.classList.remove("open"); }
    function toggle(preset) { root.classList.contains("open") ? close() : open(preset); }
    root.addEventListener("mousedown", e => { if (e.target === root) close(); });
    input.addEventListener("input", () => { active = 0; render(input.value); });
    input.addEventListener("keydown", e => {
      if (e.key === "ArrowDown") { e.preventDefault(); setActive(active + 1, true); }
      else if (e.key === "ArrowUp") { e.preventDefault(); setActive(active - 1, true); }
      else if (e.key === "Enter") { e.preventDefault(); run(shown[active]); }
    });
    render("");
    return { open, close, toggle };
  }

  /* ---------- toast ---------- */
  function toast(msg, icon) {
    let host = $(".toasts");
    if (!host) { host = document.createElement("div"); host.className = "toasts"; document.body.appendChild(host); }
    const t = document.createElement("div");
    t.className = "toast";
    t.innerHTML = ic(icon || "check") + "<span></span>";
    t.lastElementChild.textContent = msg;
    host.appendChild(t);
    setTimeout(() => { t.classList.add("out"); setTimeout(() => t.remove(), 320); }, 2600);
  }

  /* ---------- mm:ss ticker ---------- */
  function ticker(el, startSec) {
    let s = startSec;
    const f = () => {
      const m = String(Math.floor(s / 60)).padStart(2, "0"), ss = String(s % 60).padStart(2, "0");
      el.textContent = m + ":" + ss; s++;
    };
    f(); setInterval(f, 1000);
  }

  return { $, $$, REDUCED, FINE, clamp, icons, ic, reveal, stagger, countUp,
           pops, modals, dismissAll, spotlight, vt, stream, chat, palette, toast, ticker, REPLY };
})();
