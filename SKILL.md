---
name: LuluLab-Product-Video
description: 根据商品图生成 1～10 条原创 UGC 或剧情带货视频，可配置市场、口播语言、提示词、模型、时长、数量及达人方式（AI 生成或用户提供），默认使用 LuluLab Node.js CLI。
metadata:
  version: "v8.3.0"
license: GPL-3.0-only
---

# LuluLab 带货视频

## 定位与执行边界

以用户提供的产品图创建 1～10 条独立带货视频。保留 `batch-product-video` v5.1.1 的四字段输入、UGC/剧情分支、最少 Segment 拆分、达人参考图、逐段生成、拼接、结果保存和最多 3 条完整视频并发的流程。以下三个环节改用 LuluLab Node.js CLI 作为默认入口：

1. `scripts/prompt_workflow.py` 经 `scripts/lululab_cli.mjs` 提交 `SalesVideoPromptV2`。核心元提示词只存在于私有工作流的“原创视频元提示词”节点；本地 `scripts/prompt_validator.py` 只校验返回结果，不生成创意。不得运行旧版 `local_prompt.py`、本地母提示词、知识库检索或其他提示词生成链路。
2. 未提供达人图时，`scripts/local_creator_image_generate.py` 经 LuluLab `ImageGenV2`，使用全部产品原图生成一张多视角真人达人产品参考图；批量默认共用。用户提供达人图时直接使用，不另行生图。
3. `scripts/video_cli.py` 在视频阶段验证 LuluLab `VideoGenV2` 是否支持已确认模型及配置，并优先使用 `scripts/local_video_generate.py --provider lululab_cli`。仅 LuluLab 在任何视频提交前不可用或不支持时，依次检查 LibTV、小云雀、即梦。提交后锁定当前 provider 和任务 ID，不因失败或超时换渠道或重提。

使用 Node.js ≥20；Python ≥3.10；多段拼接需要 FFmpeg。API Key 仅在首次 LuluLab 计费提交前由 CLI 从本地已配置凭证读取，同时查询积分；不在对话、提示词、任务 JSON 或日志中展示密钥。首次只读预检：在展示确认配置前运行 `scripts/video_cli.py preflight --model <当前模型>` 检查 CLI 能力；该步骤不得读取凭证、提交任务或输出成功的渠道诊断。实际视频提交前再验证登录、余额及模型 schema。远程工作流必须已部署并将 workflow ID `SalesVideoPromptV2` 映射到本文的私有工作流；n8n 显示名本身不是 workflow ID。

## 商品拆解与用户确认

没有产品图时仅请求产品图。收到图后，保守识别商品类别、清晰可辨的品牌及最多三个卖点。将图片可见依据、用户提供的信息、推断的展示角度和未知功效分开；不编造成分、疗效、认证、销量、参数或价格。每条卖点以“依据 → 可用于视频的表达”说明；没有依据就不凑数。目标市场默认美国，不从对话语言推断市场；口播语言按目标市场或用户明确要求确定。

任何付费提示词、图片或视频提交前，只发一次简短确认。确认页分为“已识别商品”和“生成配置”：商品名称及有依据的卖点用项目符号列出；所有用户可选择的配置都要列出完整选项，不能只报当前值，也不能隐藏默认选项。画幅、清晰度、声音、字幕、水印和生成渠道不列为用户选项。

默认配置为原创 UGC、工作流生成提示词、`seedance-2-fast`（显示 **Seedance 2.0 Fast**）、15 秒、1 条、AI 生成达人图、美国市场及按美国市场确定的英语口播。目标市场可由用户指定任意国家或地区；口播语言可按市场默认，也可单独指定。视频类型可选原创 UGC（`ugcProductDemo`）或剧情带货（`storyDrivenAd`）；提示词可由工作流生成，也可由用户提供创作要求或提示词；达人可由 AI 生成，也可由用户提供达人参考图。用户选择提供达人时，若图片尚未提供，先收取图片，再展示最终确认配置。可选模型限 `seedance-2-fast`、`seedance-2-mini`、`seedance-2`、`seedance-2-5`；时长 4～60 秒，数量 1～10 条。用户已明确的设置优先。

生成配置必须使用 Markdown 表格展示，每个配置项单独一行，选项在单元格内逐项换行或用 `<br>` 分隔。每个离散选项都列全，并在默认选项后标注“（默认）”；若用户指定非默认选项，保留默认标记并在所选项后标注“（当前选择）”。市场及口播语言是可自由输入值，不要伪造有限选项列表；显示当前值、默认规则及可修改说明。时长与数量显示允许范围、默认值和当前值。确认页末尾提供 `[1] 按默认配置继续`（若存在非默认选择则改为 `[1] 按当前配置继续`）和 `[2] 修改配置`；用户也可直接回复“确认生成”或用自然语言修改多个字段。任一明确等效的确认即授权本轮已列配置的提示词、必要的达人图和视频计费提交；后续同配置各阶段不重复确认。若达人选择用户提供参考图，不生成 AI 达人图，其余付费流程不变。额外任务、付费重试或改变付费模型／渠道需要重新授权。

确认格式示例：

