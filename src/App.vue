<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import JSZip from "jszip";
import {
  Circle,
  Download,
  ExternalLink,
  Globe2,
  LoaderCircle,
  Moon,
  Send,
  Square,
  Upload,
} from "lucide-vue-next";

const densities = [
  { name: "mdpi", size: 48, foreground: 108 },
  { name: "hdpi", size: 72, foreground: 162 },
  { name: "xhdpi", size: 96, foreground: 216 },
  { name: "xxhdpi", size: 144, foreground: 324 },
  { name: "xxxhdpi", size: 192, foreground: 432 },
];
type Shape = "square" | "rounded" | "circle";

const sourceUrl = ref<string>();
const sourceImage = ref<HTMLImageElement>();
const color = ref("#ffffff");
const shape = ref<Shape>("rounded");
const zoom = ref(1);
const padding = ref(0);
const crop = ref(false);
const x = ref(0);
const y = ref(0);
const dragging = ref(false);
const submitting = ref(false);
const actionsUrl = ref<string>();
const jobStatus = ref<"queued" | "running" | "succeeded" | "failed">();
const error = ref<string>();
const previewRef = ref<HTMLCanvasElement>();
let dragStart: { x: number; y: number; offsetX: number; offsetY: number } | undefined;
let statusPoll: number | undefined;
const canvasStyle = computed(() => ({ background: color.value }));
const shapeName = computed(() =>
  shape.value === "circle" ? "圆形" : shape.value === "rounded" ? "圆角" : "方形",
);

