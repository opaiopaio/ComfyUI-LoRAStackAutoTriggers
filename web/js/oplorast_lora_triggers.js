// ComfyUI-LoRAStackAutoTriggers — trigger-word picker UI (v1.1.0)
//
// Why this exists: a civitai `trainedWords` entry is normally a WHOLE trigger
// sentence per costume/variant (e.g. "... , black dress, see-through mouth
// mask"), so index-based selection can only take or drop an entire variant.
// This dialog lets you:
//   - pick a variant as a preset,
//   - toggle individual comma-separated segments (drop "see-through mouth
//     mask" etc.),
//   - select text with the mouse and inject only that selection,
//   - search the training-tag dump and append single tags.
//
// The result is written into `trigger_selector_i` as free text; the backend
// injects free text verbatim (legacy slice syntax still supported).
import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

const NODE_NAME = "LoRA Stack Auto Triggers";
const ROUTE = "/lorastack/trigger_words";
const SLOTS = 4;
const META_RENDER_LIMIT = 400;
const LOG = "[LoRAStackAutoTriggers]";

// --------------------------------------------------------------------------- //
// small helpers
// --------------------------------------------------------------------------- //
function getWidget(node, name) {
    return node.widgets ? node.widgets.find((w) => w.name === name) : undefined;
}

function setWidgetValue(node, name, value) {
    const w = getWidget(node, name);
    if (!w) return;
    w.value = value;
    if (w.inputEl && w.inputEl.value !== value) w.inputEl.value = value;
}

function looksLikeSlice(value) {
    const s = (value == null ? "" : String(value)).trim();
    if (!s) return false;
    if (!/^[0-9\s,:.\-]+$/.test(s)) return false;
    return /[0-9:]/.test(s);
}

// JS port of oplorast_utils.parse_selector (kept in sync with the backend).
function parseSelector(selector, tags) {
    if (!tags || tags.length === 0) return "";
    selector = selector == null ? "" : String(selector);
    const output = new Map();
    for (const part of selector.split(",")) {
        const colons = (part.match(/:/g) || []).length;
        if (colons === 0) {
            if (part.trim() === "") continue;
            const idx = parseInt(part, 10);
            if (isNaN(idx)) continue;
            if (Math.abs(idx) > tags.length - 1) continue;
            const real = idx < 0 ? tags.length + idx : idx;
            output.set(real, tags[real]);
        } else if (colons === 1) {
            const [a, b] = part.split(":");
            let start = a === "" ? 0 : parseInt(a, 10);
            let end = b === "" ? tags.length : parseInt(b, 10);
            if (isNaN(start)) start = 0;
            if (isNaN(end)) end = tags.length;
            if (start < 0) start = tags.length + start;
            if (end < 0) end = tags.length + end;
            start = Math.min(Math.max(start, 0), tags.length);
            end = Math.min(Math.max(end, 0), tags.length);
            for (let i = start; i < end; i++) output.set(i, tags[i]);
        }
    }
    return [...output.values()].join(", ");
}

// Mirror of oplorast_utils.resolve_selection (preview only).
function resolveText(value, variants, meta) {
    const v = value == null ? "" : String(value);
    const s = v.trim();
    if (s === "") return variants && variants.length ? variants[0] : "";
    if (s.startsWith("[")) {
        try {
            const arr = JSON.parse(s);
            if (Array.isArray(arr)) {
                return arr.map((x) => String(x).trim()).filter(Boolean).join(", ");
            }
        } catch (e) { /* fall through */ }
    }
    if (looksLikeSlice(s)) {
        return parseSelector(s, [...(variants || []), ...(meta || [])]);
    }
    return s;
}

function splitSegments(text) {
    if (!text) return [];
    return String(text).split(",").map((s) => s.trim()).filter(Boolean);
}

