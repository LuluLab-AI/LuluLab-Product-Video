# LuluLab Node.js API 适配

依据用户附件 `v1 (2).json`（OpenAPI 3.1.1，Customer Service v1）。默认生产服务 `https://customer.lululab.ai`；测试服务 `https://customer.test.lululab.ai` 需显式配置 `LULULAB_API_BASE_URL`。Node.js ≥20，无 npm 依赖。图片与视频编排、质量门禁仍由现有 Python 脚本负责，所有 LuluLab 网络请求由 `scripts/lululab_cli.mjs` 负责。

| CLI 命令 | API | 处理 |
|---|---|---|
| `upload <file>` | `POST /uploads` | 获取 `presignedUrl`、`location`、`mimeType`；按服务端允许的方法及 Content-Type 向预签名地址发送文件字节，不传 LuluLab Authorization；完成后返回 `{url: location, mimeType}`，其中 PNG/JPEG/GIF/WebP 的媒体 mimeType 由文件头识别，不能沿用存储接口的通用二进制类型；未识别的格式保留接口返回值 |
| `task submit --workflow-id <id> --input <JSON>` | `POST /tasks` | 请求体 `{workflowId, input}`；返回 `WorkflowTaskModel`，记录 `id` |
| `task fetch --id <id>` | `GET /tasks/{id}` | 原任务状态与 `output`；成功下载只读取 output，避免误用 input 里的参考图地址 |
| `user --credits` | `GET /credits?page=N&pageSize=100` | 按 `total/items` 分页，汇总全部账户 `creditsBalance`，输出 `{balance}`；支持整数或字符串，拒绝精度溢出 |

鉴权使用 API 文档的 `UserKey`：`Authorization: <原始 API Key>`。优先 `LULULAB_API_KEY`，兼容旧环境变量 `LINGZHI_API_KEY`、`LZSTUDIO_API_KEY` 与 `~/.ugc-product-video/config.json` 的 `apiKey`。不把凭证写入参数、任务文件、回复或日志。检测命令帮助不读取凭证，不访问接口。

`VideoGenV2` workflow ID、逻辑模型 ID 与工作流 input 字段保持原协议；附件定义任务外层 envelope，未定义 VideoGenV2 内部 schema。预签名上传使用 PUT 是标准存储上传约定的实现假设：附件没有指定存储上传的 HTTP 方法，若实际服务要求不同方法，需按服务方说明修正；不通过付费请求验证。`PresignedUploadModel.expiresAt` 仅说明上传链接有效期，不能当成最终媒体有效期。

任务状态包括 Created、Pending、Running、Succeeded、Failed、Cancelled；Python 轮询忽略大小写。提交没有自动重试；网络超时或响应异常保留现有 `submit_started_uncertain` 状态，禁止自动重复计费。服务 API 与预签名上传均禁止自动跳转；LuluLab 凭证只发送到选定 API 服务，不发送到存储地址。只允许本地开发服务使用 HTTP，外部地址使用 HTTPS。

调用示例：

```sh
node scripts/lululab_cli.mjs --help
python3 scripts/video_cli.py preflight --model seedance-2-fast
# 只有用户授权视频生成后才运行计费入口：
python3 scripts/local_video_generate.py --job request-job.json --provider lululab_cli --generation-approved
```

## 达人参考图 ImageGenV2

`local_creator_image_generate.py` 先查询积分，再逐张调用 `upload` 上传用户产品图。图片任务的 `input` 默认使用 `model: gpt-image-2-5-sunburst`、`prompt`、`resolution: 1K`、`aspectRatio: 9:16`、`referenceImages`。明确传入受支持的 `--image-model gpt-image-2-5-flare` 时，状态记录与实际提交均使用 Flare。上传结果只把 `url` 和 `mimeType` 带入生成请求，上传链接的 `expiresAt` 不是媒体的 `expiredAt`。

图片任务在产品图上传成功后、计费提交前保存 `submit_started_uncertain`；拿到 task ID 后保存 `submitted`，后续只查询该 ID。成功结果必须从 `output.image.url` 下载为 PNG，并验证 PNG 文件头。无 task ID 的不确定提交不自动重试。默认不调用其他生图平台。

预签名上传默认使用 PUT；若服务端返回 HTTP 405 且 `Allow` 明确包含 POST，则对同一预签名地址改用 POST 发送原始文件字节；若服务端随后返回 415，再用 multipart/form-data 的 `file` 字段提交，不携带 LuluLab Authorization。
