// OPLoraST frontend: live trigger-word preview for "CR LoRA Stack Triggers JK".
// - On lora_name_i change -> fetch /oplorast/trigger_words -> render preview
// - On trigger_selector_i change -> JS parseSelector -> refresh "[selected]" line
// - force_fetch toggle on -> refetch all slots from civitai
import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

const NODE_NAME = "LoRA Stack Auto Triggers";
const ROUTE = "/lorastack/trigger_words";
const SLOTS = 4;

// JS port of oplorast_utils.parse_selector (kept in sync with the backend).
function parseSelector(selector, tags) {
    if (!tags || tags.length === 0) return "";
    selector = selector == null ? "" : String(selector);
    const output = new Map();
    for (let part of selector.split(",")) {
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

function setWidgetValue(node, name, value) {
    const w = node.widgets && node.widgets.find((x) => x.name === name);
    if (!w) return;
    w.value = value;
    if (w.inputEl) w.inputEl.value = value;
}

async function fetchTags(loraName, force) {
    try {
        const url = `${ROUTE}?lora_name=${encodeURIComponent(loraName)}&force=${force ? "true" : "false"}`;
        const r = await api.fetchApi(url);
        const data = await r.json();
        return {
            tags: data.tags || [],
            civitai_count: data.civitai_count || 0,
            meta_count: data.meta_count || 0,
            ok: !!data.ok,
        };
    } catch (e) {
        console.error("[OPLoraST] fetch error", e);
        return { tags: [], civitai_count: 0, meta_count: 0, ok: false };
    }
}

function renderPreview(node, i) {
    const cache = (node.opLoraTagsCache = node.opLoraTagsCache || {});
    const entry = cache[i] || { tags: [], civitai_count: 0, meta_count: 0, ok: true };
    const tags = entry.tags || [];
    const selWidget = node.widgets.find((w) => w.name === `trigger_selector_${i}`);
    const selector = selWidget ? selWidget.value : "";
    const selected = parseSelector(selector, tags);

    const lines = [];
    if (!entry.ok) {
        lines.push("[!] fetch failed (check network / enable force_fetch)");
    } else if (tags.length === 0) {
        lines.push("[no trigger words found]");
    } else {
        lines.push(`[trigger words] civitai:${entry.civitai_count} meta:${entry.meta_count}`);
        tags.forEach((t, idx) => {
            const src = idx < entry.civitai_count ? "civitai" : "meta";
            lines.push(`${idx}: ${t} (${src})`);
        });
    }
    if (selected) lines.push(`[selected] ${selected}`);
    setWidgetValue(node, `trigger_preview_${i}`, lines.join("\n"));
    if (node.setDirtyCanvas) node.setDirtyCanvas(true, true);
}

async function updateForSlot(node, i, force) {
    const nameWidget = node.widgets.find((w) => w.name === `lora_name_${i}`);
    const name = nameWidget ? nameWidget.value : "None";
    const cache = (node.opLoraTagsCache = node.opLoraTagsCache || {});
    if (!name || name === "None") {
        cache[i] = { tags: [], civitai_count: 0, meta_count: 0, ok: true };
        renderPreview(node, i);
        return;
    }
    renderPreview(node, i); // show current while fetching
    const data = await fetchTags(name, force);
    cache[i] = data;
    renderPreview(node, i);
}

function bindSlot(node, i) {
    const nameWidget = node.widgets.find((w) => w.name === `lora_name_${i}`);
    const selWidget = node.widgets.find((w) => w.name === `trigger_selector_${i}`);

    if (nameWidget && !nameWidget._opBound) {
        const orig = nameWidget.callback;
        nameWidget.callback = function () {
            const r = orig ? orig.apply(this, arguments) : undefined;
            updateForSlot(node, i, false);
            return r;
        };
        nameWidget._opBound = true;
    }
    if (selWidget && !selWidget._opBound) {
        const orig = selWidget.callback;
        selWidget.callback = function () {
            const r = orig ? orig.apply(this, arguments) : undefined;
            renderPreview(node, i);
            return r;
        };
        selWidget._opBound = true;
    }
}

function bindForceFetch(node) {
    const ff = node.widgets.find((w) => w.name === "force_fetch");
    if (!ff || ff._opBound) return;
    const orig = ff.callback;
    ff.callback = function () {
        const r = orig ? orig.apply(this, arguments) : undefined;
        if (ff.value === true) {
            // refetch every slot that has a real lora selected
            for (let i = 1; i <= SLOTS; i++) {
                const nm = node.widgets.find((w) => w.name === `lora_name_${i}`);
                if (nm && nm.value && nm.value !== "None") {
                    updateForSlot(node, i, true);
                }
            }
        }
        return r;
    };
    ff._opBound = true;
}

app.registerExtension({
    name: "oplorast.lora_triggers",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_NAME) return;
        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
            const node = this;
            // widgets exist at this point; small timeout for safety
            setTimeout(() => {
                for (let i = 1; i <= SLOTS; i++) {
                    bindSlot(node, i);
                    updateForSlot(node, i, false);
                }
                bindForceFetch(node);
            }, 60);
            return r;
        };
    },
});