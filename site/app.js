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

// ---------------------------------------------------------------------------
// Truong sao 3 chieu cho hero. Canvas 2D, khong thu vien - CSP chan moi CDN nen
// khong co three.js o day, va cung khong can: chieu phoi canh la mot phep chia.
//
// Vong lap CHI chay khi hero dang nam trong man hinh va tab dang hien. Khong co
// hai cai khoa do thi trang van dot CPU/pin khi nguoi ta da cuon xuong duoi hoac
// chuyen sang tab khac.
// ---------------------------------------------------------------------------
function setupStarfield() {
  const canvas = document.querySelector(".starfield");
  const ctx = canvas && canvas.getContext("2d");
  if (!ctx) return;

  const SAU = 900;                       // do sau cua khoi khong gian
  const TIEU_CU = 380;                   // tieu cu: lon hon = goc hep hon
  const MAU = ["#FFFFFF", "#9BE7F5", "#FFC400", "#D8F5FA"];
  const itMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  let sao = [], rong = 0, cao = 0, khung = 0, dangChay = false;
  let camX = 0, camY = 0, dichX = 0, dichY = 0;

  const GAN = 90;                        // z nho nhat: gan hon nua thi sao to nhu cuc bong
  const TOC = .22;                       // toc do troi NGANG trong khong gian

  const moi = () => ({
    // 62% so sao bi nen quanh mot mat phang -> thanh dai ngan ha, khong phai bui deu
    x: (Math.random() - .5) * rong * 1.8,
    y: (Math.random() - .5) * cao * (Math.random() < .62 ? .42 : 1.5),
    z: GAN + Math.random() * (SAU - GAN),
    mau: MAU[(Math.random() * MAU.length) | 0],
    co: .35 + Math.random() * .95,
  });

  function doLai() {
    const hop = canvas.getBoundingClientRect();
    rong = hop.width;
    cao = hop.height;
    if (!rong || !cao) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(rong * dpr);
    canvas.height = Math.round(cao * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    // Mat do theo dien tich, co tran tren va duoi: dien thoai ~200, desktop ~600.
    const soSao = Math.round(Math.min(820, Math.max(220, (rong * cao) / 1200)));
    sao = Array.from({ length: soSao }, moi);
  }

  function ve(troi) {
    ctx.clearRect(0, 0, rong, cao);
    camX += (dichX - camX) * .045;
    camY += (dichY - camY) * .045;
    const gx = rong / 2, gy = cao / 2;

    for (const s of sao) {
      // Troi NGANG, khong lao vao man hinh: lao thang la hieu ung duong ham, nhin lau chong mat.
      // Chieu sau chi con lam thi sai - sao gan troi nhanh, sao xa gan nhu dung yen.
      if (troi) s.x -= TOC;
      const k = TIEU_CU / s.z;
      let x = gx + (s.x - camX) * k;
      const y = gy + (s.y - camY) * k;
      // Ra khoi mep trai thi day sang phai DUNG mot man hinh, giu nguyen do sau -> khong thay nhay.
      if (x < -40) {
        s.x += (rong + 80) / k;
        x = gx + (s.x - camX) * k;
      }
      if (x > rong + 40 || y < -30 || y > cao + 30) continue;
      ctx.globalAlpha = Math.min(1, (1 - s.z / SAU) * 1.7);
      ctx.fillStyle = s.mau;
      ctx.beginPath();
      ctx.arc(x, y, Math.min(2.6, Math.max(.35, s.co * k)), 0, 6.2832);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  function vongLap() {
    ve(true);
    khung = requestAnimationFrame(vongLap);
  }

  function chay() {
    if (dangChay || itMotion.matches) return;
    dangChay = true;
    khung = requestAnimationFrame(vongLap);
  }

  function dung() {
    dangChay = false;
    cancelAnimationFrame(khung);
  }

  doLai();
  ve(false);                             // mot khung tinh: reduced-motion dung o day

  // Do lai mot lan nua khi load xong: neu CSS ve sau JS thi lan do dau tien ra
  // kich thuoc mac dinh 300x150 va truong sao ket o do.
  window.addEventListener("load", () => { doLai(); if (!dangChay) ve(false); });
  window.addEventListener("resize", () => { doLai(); ve(false); });
  document.addEventListener("visibilitychange", () => (document.hidden ? dung() : chay()));
  itMotion.addEventListener("change", () => (itMotion.matches ? dung() : chay()));

  const hero = canvas.closest("section");
  hero.addEventListener("pointermove", (e) => {
    const hop = hero.getBoundingClientRect();
    dichX = ((e.clientX - hop.left) / hop.width - .5) * 190;
    dichY = ((e.clientY - hop.top) / hop.height - .5) * 130;
  });
  hero.addEventListener("pointerleave", () => { dichX = 0; dichY = 0; });

  new IntersectionObserver(
    ([muc]) => (muc.isIntersecting && !document.hidden ? chay() : dung()),
    { threshold: 0 },
  ).observe(hero);
}

setupStarfield();
