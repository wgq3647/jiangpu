# -*- coding: utf-8 -*-
"""
向量嵌入语义匹配模块
基于FastEmbed（ONNX推理，无需PyTorch），提供文本语义相似度计算
作为关键词匹配和LLM之间的中间层，解决"税务申报≈纳税申报"类语义等价问题
"""
import os
import logging
import numpy as np
from typing import List, Optional, Tuple

# 配置HuggingFace国内镜像（解决模型下载网络问题）
# 优先级：环境变量HF_ENDPOINT > 国内镜像hf-mirror.com > 默认
if not os.environ.get('HF_ENDPOINT'):
    os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
if not os.environ.get('HF_HUB_ENABLE_HF_TRANSFER'):
    os.environ['HF_HUB_ENABLE_HF_TRANSFER'] = '0'

logger = logging.getLogger(__name__)


class SemanticEmbedding:
    """
    语义嵌入单例
    延迟加载：第一次使用时才下载和初始化模型
    模型：BAAI/bge-small-zh-v1.5（中文优化，384维，体积小速度快）
    """

    _instance = None
    _model = None
    _available = None  # None=未检测, True=可用, False=不可用

    # 语义匹配阈值
    THRESHOLD_HIGH = 0.75   # 高相似度，视为完全匹配
    THRESHOLD_MEDIUM = 0.60 # 中等相似度，视为部分匹配
    THRESHOLD_LOW = 0.45    # 低相似度阈值，低于此视为不匹配

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _ensure_model(self) -> bool:
        """确保模型已加载，返回是否可用"""
        if self._available is not None:
            return self._available

        try:
            from fastembed import TextEmbedding
            # 使用中文优化的轻量模型，首次会自动下载（约100MB）
            # 通过HF_ENDPOINT环境变量使用国内镜像加速下载
            logger.info("正在加载语义嵌入模型 BAAI/bge-small-zh-v1.5（首次需下载约100MB）...")
            self._model = TextEmbedding(model_name="BAAI/bge-small-zh-v1.5")
            self._available = True
            logger.info("语义嵌入模型加载成功: BAAI/bge-small-zh-v1.5")
        except Exception as e:
            error_msg = str(e)
            logger.warning(f"语义嵌入模型加载失败，将使用字符相似度降级: {error_msg}")
            if 'Connection' in error_msg or '10061' in error_msg or 'timeout' in error_msg.lower():
                logger.warning("网络连接失败提示：可尝试设置环境变量 HF_ENDPOINT=https://hf-mirror.com 使用国内镜像")
            self._available = False
            self._model = None

        return self._available

    def is_available(self) -> bool:
        """检查语义嵌入是否可用"""
        return self._ensure_model()

    def _embed(self, text: str) -> Optional[np.ndarray]:
        """将文本转为向量"""
        if not self._ensure_model() or not text or not text.strip():
            return None
        try:
            embeddings = list(self._model.embed([text.strip()]))
            if embeddings and len(embeddings) > 0:
                return np.array(embeddings[0])
        except Exception as e:
            logger.warning(f"文本嵌入失败: {str(e)}")
        return None

    def _embed_batch(self, texts: List[str]) -> List[Optional[np.ndarray]]:
        """批量文本转向量"""
        if not self._ensure_model():
            return [None] * len(texts)
        # 过滤空文本
        valid_indices = [i for i, t in enumerate(texts) if t and t.strip()]
        if not valid_indices:
            return [None] * len(texts)
        try:
            valid_texts = [texts[i].strip() for i in valid_indices]
            embeddings = list(self._model.embed(valid_texts))
            result = [None] * len(texts)
            for idx, emb in zip(valid_indices, embeddings):
                result[idx] = np.array(emb)
            return result
        except Exception as e:
            logger.warning(f"批量嵌入失败: {str(e)}")
            return [None] * len(texts)

    @staticmethod
    def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """计算余弦相似度"""
        if vec1 is None or vec2 is None:
            return 0.0
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(vec1, vec2) / (norm1 * norm2))

    def similarity(self, text1: str, text2: str) -> float:
        """
        计算两个文本的语义相似度（0-1）
        优先使用向量嵌入，不可用时回退到字符Jaccard相似度
        """
        if not text1 or not text2:
            return 0.0

        # 精确包含直接返回高相似度
        t1_lower = text1.lower().strip()
        t2_lower = text2.lower().strip()
        if t1_lower == t2_lower:
            return 1.0
        if t2_lower in t1_lower or t1_lower in t2_lower:
            return 0.92

        # 向量语义匹配
        vec1 = self._embed(text1)
        vec2 = self._embed(text2)
        if vec1 is not None and vec2 is not None:
            sim = self._cosine_similarity(vec1, vec2)
            # 向量相似度通常偏低，做尺度变换让匹配更合理
            # 0.5 -> 0.6, 0.6 -> 0.72, 0.7 -> 0.84, 0.8 -> 0.95
            adjusted = min(1.0, sim * 1.15 + 0.05)
            return round(adjusted, 4)

        # 降级：字符级Jaccard相似度
        return self._jaccard_similarity(text1, text2)

    def batch_similarity(self, query: str, candidates: List[str]) -> List[float]:
        """
        批量计算一个查询文本与多个候选文本的相似度
        比逐个调用更高效（只嵌入一次查询文本）
        """
        if not query or not candidates:
            return [0.0] * len(candidates)

        # 精确匹配快速通道
        results = []
        query_lower = query.lower().strip()
        for c in candidates:
            if not c:
                results.append(0.0)
                continue
            c_lower = c.lower().strip()
            if query_lower == c_lower:
                results.append(1.0)
            elif c_lower in query_lower or query_lower in c_lower:
                results.append(0.92)
            else:
                results.append(None)  # 标记为需要向量计算

        # 需要向量计算的索引
        need_vec_indices = [i for i, r in enumerate(results) if r is None]
        if need_vec_indices and self._ensure_model():
            need_texts = [candidates[i] for i in need_vec_indices]
            query_vec = self._embed(query)
            candidate_vecs = self._embed_batch(need_texts)
            for idx, c_vec in zip(need_vec_indices, candidate_vecs):
                if query_vec is not None and c_vec is not None:
                    sim = self._cosine_similarity(query_vec, c_vec)
                    adjusted = min(1.0, sim * 1.15 + 0.05)
                    results[idx] = round(adjusted, 4)
                else:
                    results[idx] = self._jaccard_similarity(query, candidates[idx])

        # 剩余的用降级方案
        for i in range(len(results)):
            if results[i] is None:
                results[i] = self._jaccard_similarity(query, candidates[i])

        return results

    def match_set_semantic(
        self,
        resume_value: str,
        required_items: List[str],
        match_mode: str = "all"
    ) -> Tuple[bool, float, List[dict]]:
        """
        集合语义匹配（技能、证书等多值字段）
        对每个要求项，在简历中找语义最相似的项
        返回: (是否通过, 得分0-100, 匹配详情列表)
        """
        if not resume_value or not required_items:
            return False, 0.0, []

        import re
        resume_items = [item.strip() for item in re.split(r'[,，、/|；;]', resume_value) if item.strip()]

        if not resume_items:
            return False, 0.0, []

        # 批量计算每个要求项与所有简历项的相似度
        details = []
        matched_count = 0

        for req_item in required_items:
            sims = self.batch_similarity(req_item, resume_items)
            best_idx = int(np.argmax(sims)) if sims else -1
            best_sim = sims[best_idx] if best_idx >= 0 else 0.0
            best_match = resume_items[best_idx] if best_idx >= 0 else ""

            # 高相似度视为匹配
            is_matched = best_sim >= self.THRESHOLD_MEDIUM
            if is_matched:
                matched_count += 1

            details.append({
                'required': req_item,
                'matched': best_match,
                'similarity': round(best_sim * 100, 1),
                'is_matched': is_matched
            })

        # 判定是否通过
        if match_mode == 'all':
            passed = matched_count == len(required_items)
        else:  # any
            passed = matched_count >= 1

        score = int(matched_count / len(required_items) * 100)
        return passed, score, details

    @staticmethod
    def _jaccard_similarity(text1: str, text2: str) -> float:
        """字符级Jaccard相似度（降级方案）"""
        if not text1 or not text2:
            return 0.0
        t1 = set(text1.lower())
        t2 = set(text2.lower())
        intersection = len(t1 & t2)
        union = len(t1 | t2)
        if union == 0:
            return 0.0
        return round(intersection / union, 4)


# 全局单例
semantic_embedding = SemanticEmbedding()