function clipShape(context: CanvasRenderingContext2D, size: number, iconShape: Shape) {
  context.beginPath();
  if (iconShape === "circle") context.arc(size / 2, size / 2, size / 2, 0, Math.PI * 2);
  else if (iconShape === "rounded") context.roundRect(0, 0, size, size, size * 0.22);
  else context.rect(0, 0, size, size);
  context.clip();
}
function fillBackground(context: CanvasRenderingContext2D, size: number) {
  context.fillStyle = color.value;
  context.fillRect(0, 0, size, size);
}
function drawIcon(
  source: HTMLImageElement,
  size: number,
  includeBackground = true,
  extraPadding = 0,
) {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d")!;
  context.save();
  clipShape(context, size, shape.value);
  if (includeBackground) fillBackground(context, size);
  const available = size * (1 - (padding.value + extraPadding) * 2);
  const baseScale = crop.value
    ? Math.max(available / source.naturalWidth, available / source.naturalHeight)
    : Math.min(available / source.naturalWidth, available / source.naturalHeight);
  const scale = baseScale * zoom.value;
  const width = source.naturalWidth * scale;
  const height = source.naturalHeight * scale;
  context.drawImage(
    source,
    (size - width) / 2 + x.value * size,
    (size - height) / 2 + y.value * size,
    width,
    height,
  );
  context.restore();
  return canvas;
}
function drawBackground(size: number) {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  fillBackground(canvas.getContext("2d")!, size);
  return canvas;
}
function canvasBlob(canvas: HTMLCanvasElement) {
  return new Promise<Blob>((resolve, reject) =>
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("无法生成 PNG"))),
      "image/png",
    ),
  );
}
function renderPreview() {
  if (!sourceImage.value || !previewRef.value) return;
  const preview = drawIcon(sourceImage.value, 512);
  const context = previewRef.value.getContext("2d")!;
  context.clearRect(0, 0, 512, 512);
  context.drawImage(preview, 0, 0);
}
watch([sourceImage, zoom, padding, crop, x, y, shape, color], () => nextTick(renderPreview));
function loadFile(file?: File) {
  if (!file?.type.startsWith("image/")) {
    error.value = "请选择 PNG、JPG 或 WebP 图片。";
    return;
  }
  if (sourceUrl.value) URL.revokeObjectURL(sourceUrl.value);
  const url = URL.createObjectURL(file);
  const image = new Image();
  image.onload = () => {
    sourceImage.value = image;
    sourceUrl.value = url;
    zoom.value = 1;
    x.value = 0;
    y.value = 0;
    error.value = undefined;
  };
  image.src = url;
}
function loadInput(event: Event) {
  loadFile((event.target as HTMLInputElement).files?.[0]);
}
function startDrag(event: PointerEvent) {
  if (!sourceImage.value) return;
  dragStart = { x: event.clientX, y: event.clientY, offsetX: x.value, offsetY: y.value };
  dragging.value = true;
  (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
}
function drag(event: PointerEvent) {
  if (!dragging.value || !dragStart) return;
  x.value = dragStart.offsetX + (event.clientX - dragStart.x) / 480;
  y.value = dragStart.offsetY + (event.clientY - dragStart.y) / 480;
}
async function createBundle() {
  if (!sourceImage.value) throw new Error("请先上传一张图标图片。");
  const zip = new JSZip();
  for (const density of densities) {
    zip.file(
      `res/mipmap-${density.name}/ic_launcher.png`,
      await canvasBlob(drawIcon(sourceImage.value, density.size)),
    );
    zip.file(
      `res/mipmap-${density.name}/ic_launcher_adaptive_fore.png`,
      await canvasBlob(drawIcon(sourceImage.value, density.foreground, false, 0.15)),
    );
    zip.file(
      `res/mipmap-${density.name}/ic_launcher_adaptive_back.png`,
      await canvasBlob(drawBackground(density.foreground)),
    );
  }
  zip.file(
    "res/mipmap-anydpi-v26/ic_launcher.xml",
    `<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
  <background android:drawable="@mipmap/ic_launcher_adaptive_back"/>
  <foreground android:drawable="@mipmap/ic_launcher_adaptive_fore"/>
</adaptive-icon>`,
  );
  zip.file("play_store_512.png", await canvasBlob(drawIcon(sourceImage.value, 512)));
  zip.file("1024.png", await canvasBlob(drawIcon(sourceImage.value, 1024)));
  zip.file(
    "manifest.json",
    JSON.stringify(
      {
        format: "android-asset-studio-launcher-icon-v1",
        shape: shape.value,
        color: color.value,
        densities: densities.map((density) => density.name),
        scaling: crop.value ? "crop" : "center",
        generatedAt: new Date().toISOString(),
      },
      null,
      2,
    ),
  );
  return zip.generateAsync({
    type: "blob",
    compression: "DEFLATE",
    compressionOptions: { level: 6 },
  });
}
async function submit() {
  try {
    submitting.value = true;
    error.value = undefined;
    actionsUrl.value = undefined;
    jobStatus.value = undefined;
    window.clearInterval(statusPoll);
    statusPoll = undefined;
    const form = new FormData();
    form.append("bundle", await createBundle(), "YumeBox-IconKit-icons.zip");
    const response = await fetch("/v1/jobs", { method: "POST", body: form });
    if (!response.ok) throw new Error(await response.text());
    const job = (await response.json()) as { actionsUrl: string; statusUrl: string };
    actionsUrl.value = job.actionsUrl;
    jobStatus.value = "queued";
    await refreshJob(job.statusUrl);
    statusPoll = window.setInterval(() => void refreshJob(job.statusUrl), 5000);
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "提交失败，请重试。";
  } finally {
    submitting.value = false;
  }
}
async function refreshJob(statusUrl: string) {
  try {
    const response = await fetch(statusUrl, { cache: "no-store" });
    if (!response.ok) return;
    const job = (await response.json()) as {
      status: "queued" | "running" | "succeeded" | "failed";
      actionsUrl?: string;
    };
    jobStatus.value = job.status;
    if (job.actionsUrl) actionsUrl.value = job.actionsUrl;
    if (job.status === "succeeded" || job.status === "failed") {
      window.clearInterval(statusPoll);
      statusPoll = undefined;
    }
  } catch {
    // A transient poll failure should not hide the workflow link or stop polling.
  }
}
onBeforeUnmount(() => window.clearInterval(statusPoll));
async function downloadBundle() {
  try {
    error.value = undefined;
    const bundle = await createBundle();
    const url = URL.createObjectURL(bundle);
    const link = document.createElement("a");
    link.href = url;
    link.download = "YumeBox-IconKit.zip";
    link.click();
    URL.revokeObjectURL(url);
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "生成 ZIP 失败，请重试。";
  }
}
</script>

<template>
  <main>
    <header>
      <div class="utility">
        <button aria-label="切换深色模式"><Moon :size="21" /></button
        ><button aria-label="切换语言"><Globe2 :size="21" /></button>
      </div>
    </header>
    <section class="hero">
      <h1>YumeBox-IconKit</h1>
      <p>为您的设备生成专属 YumeBox 图标</p>
    </section>
    <section class="workspace">
      <div class="preview-column">
        <div
          :class="['icon-stage', { 'has-image': sourceImage }]"
          @pointerdown="startDrag"
          @pointermove="drag"
          @pointerup="dragging = false"
        >
          <canvas v-if="sourceImage" ref="previewRef" width="512" height="512" />
          <label v-else class="empty-preview"
            ><Upload :size="35" /><span>上传图片</span
            ><input type="file" accept="image/png,image/jpeg,image/webp" @change="loadInput"
          /></label>
        </div>
        <div class="zoom-row">
          <span>预览</span
          ><input
            v-model.number="zoom"
            aria-label="预览缩放"
            type="range"
            min="0.5"
            max="3"
            step="0.01"
          /><output>{{ Math.round(zoom * 100) }}%</output>
        </div>
        <div class="preview-meta">
          <span class="color-dot" :style="canvasStyle"></span><code>{{ color.toUpperCase() }}</code
          ><span>{{ shapeName }}</span>
        </div>
      </div>
      <aside class="controls">
        <section class="background-control">
          <h2>背景</h2>
          <div class="color-input">
            <input v-model="color" aria-label="背景色" type="color" />
            <input v-model="color" aria-label="背景色 HEX" maxlength="7" />
          </div>
        </section>
        <section>
          <h2>形状</h2>
          <div class="shape-tabs">
            <button :class="{ active: shape === 'square' }" @click="shape = 'square'">
              <Square :size="17" />方形</button
            ><button :class="{ active: shape === 'rounded' }" @click="shape = 'rounded'">
              <Square :size="17" />圆角</button
            ><button :class="{ active: shape === 'circle' }" @click="shape = 'circle'">
              <Circle :size="17" />圆形
            </button>
          </div>
        </section>
        <section>
          <div class="section-line">
            <h2>裁剪</h2>
            <label class="replace"
              ><Upload :size="15" />更换图片<input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                @change="loadInput"
            /></label>
          </div>
          <div class="scaling-tabs">
            <button :class="{ active: !crop }" @click="crop = false">居中</button>
            <button :class="{ active: crop }" @click="crop = true">裁切</button>
          </div>
          <label class="range-line"
            ><span>留白</span><output>{{ Math.round(padding * 100) }}%</output></label
          ><input
            v-model.number="padding"
            aria-label="图标内边距"
            type="range"
            min="0"
            max="0.35"
            step="0.01"
          />
        </section>
        <p v-if="error" class="message error">{{ error }}</p>
        <a
          v-if="actionsUrl"
          class="message success"
          :href="actionsUrl"
          target="_blank"
          rel="noreferrer"
          >{{
            jobStatus === "succeeded"
              ? "构建完成"
              : jobStatus === "failed"
                ? "构建失败"
                : jobStatus === "running"
                  ? "构建中"
                  : "已提交"
          }}，打开 Actions <ExternalLink :size="15"
        /></a>
        <div class="action-row">
          <button
            class="download-zip"
            :disabled="!sourceImage || submitting"
            @click="downloadBundle"
          >
            <Download :size="18" />下载 ZIP
          </button>
          <button class="submit" :disabled="!sourceImage || submitting" @click="submit">
            <LoaderCircle v-if="submitting" class="spin" :size="19" /><Send v-else :size="18" />{{
              submitting ? "提交中" : "构建 APK"
            }}
          </button>
        </div>
        <p class="output-note"><Download :size="15" />Asset Studio 图标包</p>
      </aside>
    </section>
  </main>
</template>
