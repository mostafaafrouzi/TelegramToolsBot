/* Tele2Rub Mini App — shared Telegram WebApp helpers */
(function (global) {
  const tg = global.Telegram && global.Telegram.WebApp;

  const STR = {
    fa: {
      loading: "در حال بارگذاری…",
      error: "خطا",
      copy: "کپی",
      copied: "کپی شد",
      back: "خانه",
      home_title: "Tele2Rub",
      home_sub: "ابزارهای شبکه و کاربردی — روی دستگاه شما یا از سرور ربات.",
      device: "از دستگاه شما",
      server: "از سرور ربات",
      compare: "مقایسه",
      run: "اجرا",
      empty: "هنوز نتیجه‌ای نیست.",
      api_fail: "API سرور در دسترس نیست.",
      not_icmp: "این ICMP واقعی نیست؛ اندازه‌گیری از مرورگر شماست.",
      from_vps: "این تست از VPS ربات اجرا می‌شود.",
    },
    en: {
      loading: "Loading…",
      error: "Error",
      copy: "Copy",
      copied: "Copied",
      back: "Home",
      home_title: "Tele2Rub",
      home_sub: "Network & utility tools — from your device or the bot server.",
      device: "From your device",
      server: "From bot server",
      compare: "Compare",
      run: "Run",
      empty: "No result yet.",
      api_fail: "Server API unavailable.",
      not_icmp: "Not real ICMP — measured from your browser.",
      from_vps: "This test runs on the bot VPS.",
    },
  };

  function lang() {
    const code =
      (tg && tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.language_code) ||
      "fa";
    return code.startsWith("en") ? "en" : "fa";
  }

  function t(key) {
    const L = STR[lang()] || STR.fa;
    return L[key] || STR.en[key] || key;
  }

  function isDarkTheme() {
    try {
      const bg = (tg && tg.themeParams && tg.themeParams.bg_color) || "";
      if (!bg) return false;
      const hex = bg.replace("#", "");
      if (hex.length < 6) return false;
      const r = parseInt(hex.slice(0, 2), 16);
      const g = parseInt(hex.slice(2, 4), 16);
      const b = parseInt(hex.slice(4, 6), 16);
      return (r + g + b) / 3 < 100;
    } catch (e) {
      return false;
    }
  }

  function initApp() {
    if (tg) {
      tg.ready();
      tg.expand();
      if (tg.enableClosingConfirmation) tg.enableClosingConfirmation();
      try {
        if (tg.setHeaderColor) tg.setHeaderColor("secondary_bg_color");
        if (tg.setBackgroundColor) tg.setBackgroundColor("bg_color");
      } catch (e) { /* ignore */ }
    }
    const rtl = lang() === "fa";
    document.body.classList.add(rtl ? "rtl" : "ltr");
    if (isDarkTheme()) document.body.classList.add("tg-dark");
    document.documentElement.lang = lang();
    document.documentElement.dir = rtl ? "rtl" : "ltr";
  }

  function shell(title, backHref) {
    let root = document.getElementById("app");
    if (!root) {
      root = document.createElement("div");
      root.id = "app";
      root.className = "app-shell";
      while (document.body.firstChild) root.appendChild(document.body.firstChild);
      document.body.appendChild(root);
    } else {
      root.classList.add("app-shell");
    }
    const hdr = document.getElementById("hdr");
    if (hdr) {
      hdr.innerHTML = "";
      hdr.appendChild(header(title, backHref));
    }
    return root;
  }

  function header(title, backHref) {
    const wrap = document.createElement("header");
    wrap.className = "app-header";
    if (backHref) {
      const a = document.createElement("a");
      a.className = "back-link";
      a.href = backHref;
      a.textContent = (lang() === "fa" ? "→ " : "← ") + t("back");
      wrap.appendChild(a);
    }
    const h1 = document.createElement("h1");
    h1.textContent = title;
    wrap.appendChild(h1);
    return wrap;
  }

  function badge(kind) {
    const el = document.createElement("div");
    el.className = "badge " + (kind === "server" ? "server" : "device");
    el.textContent = kind === "server" ? t("server") : t("device");
    return el;
  }

  function segmented(container, items, onChange, initial) {
    container.innerHTML = "";
    container.className = "segmented";
    let active = initial || (items[0] && items[0].id);
    const buttons = [];
    items.forEach((it) => {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = it.label;
      b.dataset.id = it.id;
      if (it.id === active) b.classList.add("active");
      b.onclick = () => {
        active = it.id;
        buttons.forEach((x) => x.classList.toggle("active", x.dataset.id === active));
        onChange(active);
      };
      buttons.push(b);
      container.appendChild(b);
    });
    return {
      get: () => active,
      set: (id) => {
        active = id;
        buttons.forEach((x) => x.classList.toggle("active", x.dataset.id === active));
      },
    };
  }

  function setResult(el, text, state) {
    if (!el) return;
    el.className = "result" + (state ? " " + state : "");
    el.textContent = text == null || text === "" ? t("empty") : String(text);
  }

  function setResultHtml(el, html, state) {
    if (!el) return;
    el.className = "result" + (state ? " " + state : "");
    el.innerHTML = html;
  }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      if (tg && tg.showPopup) tg.showPopup({ message: t("copied") });
      else if (tg && tg.showAlert) tg.showAlert(t("copied"));
      return true;
    } catch (e) {
      return false;
    }
  }

  function addCopyButton(container, getText) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn secondary";
    btn.textContent = t("copy");
    btn.onclick = () => copyText(typeof getText === "function" ? getText() : getText);
    container.appendChild(btn);
    return btn;
  }

  async function fetchJson(url, opts) {
    const r = await fetch(url, opts);
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }

  async function publicIp() {
    const j = await fetchJson("https://api.ipify.org?format=json");
    return j.ip || "";
  }

  async function ipDetails(ip) {
    const url = ip ? "https://ipwho.is/" + encodeURIComponent(ip) : "https://ipwho.is/";
    const j = await fetchJson(url);
    if (j.success === false) throw new Error(j.message || "lookup failed");
    return j;
  }

  async function dnsQuery(name, type) {
    const url =
      "https://cloudflare-dns.com/dns-query?name=" +
      encodeURIComponent(name) +
      "&type=" +
      encodeURIComponent(type);
    const r = await fetch(url, { headers: { Accept: "application/dns-json" } });
    if (!r.ok) throw new Error("DNS " + r.status);
    return r.json();
  }

  async function latencyMs(url, timeoutMs) {
    const t0 = performance.now();
    const ctrl = new AbortController();
    const id = setTimeout(() => ctrl.abort(), timeoutMs || 8000);
    try {
      await fetch(url, { mode: "no-cors", cache: "no-store", signal: ctrl.signal });
      return Math.round(performance.now() - t0);
    } finally {
      clearTimeout(id);
    }
  }

  /** Probe host/IP from the user's browser (HTTP RTT, not ICMP). */
  async function clientReach(host, samples, timeoutMs) {
    const h = (host || "").trim().replace(/^https?:\/\//i, "").split("/")[0];
    if (!h) throw new Error("empty host");
    const isIp = /^(\d{1,3}\.){3}\d{1,3}$/.test(h) || h.includes(":");
    const urls = [];
    if (!isIp) {
      urls.push("https://" + h);
      urls.push("http://" + h);
    } else {
      urls.push("https://" + h);
      urls.push("http://" + h);
    }
    const n = Math.max(1, Math.min(samples || 3, 5));
    const times = [];
    let lastErr = null;
    for (let i = 0; i < n; i++) {
      let ok = false;
      for (const u of urls) {
        try {
          const ms = await latencyMs(u, timeoutMs || 10000);
          times.push(ms);
          ok = true;
          break;
        } catch (e) {
          lastErr = e;
        }
      }
      if (!ok) times.push(null);
    }
    const good = times.filter((x) => typeof x === "number");
    if (!good.length) throw lastErr || new Error("unreachable");
    const avg = Math.round(good.reduce((a, b) => a + b, 0) / good.length);
    const min = Math.min.apply(null, good);
    const max = Math.max.apply(null, good);
    return { host: h, samples: times, avg, min, max, ok: good.length, fail: n - good.length };
  }

  async function sha256Hex(text) {
    const data = new TextEncoder().encode(text);
    const hash = await crypto.subtle.digest("SHA-256", data);
    return Array.from(new Uint8Array(hash))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  }

  /* Minimal MD5 (browser) — for toolkit parity */
  function md5Hex(str) {
    function cmn(q, a, b, x, s, t) {
      a = (a + q + x + t) | 0;
      return (((a << s) | (a >>> (32 - s))) + b) | 0;
    }
    function ff(a, b, c, d, x, s, t) {
      return cmn((b & c) | (~b & d), a, b, x, s, t);
    }
    function gg(a, b, c, d, x, s, t) {
      return cmn((b & d) | (c & ~d), a, b, x, s, t);
    }
    function hh(a, b, c, d, x, s, t) {
      return cmn(b ^ c ^ d, a, b, x, s, t);
    }
    function ii(a, b, c, d, x, s, t) {
      return cmn(c ^ (b | ~d), a, b, x, s, t);
    }
    function md5blk(s) {
      const md5blks = [];
      for (let i = 0; i < 64; i += 4) {
        md5blks[i >> 2] =
          s.charCodeAt(i) +
          (s.charCodeAt(i + 1) << 8) +
          (s.charCodeAt(i + 2) << 16) +
          (s.charCodeAt(i + 3) << 24);
      }
      return md5blks;
    }
    function md51(s) {
      const n = s.length;
      const state = [1732584193, -271733879, -1732584194, 271733878];
      let i;
      for (i = 64; i <= n; i += 64) md5cycle(state, md5blk(s.substring(i - 64, i)));
      s = s.substring(i - 64);
      const tail = new Array(16).fill(0);
      for (i = 0; i < s.length; i++) tail[i >> 2] |= s.charCodeAt(i) << (i % 4 << 3);
      tail[i >> 2] |= 0x80 << (i % 4 << 3);
      if (i > 55) {
        md5cycle(state, tail);
        for (let j = 0; j < 16; j++) tail[j] = 0;
      }
      tail[14] = n * 8;
      md5cycle(state, tail);
      return state;
    }
    function md5cycle(x, k) {
      let [a, b, c, d] = x;
      a = ff(a, b, c, d, k[0], 7, -680876936);
      d = ff(d, a, b, c, k[1], 12, -389564586);
      c = ff(c, d, a, b, k[2], 17, 606105819);
      b = ff(b, c, d, a, k[3], 22, -1044525330);
      a = ff(a, b, c, d, k[4], 7, -176418897);
      d = ff(d, a, b, c, k[5], 12, 1200080426);
      c = ff(c, d, a, b, k[6], 17, -1473231341);
      b = ff(b, c, d, a, k[7], 22, -45705983);
      a = ff(a, b, c, d, k[8], 7, 1770035416);
      d = ff(d, a, b, c, k[9], 12, -1958414417);
      c = ff(c, d, a, b, k[10], 17, -42063);
      b = ff(b, c, d, a, k[11], 22, -1990404162);
      a = ff(a, b, c, d, k[12], 7, 1804603682);
      d = ff(d, a, b, c, k[13], 12, -40341101);
      c = ff(c, d, a, b, k[14], 17, -1502002290);
      b = ff(b, c, d, a, k[15], 22, 1236535329);
      a = gg(a, b, c, d, k[1], 5, -165796510);
      d = gg(d, a, b, c, k[6], 9, -1069501632);
      c = gg(c, d, a, b, k[11], 14, 643717713);
      b = gg(b, c, d, a, k[0], 20, -373897302);
      a = gg(a, b, c, d, k[5], 5, -701558691);
      d = gg(d, a, b, c, k[10], 9, 38016083);
      c = gg(c, d, a, b, k[15], 14, -660478335);
      b = gg(b, c, d, a, k[4], 20, -405537848);
      a = gg(a, b, c, d, k[9], 5, 568446438);
      d = gg(d, a, b, c, k[14], 9, -1019803690);
      c = gg(c, d, a, b, k[3], 14, -187363961);
      b = gg(b, c, d, a, k[8], 20, 1163531501);
      a = gg(a, b, c, d, k[13], 5, -1444681467);
      d = gg(d, a, b, c, k[2], 9, -51403784);
      c = gg(c, d, a, b, k[7], 14, 1735328473);
      b = gg(b, c, d, a, k[12], 20, -1926607734);
      a = hh(a, b, c, d, k[5], 4, -378558);
      d = hh(d, a, b, c, k[8], 11, -2022574463);
      c = hh(c, d, a, b, k[11], 16, 1839030562);
      b = hh(b, c, d, a, k[14], 23, -35309556);
      a = hh(a, b, c, d, k[1], 4, -1530992060);
      d = hh(d, a, b, c, k[4], 11, 1272893353);
      c = hh(c, d, a, b, k[7], 16, -155497632);
      b = hh(b, c, d, a, k[10], 23, -1094730640);
      a = hh(a, b, c, d, k[13], 4, 681279174);
      d = hh(d, a, b, c, k[0], 11, -358537222);
      c = hh(c, d, a, b, k[3], 16, -722521979);
      b = hh(b, c, d, a, k[6], 23, 76029189);
      a = hh(a, b, c, d, k[9], 4, -640364487);
      d = hh(d, a, b, c, k[12], 11, -421815835);
      c = hh(c, d, a, b, k[15], 16, 530742520);
      b = hh(b, c, d, a, k[2], 23, -995338651);
      a = ii(a, b, c, d, k[0], 6, -198630844);
      d = ii(d, a, b, c, k[7], 10, 1126891415);
      c = ii(c, d, a, b, k[14], 15, -1416354905);
      b = ii(b, c, d, a, k[5], 21, -57434055);
      a = ii(a, b, c, d, k[12], 6, 1700485571);
      d = ii(d, a, b, c, k[3], 10, -1894986606);
      c = ii(c, d, a, b, k[10], 15, -1051523);
      b = ii(b, c, d, a, k[1], 21, -2054922799);
      a = ii(a, b, c, d, k[8], 6, 1873313359);
      d = ii(d, a, b, c, k[15], 10, -30611744);
      c = ii(c, d, a, b, k[6], 15, -1560198380);
      b = ii(b, c, d, a, k[13], 21, 1309151649);
      a = ii(a, b, c, d, k[4], 6, -145523070);
      d = ii(d, a, b, c, k[11], 10, -1120210379);
      c = ii(c, d, a, b, k[2], 15, 718787259);
      b = ii(b, c, d, a, k[9], 21, -343485551);
      x[0] = (a + x[0]) | 0;
      x[1] = (b + x[1]) | 0;
      x[2] = (c + x[2]) | 0;
      x[3] = (d + x[3]) | 0;
    }
    function rhex(n) {
      let s = "";
      for (let j = 0; j < 4; j++) s += ("0" + ((n >> (j * 8)) & 255).toString(16)).slice(-2);
      return s;
    }
    // UTF-8
    const utf8 = unescape(encodeURIComponent(str));
    return md51(utf8).map(rhex).join("");
  }

  function parseSubnet(cidr) {
    const m = (cidr || "").trim().match(/^(\d{1,3}(?:\.\d{1,3}){3})\/(\d{1,2})$/);
    if (!m) return null;
    const parts = m[1].split(".").map(Number);
    if (parts.some((p) => p > 255)) return null;
    const prefix = parseInt(m[2], 10);
    if (prefix < 0 || prefix > 32) return null;
    const ip = ((parts[0] << 24) | (parts[1] << 16) | (parts[2] << 8) | parts[3]) >>> 0;
    const mask = prefix === 0 ? 0 : (0xffffffff << (32 - prefix)) >>> 0;
    const network = (ip & mask) >>> 0;
    const broadcast = (network | (~mask >>> 0)) >>> 0;
    const hosts = prefix >= 31 ? 0 : Math.max(0, broadcast - network - 1);
    const toIp = (n) =>
      [(n >>> 24) & 255, (n >>> 16) & 255, (n >>> 8) & 255, n & 255].join(".");
    return {
      network: toIp(network),
      broadcast: toIp(broadcast),
      mask: toIp(mask),
      firstHost: prefix >= 31 ? toIp(network) : toIp(network + 1),
      lastHost: prefix >= 31 ? toIp(broadcast) : toIp(broadcast - 1),
      hosts,
    };
  }

  function randomPassword(len, opts) {
    const lower = "abcdefghijkmnopqrstuvwxyz";
    const upper = "ABCDEFGHJKLMNPQRSTUVWXYZ";
    const digits = "23456789";
    const sym = "!@#$%&*+-=?";
    let pool = lower + digits;
    if (opts.upper) pool += upper;
    if (opts.symbols) pool += sym;
    const arr = new Uint32Array(len);
    crypto.getRandomValues(arr);
    let out = "";
    for (let i = 0; i < len; i++) out += pool[arr[i] % pool.length];
    return out;
  }

  function apiBase() {
    const p = location.pathname || "";
    const idx = p.indexOf("/miniapp/");
    if (idx >= 0) return p.slice(0, idx);
    return "";
  }

  async function miniappApi(action, params) {
    const p = Object.assign({}, params || {});
    if (tg && tg.initData) p.initData = tg.initData;
    const qs = new URLSearchParams(p).toString();
    const url = apiBase() + "/miniapp/api/" + action + (qs ? "?" + qs : "");
    const r = await fetch(url, { headers: { Accept: "application/json" } });
    let j;
    try {
      j = await r.json();
    } catch (e) {
      throw new Error(t("api_fail"));
    }
    if (!r.ok && j && j.error) throw new Error(j.error);
    return j;
  }

  function parseTimestampInput(raw) {
    const s = (raw || "").trim();
    if (!s) return null;
    if (/^\d{10,13}$/.test(s)) {
      let n = parseInt(s, 10);
      if (s.length <= 10) n *= 1000;
      return new Date(n);
    }
    const d = new Date(s.replace(" ", "T"));
    return isNaN(d.getTime()) ? null : d;
  }

  function bindTabs(tabsEl, panelSelector) {
    const tabs = Array.from(tabsEl.querySelectorAll(".tab"));
    const panels = Array.from(document.querySelectorAll(panelSelector || ".panel"));
    tabs.forEach((tab, i) => {
      tab.onclick = () => {
        tabs.forEach((x, j) => x.classList.toggle("active", j === i));
        panels.forEach((p, j) => p.classList.toggle("active", j === i));
      };
    });
  }

  global.T2R = {
    tg,
    t,
    lang,
    initApp,
    shell,
    header,
    badge,
    segmented,
    setResult,
    setResultHtml,
    copyText,
    addCopyButton,
    fetchJson,
    publicIp,
    ipDetails,
    dnsQuery,
    latencyMs,
    clientReach,
    sha256Hex,
    md5Hex,
    parseSubnet,
    randomPassword,
    parseTimestampInput,
    apiBase,
    miniappApi,
    bindTabs,
  };
})(window);
