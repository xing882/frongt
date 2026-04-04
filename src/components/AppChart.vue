<script setup>
import * as echarts from 'echarts'
import { onMounted, onUnmounted, ref, watch } from 'vue'

const props = defineProps({
  option: { type: Object, required: true },
  theme: { type: String, default: undefined },
})

const root = ref(null)
let chart

function resize() {
  chart?.resize()
}

onMounted(() => {
  if (!root.value) return
  chart = echarts.init(root.value, props.theme)
  chart.setOption(props.option)
  window.addEventListener('resize', resize)
})

watch(
  () => props.option,
  (o) => {
    if (chart && o) chart.setOption(o, true)
  },
  { deep: true },
)

onUnmounted(() => {
  window.removeEventListener('resize', resize)
  chart?.dispose()
  chart = undefined
})
</script>

<template>
  <div ref="root" class="app-chart" />
</template>

<style scoped>
.app-chart {
  width: 100%;
  min-height: 280px;
  height: 100%;
}
</style>
