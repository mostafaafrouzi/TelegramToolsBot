/* Tele2Rub Mini App — shared Telegram WebApp helpers */
(function (global) {
  const tg = global.Telegram && global.Telegram.WebApp;

  const STR = {
    fa: {
      loading: "در حال بارگذاری…",
      error: "خطا",
      copy: "کپی",
      copied: "کپی شد",
      back: "← خانه",
      home_title: "ابزارهای مرورگر",
      home_sub: "همه‌چیز از شبکه و دستگاه شما اجرا می‌شود (نه IP سرور ربات).",
    },
    en: {
      loading: "Loading…",
      error: "Error",
      copy: "Copy",
      copied: "Copied",
      back: "← Home",
      home_title: "Browser tools",
      home_sub: "Runs on your network (not the bot server IP).",
    },
  };

  function lang() {
    const code = (tg && tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.language_code) || "fa";
    return code.startsWith("en") ? "en" : "fa";
  }

  function t(key) {
    const L = STR[lang()] || STR.fa;
    return L[key] || STR.en[key] || key;
  }

  function initApp() {
    if (tg) {
      tg.ready();
      tg.expand();
      if (tg.enableClosingConfirmation) tg.enableClosingConfirmation();
    }
    const rtl = lang() === "fa";
    document.body.classList.add(rtl ? "rtl" : "ltr");
    document.documentElement.lang = lang();
    document.documentElement.dir = rtl ? "rtl" : "ltr";
  }

  function header(title, backHref) {
    const wrap = document.createElement("header");
    wrap.className = "app-header";
    if (backHref) {
      const a = document.createElement("a");
      a.className = "back-link";
      a.href = backHref;
      a.textContent = t("back");
      wrap.appendChild(a);
    }
    const h1 = document.createElement("h1");
    h1.textContent = title;
    wrap.appendChild(h1);
    return wrap;
  }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      if (tg && tg.showPopup) {
        tg.showPopup({ message: t("copied") });
      } else if (tg && tg.showAlert) {
        tg.showAlert(t("copied"));
      }
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

  async function sha256Hex(text) {
    const data = new TextEncoder().encode(text);
    const hash = await crypto.subtle.digest("SHA-256", data);
    return Array.from(new Uint8Array(hash))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  }

  function parseSubnet(cidr) {
    const m = (cidr || "").trim().match(/^(\d{1,3}(?:\.\d{1,3}){3})\/(\d{1,2})$/);
    if (!m) return null;
    const parts = m[1].split(".").map(Number);
    if (parts.some((p) => p > 255)) return null;
    const prefix = parseInt(m[2], 10);
    if (prefix < 0 || prefix > 32) return null;
    const ip =
      ((parts[0] << 24) | (parts[1] << 16) | (parts[2] << 8) | parts[3]) >>> 0;
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
    const qs = new URLSearchParams(params || {}).toString();
    const url = apiBase() + "/miniapp/api/" + action + (qs ? "?" + qs : "");
    const r = await fetch(url, { headers: { Accept: "application/json" } });
    const j = await r.json();
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

  global.T2R = {
    tg,
    t,
    lang,
    initApp,
    header,
    copyText,
    addCopyButton,
    fetchJson,
    publicIp,
    ipDetails,
    dnsQuery,
    latencyMs,
    sha256Hex,
    parseSubnet,
    randomPassword,
    parseTimestampInput,
    apiBase,
    miniappApi,
  };
})(window);
