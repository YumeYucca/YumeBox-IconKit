<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { Upload } from "lucide-vue-next";

export type IconShape = "square" | "rounded" | "circle";

const props = defineProps<{
  sourceImage?: HTMLImageElement;
  color: string;
  shape: IconShape;
  zoom: number;
  padding: number;
  crop: boolean;
  x: number;
  y: number;
}>();
const emit = defineEmits<{
  file: [file?: File];
  "update:zoom": [value: number];
  "update:x": [value: number];
  "update:y": [value: number];
}>();

const previewRef = ref<HTMLCanvasElement>();
const dragging = ref(false);
let dragStart: { x: number; y: number; offsetX: number; offsetY: number } | undefined;
const canvasStyle = computed(() => ({ background: props.color }));
const shapeName = computed(() =>
  props.shape === "circle" ? "圆形" : props.shape === "rounded" ? "圆角" : "方形",
);

function clipShape(context: CanvasRenderingContext2D, size: number) {
  context.beginPath();
  if (props.shape === "circle") context.arc(size / 2, size / 2, size / 2, 0, Math.PI * 2);
  else if (props.shape === "rounded") context.roundRect(0, 0, size, size, size * 0.22);
  else context.rect(0, 0, size, size);
  context.clip();
}
function renderPreview() {
  if (!props.sourceImage || !previewRef.value) return;
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 512;
  const context = canvas.getContext("2d")!;
  context.save();
  clipShape(context, 512);
  context.fillStyle = props.color;
  context.fillRect(0, 0, 512, 512);
  const available = 512 * (1 - props.padding * 2);
  const baseScale = props.crop
    ? Math.max(
        available / props.sourceImage.naturalWidth,
        available / props.sourceImage.naturalHeight,
      )
    : Math.min(
        available / props.sourceImage.naturalWidth,
        available / props.sourceImage.naturalHeight,
      );
  const width = props.sourceImage.naturalWidth * baseScale * props.zoom;
  const height = props.sourceImage.naturalHeight * baseScale * props.zoom;
  context.drawImage(
    props.sourceImage,
    (512 - width) / 2 + props.x * 512,
    (512 - height) / 2 + props.y * 512,
    width,
    height,
  );
  context.restore();
  const previewContext = previewRef.value.getContext("2d")!;
  previewContext.clearRect(0, 0, 512, 512);
  previewContext.drawImage(canvas, 0, 0);
}
function loadInput(event: Event) {
  emit("file", (event.target as HTMLInputElement).files?.[0]);
}
function startDrag(event: PointerEvent) {
  if (!props.sourceImage) return;
  dragStart = { x: event.clientX, y: event.clientY, offsetX: props.x, offsetY: props.y };
  dragging.value = true;
  (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
}
function drag(event: PointerEvent) {
  if (!dragging.value || !dragStart) return;
  const stage = event.currentTarget as HTMLElement;
  const size = stage.getBoundingClientRect().width;
  emit("update:x", dragStart.offsetX + (event.clientX - dragStart.x) / size);
  emit("update:y", dragStart.offsetY + (event.clientY - dragStart.y) / size);
}
watch(
  () => [
    props.sourceImage,
    props.color,
    props.shape,
    props.zoom,
    props.padding,
    props.crop,
    props.x,
    props.y,
  ],
  () => nextTick(renderPreview),
);
</script>

<template>
  <div class="preview-column">
    <div
      :class="['icon-stage', { 'has-image': sourceImage }]"
      @pointerdown="startDrag"
      @pointermove="drag"
      @pointerup="dragging = false"
    >
      <canvas v-if="sourceImage" ref="previewRef" width="512" height="512" />
      <label v-else class="empty-preview">
        <Upload :size="35" />
        <span>上传图片</span>
        <input type="file" accept="image/png,image/jpeg,image/webp" @change="loadInput" />
      </label>
    </div>
    <div class="zoom-row">
      <span>预览</span>
      <input
        :value="zoom"
        aria-label="预览缩放"
        type="range"
        min="0.5"
        max="3"
        step="0.01"
        @input="emit('update:zoom', Number(($event.target as HTMLInputElement).value))"
      />
      <output>{{ Math.round(zoom * 100) }}%</output>
    </div>
    <div class="preview-meta">
      <span class="color-dot" :style="canvasStyle"></span>
      <code>{{ color.toUpperCase() }}</code>
      <span>{{ shapeName }}</span>
    </div>
  </div>
</template>
