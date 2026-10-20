<script setup>
import { ref } from 'vue'

const selectedTag = ref('通过')
const tags = ['通过', '未通过', '不匹配', '建议降权']

const stars = [1, 2, 3, 4, 5]
const activeStar = ref(5)

function setStar(n) {
  activeStar.value = n
}
function selectTag(t) {
  selectedTag.value = t
}
</script>

<template>
  <div class="card feedback-panel">
    <div class="card-header">
      <span class="step-num" style="background:#22C55E;">4</span>
      <span class="card-title">人工评价与面试反馈</span>
    </div>
    <div class="card-body">
      <div class="resume-name">陈 一 · 高级数据分析师</div>
      <div class="feedback-row">
        <span class="label">通过岗位：</span>
        <span class="value" style="color:#22C55E;">匹配岗位 · 高级数据分析师</span>
      </div>
      <div class="feedback-row">
        <span class="label">星打分为：</span>
        <div class="rating-stars">
          <svg
            v-for="star in stars"
            :key="star"
            :class="star <= activeStar ? 'filled' : 'empty'"
            viewBox="0 0 24 24"
            @click="setStar(star)"
          >
            <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
          </svg>
        </div>
      </div>
      <div class="feedback-row">
        <span class="label">评价标签：</span>
      </div>
      <div class="feedback-tags">
        <span
          v-for="tag in tags"
          :key="tag"
          class="fb-tag"
          :class="{ selected: selectedTag === tag }"
          @click="selectTag(tag)"
        >
          {{ tag }}
        </span>
      </div>
      <div class="feedback-note">
        专业功底扎实，数据建模能力突出。面试中表现优秀，沟通清晰，对业务理解到位。建议优先推进终面。
      </div>
      <button class="btn-block">反馈优化给中心</button>
    </div>
  </div>
</template>
