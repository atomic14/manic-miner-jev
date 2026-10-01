// The parts that the viewer pages share.
const $ = id => document.getElementById(id);
const MACROS = ["walk_left", "walk_right", "jump_left", "jump_right", "jump_up", "wait"];
// The two more moves of a run with the setting half_steps.
const HALF_STEPS = ["step_left", "step_right"];
// The moves of a run, from its header.
const movesOfRun = h => (h && h.settings && h.settings.half_steps) ? MACROS.concat(HALF_STEPS) : MACROS;
const USD_PER_TOKEN = 0.042 / 1e6;
const SCALE = 3;  // the canvas is 3 times finer than the game screen, so that lines and labels are sharp
const color = m => getComputedStyle(document.documentElement).getPropertyValue("--" + m).trim();

function escapeHtml(text) {
  return String(text).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
}
// A `name` in back quotes in a text is a field of the state: show it as code.
function withCode(text) {
  return escapeHtml(text).replace(/`([^`]+)`/g, "<code>$1</code>");
}

// -- The header and the help dialog: the same on each page ---------------------------------------
// Each page gives its name in <header class="top" data-page="...">.
const PAGES = [["runs", "/", "Runs"], ["watch", "/watch", "Watch"], ["experiment", "/experiment", "Experiment"]];
function setupHeader() {
  const top = document.querySelector("header.top");
  const page = top.dataset.page;
  top.innerHTML = `<h1><a href="/"><span>jev</span> plays Manic Miner</a></h1>
    <nav class="pages">${PAGES.map(([id, href, name]) =>
      `<a href="${href}" class="${id === page ? "on" : ""}">${name}</a>`).join("")}</nav>
    <div class="spacer"></div>
    <a href="https://docs.typesafe.ai/llms.txt" target="_blank" rel="noopener" class="doc-link">jev documentation</a>
    <button id="open-about" title="How it works">?</button>`;
  document.body.insertAdjacentHTML("beforeend", `<dialog id="dlg-about">
    <div class="dlg-head"><h3>How it works</h3><button data-close>✕</button></div>
    <div class="dlg-body">
      <p><b>jev</b> is a small decision model from TypeSafe. It does not write text: it gets a description of a situation
         and a question, and it selects one answer. Here it plays <b>Manic Miner</b> (ZX Spectrum, 1983).
         Miner Willy must collect all keys in a cavern and then go into the exit portal, and he must stay alive.</p>
      <ol>
        <li>The game stops before each move. The code reads the game memory and writes the facts as JSON. jev gets no picture.</li>
        <li>The code first tries each of the 6 moves in the emulator. jev gets only the valid moves: not a move that kills Willy, goes into a dead end, or has no effect.</li>
        <li>jev selects one move (walk left or right, jump left, right, or up, or wait). The game runs that move, and then stops again.</li>
        <li>Less frequently, jev selects the key that Willy goes to next (the key decision).</li>
        <li>An <b>instruction set</b> has the texts that jev gets with each question. The state and the options are the same
            for each set.</li>
      </ol>
      <p>The pages:</p>
      <ul>
        <li><b>Runs</b>: all recorded runs, with filters, and the totals for each cavern. Select two runs to compare them.</li>
        <li><b>Watch</b>: one run. Each of jev's decisions, with its probabilities and all data that jev got.</li>
        <li><b>Experiment</b>: ask jev for one key decision in a situation that you set up, start a live run, or write
            an instruction set.</li>
      </ul>
      <p class="hint">A replay is free: it makes no jev call. A live run and a question in the key decision lab call jev. They need
         <code>TYPESAFE_API_KEY</code> in the <code>.env</code> file.</p>
    </div></dialog>`);
  $("open-about").onclick = () => $("dlg-about").showModal();
  document.querySelectorAll("dialog [data-close]").forEach(b => b.onclick = () => b.closest("dialog").close());
}
setupHeader();

// -- Words for a run ---------------------------------------------------------------------------
const isComplete = run => run.outcome === "cavern complete";
function outcomeText(outcome) {
  if (!outcome) return "–";
  if (outcome === "cavern complete") return "complete";
  if (outcome.startsWith("stuck")) return "no progress";
  return outcome;
}
function keysText(run) {
  return `${run.keys_collected ?? 0}${run.keys_total ? " of " + run.keys_total : ""}`;
}
function dateText(seconds) {
  if (!seconds) return "–";
  const d = new Date(seconds * 1000);
  return d.toLocaleDateString([], {month: "short", day: "numeric"}) + " " +
    d.toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"});
}
// The decision maker of a run, from its header. Keep this in step with run_mode() in runner.py.
function makerOf(header) {
  const st = header.settings;
  if (header.decision_maker && header.decision_maker !== "jev") return header.decision_maker;
  if (st.random_moves) return "random moves";
  if (st.rule) return "rule: " + st.rule;
  return st.instructions;
}

function bar(name, value, fill, chosen) {
  return `<div class="bar ${chosen ? "chosen" : ""}"><span class="name">${name}</span>
    <span class="track"><span class="fill" style="width:${(value * 100).toFixed(1)}%;background:${fill}"></span></span>
    <span class="val">${value.toFixed(2)}</span></div>`;
}

// -- The data that goes to jev ------------------------------------------------------------------
// The questions of a request in a readable form, with the exact JSON below them.
function questionsHtml(questions) {
  if (!questions) return "";
  const parts = Object.entries(questions).map(([name, q]) => `<div class="question">
    <div class="title">${escapeHtml(name)} <span>· ${escapeHtml(q.type)} · ${(q.instructions || "").split(/\s+/).length} words</span></div>
    <div class="text">${withCode(q.instructions || "")}</div>
    <dl>${Object.entries(q.criteria || {}).map(([k, v]) => `<dt>${escapeHtml(k)}</dt><dd>${withCode(v)}</dd>`).join("")}</dl>
  </div>`);
  return parts.join("") + `<details><summary>The exact JSON of the questions</summary><pre>${
    escapeHtml(JSON.stringify(questions, null, 2))}</pre></details>`;
}

// A state in a readable form: each field with its value. It shows every field of the JSON.
// A list of strings (the map) is a block of rows.
function factsHtml(value) {
  const simple = v => v === null || typeof v !== "object";
  const text = v => `<span class="v">${escapeHtml(v === null ? "none" : String(v))}</span>`;
  const inline = obj => Object.entries(obj).map(([k, v]) => `<span class="kv"><i>${escapeHtml(k)}</i> ${text(v)}</span>`).join(" ");
  const one = v => {
    if (simple(v)) return text(v);
    if (Array.isArray(v)) {
      if (!v.length) return text("none");
      if (v.every(x => typeof x === "string") && v.length > 3) return `<pre class="map">${escapeHtml(v.join("\n"))}</pre>`;
      if (v.every(simple)) return text(v.join(", "));
      return `<ol class="items">${v.map(x => `<li>${one(x)}</li>`).join("")}</ol>`;
    }
    const entries = Object.entries(v);
    if (entries.every(([, x]) => simple(x))) return inline(v);
    return `<dl class="facts">${entries.map(([k, x]) => `<dt>${escapeHtml(k)}</dt><dd>${one(x)}</dd>`).join("")}</dl>`;
  };
  return value && typeof value === "object" && !Array.isArray(value) && !Object.values(value).every(simple)
    ? `<dl class="facts top">${Object.entries(value).map(([k, x]) => `<dt>${escapeHtml(k)}</dt><dd>${one(x)}</dd>`).join("")}</dl>`
    : one(value);
}
// The state of a request twice: in a readable form, and as the exact JSON.
function stateHtml(state) {
  if (!state) return `<p class="hint">No state.</p>`;
  return factsHtml(state) + `<details class="json"><summary>The exact JSON of this state</summary><pre>${
    escapeHtml(JSON.stringify(state, null, 2))}</pre></details>`;
}

// Tabs in a side panel: each button has data-pane with the id of its pane.
function setupTabs(nav, onShow) {
  const buttons = [...nav.querySelectorAll("button")];
  const show = id => {
    buttons.forEach(b => { b.classList.toggle("on", b.dataset.pane === id); $(b.dataset.pane).hidden = b.dataset.pane !== id; });
    if (onShow) onShow(id);
  };
  buttons.forEach(b => b.onclick = () => show(b.dataset.pane));
  show(buttons[0].dataset.pane);
  return show;
}

// The canvas has object-fit: contain. This gives the part of the box that the picture fills.
function pictureRect(canvas) {
  const r = canvas.getBoundingClientRect(), ratio = canvas.width / canvas.height;
  const w = Math.min(r.width, r.height * ratio), h = w / ratio;
  return {left: r.left + (r.width - w) / 2, top: r.top + (r.height - h) / 2, width: w, height: h};
}

// Willy from the screen, with no background. With `rgb`, all his pixels get that colour.
function willyFigure(bitmap, x, y, rgb) {
  const c = new OffscreenCanvas(16, 16), g = c.getContext("2d");
  g.drawImage(bitmap, x, y, 16, 16, 0, 0, 16, 16);
  const img = g.getImageData(0, 0, 16, 16), p = img.data;
  for (let i = 0; i < p.length; i += 4) {
    if (p[i] + p[i + 1] + p[i + 2] === 0) p[i + 3] = 0;  // the background
    else if (rgb) { p[i] = rgb[0]; p[i + 1] = rgb[1]; p[i + 2] = rgb[2]; }
  }
  g.putImageData(img, 0, 0);
  return c;
}
function hexToRgb(hex) { const n = parseInt(hex.slice(1), 16); return [n >> 16, (n >> 8) & 255, n & 255]; }

async function getJson(url, body) {
  const options = body === undefined ? {} :
    {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)};
  return (await fetch(url, options)).json();
}

// The browser can refuse storage (a private window). The pages work with no storage.
const store = {
  get(key) { try { return sessionStorage.getItem(key); } catch { return null; } },
  set(key, value) { try { sessionStorage.setItem(key, value); return true; } catch { return false; } },
  remove(key) { try { sessionStorage.removeItem(key); } catch { /* no storage */ } },
};
