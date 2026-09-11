// Nut sao chep: doc noi dung tu <template id="prompt-<key>">, khong hardcode tung skill.
// Them skill moi = them mot <template> + mot nut, khong phai sua file nay.
const status = document.querySelector("#copy-status");

document.querySelectorAll("[data-copy-prompt]").forEach((button) => {
  button.addEventListener("click", async () => {
    const template = document.querySelector(`#prompt-${button.dataset.copyPrompt}`);
    if (!template) {
      status.textContent = "Khong tim thay noi dung de sao chep.";
      return;
    }
    try {
      await navigator.clipboard.writeText(template.content.textContent.trim());
      status.textContent = "Đã sao chép. Hãy dán vào AI của bạn.";
    } catch {
      status.textContent = "Không thể tự sao chép; hãy bôi đen nội dung bên trên.";
    }
  });
});

// ---------------------------------------------------------------------------
// Ban do kho. Khu skill duoc dung tu chinh cac <section data-skill-id> ma
// tools/sync_site.py sinh ra -> them skill moi thi ban do tu co them khu,
// khong ai phai sua file nay hay sua SVG bang tay.
// ---------------------------------------------------------------------------
const SVG_NS = "http://www.w3.org/2000/svg";

function svg(tag, attrs, text) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs || {})) node.setAttribute(key, value);
  if (text !== undefined) node.textContent = text;
  return node;
}

function shorten(text, limit) {
  const clean = text.trim().replace(/\.$/, "");
  return clean.length > limit ? `${clean.slice(0, limit - 1).trimEnd()}…` : clean;
}

function buildBays(bays) {
  const sections = [...document.querySelectorAll("[data-skill-id]")];
  if (!sections.length) return [];

  const LEFT = 170, RIGHT = 700, GAP = 22, TOP = 330, HEIGHT = 76;
  const width = Math.min(190, (RIGHT - LEFT - GAP * (sections.length - 1)) / sections.length);

  return sections.map((section, index) => {
    const id = section.dataset.skillId;
    const heading = section.querySelector("h2")?.textContent ?? id;
    const purpose = heading.includes("—") ? heading.split("—").slice(1).join("—") : "";
    const x = LEFT + index * (width + GAP);

    const group = svg("g", {
      class: "bay", tabindex: "0", role: "link",
      transform: `translate(${x} ${TOP})`,
      "data-target": id,
      "aria-label": `Khu ${id}: ${shorten(purpose || heading, 60)}`,
    });
    group.dataset.title = `/${id}`;
    group.dataset.cost = "khu skill";
    group.dataset.note = `${shorten(purpose || heading, 120)}. Bấm vào khu này để xem cách gọi.`;

    group.append(
      svg("path", { class: "bay-link", d: `M ${width / 2} 0 V -30` }),
      svg("rect", { class: "bay-box", width, height: HEIGHT, rx: 14 }),
      svg("text", { class: "bay-tag", x: width / 2, y: 30 }, `/${id}`),
      svg("text", { class: "bay-sub", x: width / 2, y: 54 }, shorten(purpose || "khu skill", 24)),
    );
    bays.append(group);
    return group;
  });
}

function setupMap() {
  const bayLayer = document.querySelector("#map-bays");
  const info = document.querySelector("#map-info");
  if (!bayLayer || !info) return;

  const spots = [...document.querySelectorAll(".station"), ...buildBays(bayLayer)];
  const seen = new Set();
  const counter = document.querySelector("#map-count");
  const total = document.querySelector("#map-total");
  if (total) total.textContent = String(spots.length);

  const show = (spot) => {
    if (!seen.has(spot)) {
      seen.add(spot);
      spot.classList.add("is-seen");
      if (counter) counter.textContent = String(seen.size);
    }
    spots.forEach((other) => other.classList.toggle("is-active", other === spot));
    info.innerHTML = "";
    const title = document.createElement("p");
    title.className = "map-info-title";
    title.textContent = spot.dataset.title;
    const cost = document.createElement("p");
    cost.className = "map-info-cost";
    cost.textContent = spot.dataset.cost;
    const note = document.createElement("p");
    note.className = "map-info-note";
    note.textContent = spot.dataset.note;
    info.append(title, cost, note);
  };

  const go = (spot) => {
    const target = spot.dataset.target && document.querySelector(`#${spot.dataset.target}`);
    if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  spots.forEach((spot) => {
    spot.addEventListener("mouseenter", () => show(spot));
    spot.addEventListener("focus", () => show(spot));
    spot.addEventListener("click", () => { show(spot); go(spot); });
    spot.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      show(spot);
      go(spot);
    });
  });
}

setupMap();