function truncate(s, n) {
    if (!s) return "";
    return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

function el(tag, props, children) {
    const e = document.createElement(tag);
    if (props) {
        for (const [k, v] of Object.entries(props)) {
            if (k === "style" && v && typeof v === "object") Object.assign(e.style, v);
            else if (k === "class") e.className = v;
            else if (k === "text") e.textContent = v;
            else if (k.startsWith("on") && typeof v === "function") e.addEventListener(k.slice(2), v);
            else if (v !== undefined && v !== null) e.setAttribute(k, v);
        }
    }
    (children || []).forEach((c) => c && e.appendChild(c));
    return e;
}

const CSS = `
.opls-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.55);
  z-index: 10000; display: flex; align-items: center; justify-content: center; }
.opls-panel { width: min(880px, 94vw); max-height: 88vh; display: flex;
  flex-direction: column; background: #1e1e1e; color: #d7d7d7;
  border: 1px solid #3c3c3c; border-radius: 8px; overflow: hidden;
  box-shadow: 0 16px 48px rgba(0,0,0,.65); font: 12px/1.5 system-ui, sans-serif; }
.opls-head { display: flex; align-items: center; gap: 8px; padding: 8px 12px;
  background: #262626; border-bottom: 1px solid #3c3c3c; }
.opls-title { flex: 1; font-weight: 600; font-size: 13px; color: #eee;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.opls-x { cursor: pointer; color: #999; font-size: 16px; line-height: 1;
  padding: 2px 6px; border-radius: 4px; }
.opls-x:hover { background: #3a3a3a; color: #fff; }
.opls-tabs { display: flex; gap: 4px; padding: 8px 12px 0; }
.opls-tab { cursor: pointer; padding: 5px 11px; border-radius: 6px 6px 0 0;
  background: #262626; color: #9a9a9a; border: 1px solid transparent;
  border-bottom: none; user-select: none; }
.opls-tab.on { background: #333; color: #fff; border-color: #3c3c3c; }
.opls-helper { padding: 10px 12px; overflow: auto; min-height: 90px;
  max-height: 34vh; background: #202020; border: 1px solid #3c3c3c;
  border-radius: 0 6px 6px 6px; margin: 0 12px; }
.opls-hint { color: #8a8a8a; }
.opls-var { display: flex; gap: 8px; padding: 6px 8px; border-radius: 6px;
  cursor: pointer; align-items: baseline; }
.opls-var:hover { background: #2c2c2c; }
.opls-var.on { background: #2f3b4d; outline: 1px solid #4b6c9b; }
.opls-var-name { color: #cfd8e3; font-weight: 600; }
.opls-var-count { color: #7f8c9b; }
.opls-var-prev { color: #8f8f8f; flex: 1; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap; }
.opls-chips { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 10px; }
.opls-chip { cursor: pointer; padding: 3px 8px; border-radius: 999px;
  background: #2f4a33; color: #cfe9d3; border: 1px solid #3f6b47;
  user-select: none; }
.opls-chip.off { background: #3a2b2b; color: #d7b3b3;
  border-color: #6b4141; text-decoration: line-through; }
.opls-ta { box-sizing: border-box; width: calc(100% - 24px); margin: 10px 12px 0;
  height: 108px; resize: vertical; background: #151515; color: #e8e8e8;
  border: 1px solid #3c3c3c; border-radius: 6px; padding: 8px;
  font: 12px/1.55 ui-monospace, Consolas, monospace; outline: none; }
.opls-ta:focus { border-color: #4b6c9b; }
.opls-foot { display: flex; align-items: center; gap: 8px; padding: 10px 12px;
  border-top: 1px solid #3c3c3c; background: #262626; }
.opls-count { color: #8a8a8a; }
.opls-spacer { flex: 1; }
.opls-btn { cursor: pointer; padding: 5px 12px; border-radius: 6px;
  background: #333; color: #ddd; border: 1px solid #4a4a4a; user-select: none; }
.opls-btn:hover { background: #3d3d3d; color: #fff; }
.opls-btn.primary { background: #35507a; border-color: #4b6c9b; color: #fff; }
.opls-btn.primary:hover { background: #3f5f90; }
.opls-btn[disabled] { opacity: .45; cursor: not-allowed; }
.opls-search { width: 100%; box-sizing: border-box; margin-bottom: 8px;
  background: #151515; color: #e8e8e8; border: 1px solid #3c3c3c;
  border-radius: 6px; padding: 6px 8px; outline: none; }
.opls-taglist { max-height: 26vh; overflow: auto; }
.opls-tag { cursor: pointer; padding: 3px 8px; border-radius: 4px; color: #c8c8c8; }
.opls-tag:hover { background: #2f3b4d; color: #fff; }
`;

function ensureCss() {
    if (document.getElementById("opls-style")) return;
    const s = document.createElement("style");
    s.id = "opls-style";
    s.textContent = CSS;
    document.head.appendChild(s);
}

// --------------------------------------------------------------------------- //
// backend fetch
// --------------------------------------------------------------------------- //
async function fetchTags(loraName, force) {
    try {
        const url = `${ROUTE}?lora_name=${encodeURIComponent(loraName)}&force=${force ? "true" : "false"}`;
        const r = await api.fetchApi(url);
        const data = await r.json();
        return {
            variants: data.variants || [],
            meta: data.meta || [],
            ok: !!data.ok,
        };
    } catch (e) {
        console.error(LOG, "fetch error", e);
        return { variants: [], meta: [], ok: false };
    }
}

// --------------------------------------------------------------------------- //
// node summary line
// --------------------------------------------------------------------------- //
function renderSummary(node, i) {
    const cache = (node.opLoraTagsCache = node.opLoraTagsCache || {});
    const entry = cache[i] || { variants: [], meta: [], ok: true };
    const selW = getWidget(node, `trigger_selector_${i}`);
    const raw = selW ? selW.value : "";
    const resolved = resolveText(raw, entry.variants, entry.meta);

    let text;
    if (!entry.ok) {
        text = "⚠ 拉取失败（可开 force_fetch 重试）";
    } else if (!resolved) {
        const vc = (entry.variants || []).length;
        const mc = (entry.meta || []).length;
        text = `未选择 · 变体 ${vc} / 训练标签 ${mc} — 点 ⚙ 打开选择器`;
    } else {
        const segs = splitSegments(resolved);
        text = `已选 ${segs.length} 段 / ${resolved.length} 字：${truncate(resolved, 70)}`;
    }
    setWidgetValue(node, `trigger_preview_${i}`, text);
    if (node.setDirtyCanvas) node.setDirtyCanvas(true, true);
}

async function updateForSlot(node, i, force) {
    const nameW = getWidget(node, `lora_name_${i}`);
    const name = nameW ? nameW.value : "None";
    const cache = (node.opLoraTagsCache = node.opLoraTagsCache || {});
    if (!name || name === "None") {
        cache[i] = { variants: [], meta: [], ok: true };
        renderSummary(node, i);
        return;
    }
    renderSummary(node, i); // keep current while fetching
    cache[i] = await fetchTags(name, force);
    renderSummary(node, i);
}

// --------------------------------------------------------------------------- //
// picker dialog
// --------------------------------------------------------------------------- //
function openPicker(node, i) {
    ensureCss();

    const cache = (node.opLoraTagsCache = node.opLoraTagsCache || {});
    const entry = cache[i] || { variants: [], meta: [], ok: false };
    const variants = entry.variants || [];
    const meta = entry.meta || [];
    const selW = getWidget(node, `trigger_selector_${i}`);
    const nameW = getWidget(node, `lora_name_${i}`);
    const loraName = nameW ? nameW.value : "None";
    const currentRaw = selW ? selW.value : "";

    // ---- state
    let chipState = null;   // [{text,on}] or null when manually edited
    let baseVariant = -1;

    // ---- layout
    const ta = el("textarea", { class: "opls-ta", spellcheck: "false" });
    ta.value = resolveText(currentRaw, variants, meta);

    const helper = el("div", { class: "opls-helper" });
    const countEl = el("span", { class: "opls-count" });
    const selInfoEl = el("span", { class: "opls-count" });
    const overlay = el("div", { class: "opls-overlay" });
    const panel = el("div", { class: "opls-panel" });

    const close = () => {
        overlay.remove();
        document.removeEventListener("keydown", onKey, true);
    };
    const onKey = (ev) => {
        if (ev.key === "Escape") {
            ev.stopPropagation();
            close();
        }
    };

    const apply = (text) => {
        if (selW) selW.value = text;
        renderSummary(node, i);
        if (app.graph && app.graph.setDirtyCanvas) app.graph.setDirtyCanvas(true, true);
        close();
    };

    // ---- counters
    const refreshCount = () => {
        const segs = splitSegments(ta.value);
        countEl.textContent = `已选 ${segs.length} 段 · ${ta.value.length} 字`;
        const a = ta.selectionStart, b = ta.selectionEnd;
        selInfoEl.textContent = b > a ? `选区 ${b - a} 字` : "未划选";
        if (b > a) applySelBtn.removeAttribute("disabled");
        else applySelBtn.setAttribute("disabled", "");
    };

    // ---- chips
    const chipsWrap = el("div", { class: "opls-chips" });
    const syncFromChips = () => {
        if (!chipState) return;
        ta.value = chipState.filter((c) => c.on).map((c) => c.text).join(", ");
        drawChips();
        refreshCount();
    };
    const drawChips = () => {
        chipsWrap.textContent = "";
        if (!chipState) {
            chipsWrap.appendChild(
                el("span", {
                    class: "opls-hint",
                    text: "（已手动编辑）点右侧按钮可按当前文本重建片段开关",
                })
            );
            const rebuild = el("span", {
                class: "opls-chip",
                text: "↻ 重建片段",
                onclick: () => {
                    chipState = splitSegments(ta.value).map((t) => ({ text: t, on: true }));
                    baseVariant = -1;
                    drawChips();
                },
            });
            chipsWrap.appendChild(rebuild);
            return;
        }
        chipState.forEach((c, idx) => {
            chipsWrap.appendChild(
                el("span", {
                    class: "opls-chip" + (c.on ? "" : " off"),
                    text: c.text,
                    title: c.on ? "点击剔除该片段" : "点击恢复该片段",
                    onclick: () => {
                        chipState[idx].on = !chipState[idx].on;
                        syncFromChips();
                    },
                })
            );
        });
    };

    const loadVariant = (idx) => {
        baseVariant = idx;
        chipState = splitSegments(variants[idx]).map((t) => ({ text: t, on: true }));
        syncFromChips();
        drawVariantList();
    };

    // ---- tab: variants
    const variantList = el("div");
    const drawVariantList = () => {
        variantList.textContent = "";
        if (variants.length === 0) {
            variantList.appendChild(
                el("div", {
                    class: "opls-hint",
                    text: "该 LoRA 没有从 civitai 拉到变体。可在节点上勾选 force_fetch 后重新打开本窗口。",
                })
            );
            return;
        }
        variants.forEach((v, idx) => {
            const segs = splitSegments(v);
            const head = segs.length ? segs[0] : v;
            const rest = segs.slice(1).join(", ");
            const row = el(
                "div",
                {
                    class: "opls-var" + (idx === baseVariant ? " on" : ""),
                    onclick: () => loadVariant(idx),
                    title: v,
                },
                [
                    el("span", { text: idx === baseVariant ? "●" : "○" }),
                    el("span", { class: "opls-var-name", text: head }),
                    el("span", { class: "opls-var-count", text: `${segs.length} 词` }),
                    el("span", { class: "opls-var-prev", text: rest }),
                ]
            );
            variantList.appendChild(row);
        });
        variantList.appendChild(
            el("div", {
                class: "opls-hint",
                style: { marginTop: "8px" },
                text: "点变体 = 载入；下方片段点一下即剔除（如 see-through mouth mask），再点恢复。",
            })
        );
        variantList.appendChild(chipsWrap);
    };

    // ---- tab: meta tags
    const metaBox = el("div");
    // rows live in their own container so the search input never loses focus
    const metaList = el("div");
    const drawMeta = (filter) => {
        metaList.textContent = "";
        const f = (filter || "").toLowerCase().trim();
        const hits = f ? meta.filter((t) => t.toLowerCase().includes(f)) : meta;
        metaList.appendChild(
            el("div", {
                class: "opls-hint",
                style: { marginBottom: "6px" },
                text: "训练集标签统计（多数与角色无关，仅作补充）。点击追加到结果。",
            })
        );
        if (meta.length === 0) {
            metaList.appendChild(el("div", { class: "opls-hint", text: "无训练标签。" }));
            return;
        }
        const list = el("div", { class: "opls-taglist" });
        hits.slice(0, META_RENDER_LIMIT).forEach((t) => {
            list.appendChild(
                el("div", {
                    class: "opls-tag",
                    text: t,
                    onclick: () => {
                        const cur = ta.value.trim();
                        ta.value = cur ? `${cur}, ${t}` : t;
                        chipState = null;
                        drawChips();
                        refreshCount();
                    },
                })
            );
        });
        metaList.appendChild(list);
        if (hits.length > META_RENDER_LIMIT) {
            metaList.appendChild(
                el("div", {
                    class: "opls-hint",
                    text: `还有 ${hits.length - META_RENDER_LIMIT} 条，请用搜索缩小范围。`,
                })
            );
        }
        if (f && hits.length === 0) {
            metaList.appendChild(el("div", { class: "opls-hint", text: "没有匹配的标签。" }));
        }
    };

    // ---- tab: free edit
    const freeBox = el("div", {
        class: "opls-hint",
        text:
            "这是最终要注入的文本，可直接编辑。想只取其中一段：用鼠标划选后点「应用选区」。",
    });

    // ---- tabs
    const tabsBar = el("div", { class: "opls-tabs" });
    const views = [
        { key: "var", label: `变体 ${variants.length}`, node: variantList },
        { key: "meta", label: `训练标签 ${meta.length}`, node: metaBox },
        { key: "free", label: "自由编辑", node: freeBox },
    ];
    let activeKey = variants.length ? "var" : "free";

    const showTab = (key) => {
        activeKey = key;
        helper.textContent = "";
        views.forEach((v) => {
            v.btn.classList.toggle("on", v.key === key);
        });
        const view = views.find((v) => v.key === key);
        if (view) helper.appendChild(view.node);
        if (key === "var") drawVariantList();
        if (key === "meta") drawMeta(search.value || "");
    };

    views.forEach((v) => {
        v.btn = el("div", {
            class: "opls-tab",
            text: v.label,
            onclick: () => showTab(v.key),
        });
        tabsBar.appendChild(v.btn);
    });

    // meta search box + list container (list is redrawn in place so the
    // input keeps focus while typing)
    const search = el("input", {
        class: "opls-search",
        placeholder: "搜索标签…（例：mask / hair / dress）",
    });
    search.addEventListener("input", () => drawMeta(search.value));
    metaBox.appendChild(search);
    metaBox.appendChild(metaList);

    // ---- textarea events
    ta.addEventListener("input", () => {
        chipState = null;
        if (activeKey === "var") drawChips();
        refreshCount();
    });
    ["keyup", "mouseup", "select", "click"].forEach((ev) =>
        ta.addEventListener(ev, refreshCount)
    );

    // ---- footer buttons
    const applySelBtn = el("div", {
        class: "opls-btn",
        text: "应用选区",
        onclick: () => {
            const a = ta.selectionStart, b = ta.selectionEnd;
            if (b > a) apply(ta.value.slice(a, b).trim());
        },
    });
    const applyAllBtn = el("div", {
        class: "opls-btn primary",
        text: "应用全部",
        onclick: () => apply(ta.value.trim()),
    });
    const cancelBtn = el("div", {
        class: "opls-btn",
        text: "取消",
        onclick: close,
    });

    const foot = el("div", { class: "opls-foot" }, [
        countEl,
        el("span", { class: "opls-spacer" }),
        selInfoEl,
        applySelBtn,
        applyAllBtn,
        cancelBtn,
    ]);

    // ---- header
    const head = el("div", { class: "opls-head" }, [
        el("div", {
            class: "opls-title",
            text: `触发词 · LoRA ${i} — ${truncate(String(loraName), 60)}`,
        }),
        el("div", { class: "opls-x", text: "✕", onclick: close }),
    ]);

    panel.appendChild(head);
    panel.appendChild(tabsBar);
    panel.appendChild(helper);
    panel.appendChild(ta);
    panel.appendChild(foot);
    overlay.appendChild(panel);

    // block canvas interactions underneath
    ["mousedown", "mouseup", "wheel", "pointerdown", "pointerup", "contextmenu"].forEach(
        (ev) => overlay.addEventListener(ev, (e) => e.stopPropagation())
    );
    overlay.addEventListener("mousedown", (e) => {
        if (e.target === overlay) close();
    });
    document.addEventListener("keydown", onKey, true);

    document.body.appendChild(overlay);

    showTab(activeKey);
    if (activeKey === "var" && variants.length) {
        chipState = splitSegments(ta.value).map((t) => ({ text: t, on: true }));
        drawChips();
    }
    refreshCount();
    ta.focus();
}

// --------------------------------------------------------------------------- //
// wiring
// --------------------------------------------------------------------------- //
function hideWidget(w) {
    if (!w) return;
    w.type = "hidden";
    w.computeSize = () => [0, -4];
}

function addSlotButton(node, i) {
    const clipW = getWidget(node, `clip_weight_${i}`);
    const btn = node.addWidget("button", `⚙ 触发词 ${i}`, null, () => openPicker(node, i));
    // move the button right below the CLIP weight of this slot
    const from = node.widgets.indexOf(btn);
    if (from >= 0) node.widgets.splice(from, 1);
    const at = clipW ? node.widgets.indexOf(clipW) + 1 : node.widgets.length;
    node.widgets.splice(at, 0, btn);
    btn._opButton = true;
}

function bindSlot(node, i) {
    const nameW = getWidget(node, `lora_name_${i}`);
    hideWidget(getWidget(node, `trigger_selector_${i}`));

    if (nameW && !nameW._opBound) {
        const orig = nameW.callback;
        nameW.callback = function () {
            const r = orig ? orig.apply(this, arguments) : undefined;
            updateForSlot(node, i, false);
            return r;
        };
        nameW._opBound = true;
    }
    if (!node[`_opBtn${i}`]) {
        addSlotButton(node, i);
        node[`_opBtn${i}`] = true;
    }
}

function bindForceFetch(node) {
    const ff = getWidget(node, "force_fetch");
    if (!ff || ff._opBound) return;
    const orig = ff.callback;
    ff.callback = function () {
        const r = orig ? orig.apply(this, arguments) : undefined;
        if (ff.value === true) {
            for (let k = 1; k <= SLOTS; k++) {
                const nm = getWidget(node, `lora_name_${k}`);
                if (nm && nm.value && nm.value !== "None") updateForSlot(node, k, true);
            }
        }
        return r;
    };
    ff._opBound = true;
}

app.registerExtension({
    name: "lorastackautotriggers.picker",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_NAME) return;
        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
            const node = this;
            setTimeout(() => {
                for (let i = 1; i <= SLOTS; i++) {
                    bindSlot(node, i);
                    updateForSlot(node, i, false);
                }
                bindForceFetch(node);
                const size = node.computeSize();
                node.setSize([Math.max(node.size[0], size[0]), size[1]]);
                if (node.setDirtyCanvas) node.setDirtyCanvas(true, true);
            }, 60);
            return r;
        };
    },
});
