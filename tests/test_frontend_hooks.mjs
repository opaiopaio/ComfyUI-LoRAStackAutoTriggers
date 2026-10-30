// Headless test of the picker extension's binding logic.
//
// Loads web/js/oplorast_lora_triggers.js with stubbed ComfyUI modules, then
// drives the extension hooks with a fake node and asserts that:
//   - trigger_selector_i gets hidden,
//   - a "⚙ ..." picker button is added per slot,
//   - the summary widget gets filled,
//   - running the hook twice does not duplicate buttons (idempotent).
//
// Run: node tests/test_frontend_hooks.mjs
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const jsPath = path.join(here, "..", "web", "js", "oplorast_lora_triggers.js");

const src = fs
    .readFileSync(jsPath, "utf8")
    .split("\n")
    .filter((line) => !/^import .*scripts\/(app|api)\.js/.test(line))
    .join("\n");

const captured = { ext: null };
const app = {
    registerExtension(ext) {
        captured.ext = ext;
    },
    graph: { setDirtyCanvas() {} },
};
const api = {
    async fetchApi() {
        return {
            json: async () => ({
                variants: ["zzz_x, pink hair, black dress, see-through mouth mask"],
                meta: ["pink hair", "mask"],
                blocks: 28,
                ok: true,
            }),
        };
    },
};
const nav = { language: "zh-CN" };

new Function("app", "api", "navigator", "console", src)(app, api, nav, console);

let ok = true;
const check = (label, cond, extra = "") => {
    if (!cond) ok = false;
    console.log(`[${cond ? "OK " : "FAIL"}] ${label}${cond || !extra ? "" : `  ${extra}`}`);
};

check("extension registered", !!captured.ext);
check("has nodeCreated hook", !!(captured.ext && captured.ext.nodeCreated));

function makeNode() {
    const widgets = [];
    for (let i = 1; i <= 4; i++) {
        for (const [name, value] of [
            [`lora_${i}`, false],
            [`lora_name_${i}`, "None"],
            [`model_weight_${i}`, 1.0],
            [`clip_weight_${i}`, 1.0],
            [`trigger_selector_${i}`, ""],
            [`trigger_weight_${i}`, 1.0],
            [`trigger_preview_${i}`, ""],
        ]) {
            widgets.push({ name, value, callback: null });
        }
    }
    widgets.push({ name: "save_hash", value: false });
    widgets.push({ name: "force_fetch", value: false });
    widgets.push({ name: "fallback_to_filename", value: true });

    return {
        widgets,
        size: [320, 900],
        addWidget(type, name, value, callback) {
            const w = { type, name, value, callback };
            this.widgets.push(w);
            return w;
        },
        computeSize() {
            return [320, 900];
        },
        setSize() {},
        setDirtyCanvas() {},
    };
}

const node = makeNode();
// pretend the user picked a LoRA in slot 1 so the summary has something to say
node.widgets.find((w) => w.name === "lora_1").value = true;
node.widgets.find((w) => w.name === "lora_name_1").value = "mylora.safetensors";

await captured.ext.nodeCreated(node);
await new Promise((r) => setTimeout(r, 120));

const byName = (n) => node.widgets.find((w) => w.name === n);

check("selector 1 已隐藏", byName("trigger_selector_1").type === "hidden");
check("selector 4 已隐藏", byName("trigger_selector_4").type === "hidden");

const buttons = node.widgets.filter((w) => w.type === "button");
check("4 个选词按钮", buttons.length === 4, `实际 ${buttons.length}：${buttons.map((b) => b.name).join(" | ")}`);
check("按钮标签是中文", buttons.length > 0 && buttons[0].name.includes("触发词"), buttons[0] && buttons[0].name);

const preview = byName("trigger_preview_1").value;
check("摘要已填充", typeof preview === "string" && preview.length > 0, JSON.stringify(preview));
check("摘要含层数", preview.includes("28"), preview);

// 幂等：再跑一次不应重复加按钮
await captured.ext.nodeCreated(node);
await new Promise((r) => setTimeout(r, 120));
const buttons2 = node.widgets.filter((w) => w.type === "button");
check("重复调用不重复加按钮", buttons2.length === 4, `实际 ${buttons2.length}`);

// 空节点（不是我们的）不应被动
const other = { widgets: [{ name: "seed", value: 0 }], size: [200, 100], addWidget() {}, computeSize: () => [200, 100], setSize() {}, setDirtyCanvas() {} };
await captured.ext.nodeCreated(other);
check("非本节点不处理", other.widgets.length === 1);

console.log("\nRESULT:", ok ? "ALL PASS" : "SOME FAILED");
process.exit(ok ? 0 : 1);
