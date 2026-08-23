"""Patch app.js: context card + conditional hint in renderMessages."""
import io

p = "screenplay_studio/webapp/app.js"
src = io.open(p, encoding="utf-8").read()

old = '''function renderMessages() {
  const container = $("#messages-scroll");
  container.innerHTML = "";
  const msgs = currentBranchData().messages || [];
  if (!msgs.length) {
    const hint = el("div", "chat-empty-hint");
    if (state.inIdea) {
      hint.innerHTML =
        "This is the idea desk \\u2014 no pages yet, and that's the point. Talk the idea through with Sameer " +
        "(he probes before he suggests), then flip to <em>Feedback</em> to have the premise doctor " +
        "stress-test it. Save the premise card as it sharpens \\u2014 it rides with every turn and " +
        "carries into the script when you upload the first pages.";
    } else {'''

new = '''function renderMessages() {
  const container = $("#messages-scroll");
  container.innerHTML = "";
  // the context card: PROOF Sameer has the page -- word count + a peek at
  // the actual material he is reading. Deterministic UI evidence.
  if (state.inIdea && state.currentIdea) {
    const content = (state.currentIdea.content || "").trim();
    if (content) {
      const words = content.split(/\\s+/).length;
      const card = el("div", "idea-context-card");
      const head = el("div", "idea-context-head");
      const label = el("span", "idea-context-label",
        "\\ud83d\\udcc4 Sameer has your idea page in front of him \\u2014 " + words +
        " word" + (words === 1 ? "" : "s") + " in context. No need to repeat it.");
      const toggle = el("button", "idea-context-toggle", "show");
      toggle.type = "button";
      const snap = el("div", "idea-context-snap");
      snap.hidden = true;
      snap.textContent = content;
      toggle.addEventListener("click", () => {
        snap.hidden = !snap.hidden;
        toggle.textContent = snap.hidden ? "show" : "hide";
      });
      head.appendChild(label);
      head.appendChild(toggle);
      card.appendChild(head);
      card.appendChild(snap);
      container.appendChild(card);
    }
  }
  const msgs = currentBranchData().messages || [];
  if (!msgs.length) {
    const hint = el("div", "chat-empty-hint");
    if (state.inIdea) {
      const hasPage = state.currentIdea && (state.currentIdea.content || "").trim();
      hint.innerHTML = hasPage
        ? "He\\u2019s read every word of your page \\u2014 start anywhere, or ask what snagged him. Flip to <em>Feedback</em> when you want the premise doctor to stress-test it."
        : "This is the idea desk \\u2014 no pages yet, and that\\'s the point. Talk the idea through with Sameer " +
          "(he probes before he suggests), then flip to <em>Feedback</em> to have the premise doctor " +
          "stress-test it. Save the premise card as it sharpens \\u2014 it rides with every turn and " +
          "carries into the script when you upload the first pages.";
    } else {'''

assert src.count(old) == 1, f"renderMessages anchor: {src.count(old)}"
src = src.replace(old, new)
io.open(p, "w", encoding="utf-8").write(src)
print("app.js patched")
