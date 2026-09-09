/* ux2026 shared behaviors — identical on every page. */
(function () {
  "use strict";
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));

  /* Room switching */
  function showRoom(name) {
    $$("[data-room-btn]").forEach(b =>
      b.setAttribute("aria-selected", String(b.dataset.roomBtn === name)));
    $$("[data-room-panel]").forEach(p =>
      p.classList.toggle("on", p.dataset.roomPanel === name));
  }
  $$("[data-room-btn]").forEach(b =>
    b.addEventListener("click", () => showRoom(b.dataset.roomBtn)));
  showRoom(document.body.dataset.defaultRoom || "feedback");

  /* R2: click-outside + Esc dismiss any .dismissable.open */
  document.addEventListener("click", e => {
    $$(".dismissable.open").forEach(d => {
      if (!d.contains(e.target) && !e.target.closest("[data-dismiss-target]")) {
        d.classList.remove("open");
      }
    });
  });
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") {
      $$(".dismissable.open").forEach(d => d.classList.remove("open"));
      $("#palette") && $("#palette").classList.remove("open");
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      const pal = $("#palette");
      if (pal) { pal.classList.add("open"); $("input", pal) && $("input", pal).focus(); }
    }
  });

  /* R4: composer autogrows to ~40vh then scrolls internally; Enter sends */
  $$(".ta").forEach(ta => {
    ta.style.maxHeight = Math.round(window.innerHeight * 0.4) + "px";
    ta.addEventListener("input", () => {
      ta.style.height = "auto";
      ta.style.height = Math.min(ta.scrollHeight, parseInt(ta.style.maxHeight)) + "px";
    });
    ta.addEventListener("keydown", e => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendDemo(ta); }
    });
  });
  $$(".send").forEach(b => b.addEventListener("click", () => {
    const zone = b.closest(".cowrite") || document;
    sendDemo($(".ta", zone) || $(".ta"));
  }));

  /* Demo turn: user bubble + AI reply that streams word-by-word (R3 kicks in on first send) */
  const CANNED = "Sameer here. Scene 3 earns its dawn — but Mara's exit line lands twice: once as subtext at the window, again spelled out to Dev. Cut the second. The silence after \"I kept the key\" is your act break; don't narrate over it.";
  function sendDemo(ta) {
    if (!ta || !ta.value.trim()) return;
    let panel = ta.parentElement;            /* nearest ancestor that owns .thread */
    while (panel && !panel.querySelector(".thread")) panel = panel.parentElement;
    if (!panel) return;
    const tEl = panel.querySelector(".thread");
    const r3 = panel.classList.contains("cowrite") ? panel
             : (panel.querySelector(".cowrite") || panel);
    r3.classList.add("used"); /* R3: collapse explore chips to rail */
    const text = ta.value.trim();
    ta.value = ""; ta.style.height = "auto";
    const u = document.createElement("div");
    u.className = "msg user"; u.textContent = text;
    tEl.appendChild(u);
    const a = document.createElement("div");
    a.className = "msg ai"; a.innerHTML = '<span class="body"></span><span class="cursor"></span>';
    tEl.appendChild(a);
    const words = CANNED.split(" "); let i = 0;
    const timer = setInterval(() => {
      $(".body", a).textContent += (i ? " " : "") + words[i++];
      tEl.scrollTop = 1e9;
      if (i >= words.length) {
        clearInterval(timer);
        $(".cursor", a).remove();
        a.insertAdjacentHTML("beforeend",
          "<span class='grounded'>✓ grounded · Scene 3 — INT. WRITER’S ROOM - DAWN</span>");
      }
    }, 90);
    tEl.scrollTop = 1e9;
  }
  window.__uxSendDemo = sendDemo;

  /* R3: rail "..." restores chips for exploring both states */
  $$(".rail-btn.restore").forEach(b => b.addEventListener("click", () => {
    b.closest(".cowrite").classList.remove("used");
  }));
  /* Chips fill composer with their prompt */
  $$(".chip").forEach(c => c.addEventListener("click", () => {
    const ta = c.closest(".composer-zone").querySelector(".ta");
    ta.value = c.dataset.q || c.textContent.trim();
    ta.dispatchEvent(new Event("input"));
    ta.focus();
  }));
  /* Lens + tab toggles */
  $$(".lens button").forEach(b => b.addEventListener("click", () => {
    $$(".lens button", b.parentElement).forEach(x =>
      x.setAttribute("aria-pressed", String(x === b)));
  }));
  $$(".tabs").forEach(tabs => $$(".tab", tabs).forEach(t => t.addEventListener("click", () => {
    $$(".tab", tabs).forEach(x => x.setAttribute("aria-selected", String(x === t)));
    const target = t.dataset.tabFor;
    if (target) {
      $$(".tabpane", tabs.parentElement).forEach(p =>
        p.classList.toggle("hidden", p.id !== target));
    }
  })));
  /* Modal stubs */
  $$("[data-modal]").forEach(b => b.addEventListener("click", () => {
    $("#" + b.dataset.modal).classList.add("open");
  }));
  $$(".modal-back").forEach(m => m.addEventListener("click", e => {
    if (e.target === m || e.target.closest("[data-close]")) m.classList.remove("open");
  }));
  /* Explicit openers/togglers for dismissable surfaces (R2) */
  $$("[data-dismiss-target]").forEach(b => b.addEventListener("click", () => {
    const t = $(b.dataset.dismissTarget);
    if (t) { const was = t.classList.contains("open");
      $$(".dismissable.open").forEach(d => d.classList.remove("open"));
      t.classList.toggle("open", !was); }
  }));
})();
