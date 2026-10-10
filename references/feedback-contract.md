# 生成反馈与排序边界

在本 Skill 目录记录有证据的反馈：`python3 ../1viral-knowledge-builder-local/scripts/viral_db.py record-feedback --input feedback.json`。只记录本轮实际评审过的 Prompt 或成片，不自动补造评分。

Prompt 审核和成片审核是两种不同证据。Prompt 通过仅说明提示词合同符合要求；成片必须用 `review_render.py` 核对音频、ASR 对应台词、Hook、产品、动作和连续性，不能把音轨存在或静帧正常当作成片通过。

将有证据的记录写入 Builder v3 的 `generation_feedback`，可调用 Builder 的 `viral_db.py record-feedback`。字段包括 `generationId`、`bundleKey`、`patternKey`、`assetKeys`、`productCategory`、`videoModel`、`duration`、`reviewStage`、`scores`、`failureReasons`、`renderedPassed`、`artifact`、`reviewer`、`inspectionMode`。成片评审需指明实际视频路径、评审者和 `direct-video-and-audio`。不要上传视频以换取反馈，也不要自动提交重试。

同一 Pattern 的成片审核样本少于 5 条时，反馈只展示不影响排序；达到 5 条后才小权重参与。负反馈不删除旧知识。未来真实投放数据必须带来源和观察窗口，跨账号/国家/预算时按账号基线归一，不将生成评审分伪装成 CTR/CVR。
