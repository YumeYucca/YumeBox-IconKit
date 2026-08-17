<script setup lang="ts">
import {
  Circle,
  Download,
  ExternalLink,
  LoaderCircle,
  Send,
  Square,
  Upload,
} from "lucide-vue-next";
import type { IconShape } from "./IconPreview.vue";

defineProps<{
  sourceImage?: HTMLImageElement;
  color: string;
  shape: IconShape;
  crop: boolean;
  padding: number;
  submitting: boolean;
  actionsUrl?: string;
  jobStatus?: "queued" | "running" | "succeeded" | "failed";
  error?: string;
}>();
const emit = defineEmits<{
  file: [file?: File];
  "update:color": [value: string];
  "update:shape": [value: IconShape];
  "update:crop": [value: boolean];
  "update:padding": [value: number];
  download: [];
  submit: [];
}>();

function loadInput(event: Event) {
  emit("file", (event.target as HTMLInputElement).files?.[0]);
}
function statusText(status?: "queued" | "running" | "succeeded" | "failed") {
  if (status === "succeeded") return "构建完成";
  if (status === "failed") return "构建失败";
  if (status === "running") return "构建中";
  return "已提交";
}
</script>

<template>
  <aside class="controls">
    <section class="background-control">
      <h2>背景</h2>
      <div class="color-input">
        <input
          :value="color"
          aria-label="背景色"
          type="color"
          @input="emit('update:color', ($event.target as HTMLInputElement).value)"
        />
        <input
          :value="color"
          aria-label="背景色 HEX"
          maxlength="7"
          @input="emit('update:color', ($event.target as HTMLInputElement).value)"
        />
      </div>
    </section>
    <section>
      <h2>形状</h2>
      <div class="shape-tabs">
        <button :class="{ active: shape === 'square' }" @click="emit('update:shape', 'square')">
          <Square :size="17" />方形
        </button>
        <button :class="{ active: shape === 'rounded' }" @click="emit('update:shape', 'rounded')">
          <Square :size="17" />圆角
        </button>
        <button :class="{ active: shape === 'circle' }" @click="emit('update:shape', 'circle')">
          <Circle :size="17" />圆形
        </button>
      </div>
    </section>
    <section>
      <div class="section-line">
        <h2>裁剪</h2>
        <label class="replace">
          <Upload :size="15" />更换图片
          <input type="file" accept="image/png,image/jpeg,image/webp" @change="loadInput" />
        </label>
      </div>
      <div class="scaling-tabs">
        <button :class="{ active: !crop }" @click="emit('update:crop', false)">居中</button>
        <button :class="{ active: crop }" @click="emit('update:crop', true)">裁切</button>
      </div>
      <label class="range-line"
        ><span>留白</span><output>{{ Math.round(padding * 100) }}%</output></label
      >
      <input
        :value="padding"
        aria-label="图标内边距"
        type="range"
        min="0"
        max="0.35"
        step="0.01"
        @input="emit('update:padding', Number(($event.target as HTMLInputElement).value))"
      />
    </section>
    <p v-if="error" class="message error">{{ error }}</p>
    <a
      v-if="actionsUrl"
      class="message success"
      :href="actionsUrl"
      target="_blank"
      rel="noreferrer"
    >
      {{ statusText(jobStatus) }}，打开 Actions <ExternalLink :size="15" />
    </a>
    <div class="action-row">
      <button class="download-zip" :disabled="!sourceImage || submitting" @click="emit('download')">
        <Download :size="18" />下载 ZIP
      </button>
      <button class="submit" :disabled="!sourceImage || submitting" @click="emit('submit')">
        <LoaderCircle v-if="submitting" class="spin" :size="19" />
        <Send v-else :size="18" />
        {{ submitting ? "提交中" : "构建 APK" }}
      </button>
    </div>
    <p class="output-note"><Download :size="15" />Asset Studio 图标包</p>
  </aside>
</template>
