<script setup>
defineProps({
  status: {
    type: String,
    default: 'checking',
  },
  label: {
    type: String,
    required: true,
  },
})
</script>

<template>
  <span class="status-panel" :class="`status-panel--${status}`" aria-live="polite">
    <span class="status-panel__dot" aria-hidden="true"></span>
    {{ label }}
  </span>
</template>

<style scoped>
.status-panel {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #45524d;
  font-size: 13px;
  line-height: 1;
  white-space: nowrap;
}

.status-panel__dot {
  width: 8px;
  height: 8px;
  flex: 0 0 8px;
  border-radius: 50%;
  background: #c68b3b;
}

.status-panel--online .status-panel__dot {
  background: #25836d;
}

.status-panel--offline .status-panel__dot {
  background: #c24e3e;
}
</style>