```markdown
已识别商品（可修改）

- 名称：气垫腮红
- 卖点：粉盒内侧可见镜面 → 展示照镜补妆；配有粉扑 → 展示粉扑上妆；可见珊瑚粉色腮红 → 展示产品颜色

生成配置

| 配置项 | 可选项与当前设置 |
|---|---|
| 视频类型 | 原创 UGC（默认；当前选择）<br>剧情带货 |
| 提示词 | 工作流生成（默认；当前选择）<br>用户提供提示词或创作要求 |
| 目标市场 | 美国（默认；当前选择），可指定其他国家或地区 |
| 口播语言 | 英语（美国市场默认；当前选择），可单独指定 |
| 视频模型 | Seedance 2.0 Fast（默认；当前选择）<br>Seedance 2.0 Mini<br>Seedance 2.0<br>Seedance 2.5 |
| 时长 | 4～60 秒；默认 15 秒，当前 15 秒 |
| 数量 | 1～10 条；默认 1 条，当前 1 条 |
| 达人 | AI 生成达人参考图（默认；当前选择）<br>用户提供达人参考图 |

确认后将提交提示词、按所选达人方式执行的参考图步骤及视频任务，可能消耗账户积分或产生费用。

[1] 按默认配置继续
[2] 修改配置
```

如达人选择为“用户提供”，确认文案应明确本轮不会提交 AI 达人图生成任务；用户需在提示词和视频提交前提供图片。表格只展示可选配置，不加入“付费确认”行。表格后用一句简短说明告知用户：确认后会提交本轮所需的提示词、所选达人图步骤和视频任务，可能消耗账户积分或产生费用；然后提供确认或修改入口。不得列画幅、清晰度、声音、字幕、水印或视频生成渠道。用户不需要写完整脚本。

## 输入与提示词工作流

每条视频独立提交一份请求，顶层**只能**有 `productBrief`、`userConfig`、`creativeRequirement`、`creatorBrief`：

```json
{
  "productBrief": {
    "productName": "",
    "sellingPoints": "",
    "targetCountry": "美国",
    "targetAudience": "",
    "productImages": [{"path": "/absolute/product.png"}]
  },
  "userConfig": {
    "videoModel": "seedance-2-fast",
    "duration": 15,
    "videoStyle": "ugcProductDemo",
    "interactionLanguage": "zh-CN",
    "promptLanguage": "zh-CN",
    "mediaLanguage": "en-US"
  },
  "creativeRequirement": "",
  "creatorBrief": {"creatorMode": "auto", "creatorImages": []}
}
```

`videoStyle` 为 `ugcProductDemo` 或 `storyDrivenAd`。数量只控制本地循环，不写入请求。三个语言字段由智能体在付费前解析：交互及提示词语言遵循用户要求；实际口播语言遵循用户指定值或目标市场。用户提供创作约束时原样放入 `creativeRequirement`。提供达人图时用 `creatorMode: "referCreator"` 并列出本地 `creatorImages`。

工作流的通用、UGC 与剧情元提示词只保留在私有服务端，并按 `videoStyle` 选分支。每条返回的顶层只能是 `videoPrompts` 与 `creatorPrompts`。剧情节拍、连续时间轴、独立 Segment、固定声音、自然 CTA 和禁止无依据功效均由工作流要求；`scripts/prompt_validator.py` 校验结构、模型时长、最少 Segment、连续时间轴、跨段引用和声音一致性。校验失败不得提交视频，也不得自动再次提交付费提示词任务。展示完整返回提示词供用户查看。

用 `python3 scripts/prompt_workflow.py --input request.json --output prompt_01.json` 提交。保存原 task ID；超时或状态不确定时只用 `--resume-task-id ID` 恢复原任务，不能自动重提。提示词库接口只有在实际配置适配器时才使用；目前没有数据源，不能访问飞书或索要其凭证。

## 达人图与视频

自动达人图须结合已确认市场、受众、产品、卖点及创意要求，呈现自然真实的普通 UGC 创作者。单张三视图参考板中保持同一人、产品及固定配饰；产品在所有视角均真实出现，保留原图可见外观，不凭空补造细节。用所有有效产品原图作为 LuluLab `ImageGenV2` 的实际 `referenceImages`，默认 `gpt-image-2-5-sunburst`。LuluLab 在提交前明确不可用时，可使用经验证可用的智能体生图能力；仍不可用时说明阻碍，不临时猜测其他付费接口。图片成功后展示成品，再进入视频生成。LuluLab 图片任务提交状态不确定时只恢复原 task ID，不自动转投其他生图工具。

视频模型映射：

| 逻辑模型 | 单段时长 | 小云雀／即梦精确 ID |
|---|---|---|
| `seedance-2-fast` | 4～15 秒 | `seedance2.0fast_vip` |
| `seedance-2-mini` | 4～15 秒 | `seedance2.0mini_vip` |
| `seedance-2` | 4～15 秒 | `seedance2.0_vip` |
| `seedance-2-5` | 4～30 秒 | `seedance2.5` |

LuluLab CLI 使用逻辑模型 ID；LibTV 按实时模型目录和 schema 验证，不传上述 provider ID。视频阶段运行只读 preflight；选第一个对已确认模型、时长和参考图配置真正可用且已登录的渠道。不能仅凭 CLI 在 PATH 中就视为可用。每个 Segment 使用产品原图和达人图，参考图去重并保持顺序。同一条视频的 Segment 按编号顺序生成；每条视频锁定同一 provider，保存 task ID、片段及状态。无法确定是否已提交时停止，待核对原任务。

用 `scripts/batch_control.py` 最多同时运行 **3 条完整视频工作流**；同一条视频内不并发 Segment。保留部分成功结果。多段使用 `scripts/merge_video.py` 拼为 `final_video.mp4`，不得跨视频拼接；批量输出到 `video_01/` 等目录。结果列出实际渠道、生成文件、可查询的消费与剩余积分；无法核算时明确写“无法核算／无法查询”。未经观看或检测的成片标记为待复核，不声称画面或口播已通过检查。
