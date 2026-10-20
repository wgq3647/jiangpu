<script setup>
const matchCards = [
  {
    company: '招聘需求 A · 互联网公司',
    position: '高级数据分析师',
    gradient: 'linear-gradient(135deg, #4F6EF7, #6B8AF9)',
    candidates: [
      { name: '赵 四', score: 91, level: 'high', tags: [{ text: '学历匹配', type: 'match' }, { text: '技能强匹配', type: 'match' }, { text: '5年经验', type: '' }] },
      { name: '孙 五', score: 82, level: 'high', tags: [{ text: '学历匹配', type: 'match' }, { text: '4年经验', type: '' }] },
      { name: '周 六', score: 70, level: 'mid', tags: [{ text: '技能部分匹配', type: '' }, { text: '3年经验', type: '' }] }
    ],
    total: 12
  },
  {
    company: '招聘需求 B · 金融科技',
    position: '产品经理',
    gradient: 'linear-gradient(135deg, #6366F1, #818CF8)',
    candidates: [
      { name: '陈 一', score: 88, level: 'high', tags: [{ text: '语义高亮', type: 'match' }, { text: 'Axure / SQL', type: 'match' }, { text: '4年产品', type: '' }] },
      { name: '林 二', score: 76, level: 'mid', tags: [{ text: '可备选', type: '' }, { text: '用户增长', type: '' }] },
      { name: '林 三', score: 72, level: 'mid', tags: [{ text: '可备选', type: '' }, { text: '中台建设', type: '' }] }
    ],
    total: 8
  },
  {
    company: '招聘需求 C · AI 公司',
    position: '算法工程师',
    gradient: 'linear-gradient(135deg, #0EA5E9, #38BDF8)',
    candidates: [
      { name: '赵 四', score: 85, level: 'high', tags: [{ text: 'Python / Java', type: 'match' }, { text: 'NLP 项目', type: '' }] },
      { name: '孙 五', score: 78, level: 'mid', tags: [{ text: '推荐系统', type: '' }, { text: '5年经验', type: '' }] },
      { name: '吴 七', score: 43, level: 'low', tags: [{ text: '学历未达标', type: 'hard' }] }
    ],
    total: 6
  },
  {
    company: '招聘需求 D · 电商平台',
    position: '运营专家',
    gradient: 'linear-gradient(135deg, #8B5CF6, #A78BFA)',
    candidates: [
      { name: '周 六', score: 70, level: 'mid', tags: [{ text: '跨岗位适配', type: '' }, { text: '内容运营', type: '' }] },
      { name: '郑 八', score: 65, level: 'mid', tags: [{ text: '用户运营', type: '' }, { text: '3年经验', type: '' }] },
      { name: '王 九', score: 54, level: 'low', tags: [{ text: '暂不推送', type: '' }] }
    ],
    total: 5
  }
]
</script>

<template>
  <div class="card">
    <div class="card-header">
      <span class="step-num">3</span>
      <span class="card-title">多岗位匹配结果</span>
      <span class="card-subtitle">每份简历自动遍历全部在招 JD，按匹配度降序排列</span>
    </div>
    <div class="card-body">
      <div class="match-cards">
        <div v-for="card in matchCards" :key="card.position + card.company" class="match-card">
          <div class="match-card-header" :style="{ background: card.gradient }">
            <div class="jc-name">{{ card.position }}</div>
            <div class="jc-company">{{ card.company }}</div>
          </div>
          <div class="match-card-body">
            <div v-for="cand in card.candidates" :key="cand.name" class="candidate-item">
              <div class="candidate-top">
                <span class="candidate-name">{{ cand.name }}</span>
                <span class="candidate-score" :class="cand.level">{{ cand.score }}</span>
              </div>
              <div class="candidate-tags">
                <span v-for="tag in cand.tags" :key="tag.text" class="mini-tag" :class="tag.type">
                  {{ tag.text }}
                </span>
              </div>
            </div>
          </div>
          <div class="match-card-footer">
            <button>查看全部 {{ card.total }} 位候选人</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
