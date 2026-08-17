<script setup lang="ts">
import { onBeforeUnmount, ref } from "vue";
import JSZip from "jszip";
import { Globe2, Moon } from "lucide-vue-next";
import IconControls from "./components/IconControls.vue";
import IconPreview, { type IconShape } from "./components/IconPreview.vue";

const densities = [
  { name: "mdpi", size: 48, foreground: 108 },
  { name: "hdpi", size: 72, foreground: 162 },
  { name: "xhdpi", size: 96, foreground: 216 },
  { name: "xxhdpi", size: 144, foreground: 324 },
  { name: "xxxhdpi", size: 192, foreground: 432 },
];

const sourceUrl = ref<string>();
const sourceImage = ref<HTMLImageElement>();
const color = ref("#ffffff");
const shape = ref<IconShape>("rounded");
const zoom = ref(1);
const padding = ref(0);
const crop = ref(false);
const x = ref(0);
const y = ref(0);
const submitting = ref(false);
const actionsUrl = ref<string>();
const jobStatus = ref<"queued" | "running" | "succeeded" | "failed">();
const error = ref<string>();
let statusPoll: number | undefined;

function clipShape(context: CanvasRenderingContext2D, size: number) {
  context.beginPath();
  if (shape.value === "circle") context.arc(size / 2, size / 2, size / 2, 0, Math.PI * 2);
  else if (shape.value === "rounded") context.roundRect(0, 0, size, size, size * 0.22);
  else context.rect(0, 0, size, size);
  context.clip();
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
  clipShape(context, size);
  if (includeBackground) {
    context.fillStyle = color.value;
    context.fillRect(0, 0, size, size);
  }
  const available = size * (1 - (padding.value + extraPadding) * 2);
  const baseScale = crop.value
    ? Math.max(available / source.naturalWidth, available / source.naturalHeight)
    : Math.min(available / source.naturalWidth, available / source.naturalHeight);
  const width = source.naturalWidth * baseScale * zoom.value;
  const height = source.naturalHeight * baseScale * zoom.value;
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
  const context = canvas.getContext("2d")!;
  context.fillStyle = color.value;
  context.fillRect(0, 0, size, size);
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
    // Preserve the workflow link and try again after a transient polling failure.
  }
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
onBeforeUnmount(() => window.clearInterval(statusPoll));
</script>

<template>
  <main>
    <header>
      <div class="utility">
        <button aria-label="切换深色模式"><Moon :size="21" /></button>
        <button aria-label="切换语言"><Globe2 :size="21" /></button>
      </div>
    </header>
    <section class="hero">
      <h1>YumeBox-IconKit</h1>
      <p>为您的设备生成专属 YumeBox 图标</p>
    </section>
    <section class="workspace">
      <IconPreview
        :source-image="sourceImage"
        :color="color"
        :shape="shape"
        :zoom="zoom"
        :padding="padding"
        :crop="crop"
        :x="x"
        :y="y"
        @file="loadFile"
        @update:zoom="zoom = $event"
        @update:x="x = $event"
        @update:y="y = $event"
      />
      <IconControls
        :source-image="sourceImage"
        :color="color"
        :shape="shape"
        :crop="crop"
        :padding="padding"
        :submitting="submitting"
        :actions-url="actionsUrl"
        :job-status="jobStatus"
        :error="error"
        @file="loadFile"
        @update:color="color = $event"
        @update:shape="shape = $event"
        @update:crop="crop = $event"
        @update:padding="padding = $event"
        @download="downloadBundle"
        @submit="submit"
      />
    </section>
  </main>
</template>
