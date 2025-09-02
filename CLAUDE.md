# Prompt

你是一名资深后端工程师。请 **从零生成** 一个可直接运行的 **FastAPI + Celery** 技术栈项目，面向 GPU 推理的“长任务/批处理”服务。项目需具备：API 网关（FastAPI）、任务队列（Celery + RabbitMQ/Redis）、一进程一 GPU 的 worker、S3 结果存储、可观测性（Prometheus 指标 + 结构化日志）、重试与优先级队列、幂等、API Key 鉴权、基础单元测试，以及 Docker 本地一键启动与 .env 模板。请一次性输出**全部源码文件**（按文件名分块），做到**开箱即用**。

---

## 功能与要求

1. **核心流程**

   * `POST /v1/tasks`：提交任务（含模型名、输入参数、优先级 `high|normal|low`、可选回调 `callback_url`）。返回 `task_id`。
   * `GET /v1/tasks/{task_id}`：查询状态 `PENDING|STARTED|RETRY|SUCCESS|FAILURE`，若完成，返回结果元信息（S3 key、耗时统计）。
   * 任务执行示例：以“图像放大/超分”或“图像打分”为例：读取输入（URL 或 base64），模拟 GPU 推理（可用 PyTorch 张量与 sleep 模拟），将结果文件写入 MinIO (S3 兼容)，记录分段耗时（下载/推理/上传）。
   * Worker **一进程一卡**：通过 `CUDA_VISIBLE_DEVICES` 绑定；进程启动时“加载模型”，任务处理时复用常驻模型。

2. **可靠性**

   * Celery 任务：`acks_late=True`、`task_reject_on_worker_lost=True`、`autoretry_for=(Exception,)`、指数退避、最大重试次数可配。
   * **幂等性**：对相同 `client_request_id` 或请求签名去重；重复提交返回同一 `task_id`。
   * **优先级队列**：`gpu-high`、`gpu-normal`、`gpu-low` 三个队列，任务按优先级路由。

3. **鉴权与配额**

   * API Key 鉴权（HTTP Header: `x-api-key`），支持多 key。
   * 简单速率限制（每 key 每分钟 N 次，内存或 Redis）。

4. **可观测性**

   * **Prometheus 指标**：`/metrics`，包含请求数、P99 时延、任务成功/失败数、各阶段耗时直方图。
   * 结构化 JSON 日志，包含 `task_id`、阶段耗时、GPU id、模型名。

5. **存储**

   * 结果写入 MinIO(S3 兼容)，配置项：`S3_ENDPOINT/S3_ACCESS_KEY/S3_SECRET_KEY/S3_BUCKET`。开发模式写 `./data/`。
   * Celery result backend 使用 Redis。

6. **配置与运行**

   * `.env.example`：含 Broker、Redis、S3、API\_KEY、速率限制阈值、可选 `GPU_IDS`。
   * **Dockerfile**（API 与 worker）+ **docker-compose.yml**（fastapi、rabbitmq、redis、minio、prometheus、grafana、workers、flower）。
   * `Makefile`：`make up/down/logs/test/lint/format`.

7. **代码质量**

   * 类型标注、pydantic 校验、OpenAPI 文档、错误处理（422/401/429/5xx）。
   * 单元测试（pytest）：提交/查询流 + 幂等 + 简易速率限制。
   * 读取 `.env`，区分 `DEV/PROD`。

---

## 关键设计：遵循开闭原则 (OCP)

* **模型推理部分必须抽象为接口/基类**，例如 `BaseModelRunner`，定义统一方法：

  * `prepare(input) -> Tensor`
  * `infer(tensor) -> Tensor`
  * `postprocess(output) -> dict`
* 不同模型（如 `SuperResolutionRunner`, `ImageScoringRunner`）实现该接口，放在 `app/models/runners/`。
* Worker **不直接写死调用某个模型**，而是通过 **工厂类或注册表**（`ModelRegistry`）根据 `model_name` 动态加载对应 Runner。
* **新增模型时只需新增一个类并注册**，无需修改主流程代码（体现开闭原则）。
* 至少实现：

  * `SuperResolutionRunner`（占位：sleep + 随机输出图像大小）
  * `ImageScoringRunner`（占位：返回分数）

---

## 项目结构

```
.
├─ app/
│  ├─ main.py                # FastAPI 入口
│  ├─ deps/auth.py           # API Key 校验
│  ├─ deps/ratelimit.py      # 速率限制
│  ├─ models/
│  │   ├─ base.py            # BaseModelRunner 抽象类
│  │   ├─ registry.py        # ModelRegistry
│  │   └─ runners/
│  │        ├─ superres.py   # SuperResolutionRunner
│  │        └─ scoring.py    # ImageScoringRunner
│  ├─ services/storage.py    # S3/本地存取
│  ├─ services/metrics.py    # Prometheus 指标
│  ├─ tasks/celery_app.py    # Celery 初始化
│  ├─ tasks/gpu_worker.py    # Worker 任务逻辑（通过 ModelRegistry 调度）
│  ├─ utils/idempotency.py   # 幂等缓存
│  └─ utils/timing.py        # 分段耗时统计
├─ tests/
│  └─ test_task_flow.py
├─ Dockerfile.api
├─ Dockerfile.worker
├─ docker-compose.yml
├─ prometheus.yml
├─ grafana/
├─ flower/
├─ requirements.txt
├─ Makefile
├─ .env.example
└─ README.md
```

---

## 路由与示例

* **提交任务**

  ```
  POST /v1/tasks
  {
    "model": "superres-x4",
    "input": {"image_url": "https://example.com/a.jpg"},
    "priority": "high",
    "client_request_id": "abc-123",
    "callback_url": "https://client/cb"
  }
  ```

  响应：

  ```json
  {"task_id": "xxxx", "status": "PENDING"}
  ```

* **查询状态**

  ```
  GET /v1/tasks/{task_id}
  ```

  响应：

  ```json
  {
    "task_id":"xxxx",
    "status":"SUCCESS",
    "timing":{"prepare_ms":120,"infer_ms":850,"upload_ms":60},
    "result":{"s3_key":"results/xxxx.png","size":[2048,2048]}
  }
  ```

---

## 运行说明（README 中需包含）

* `cp .env.example .env`
* `make up` 或 `docker compose up -d --build`
* `curl -H "x-api-key: <KEY>" -X POST http://localhost:8000/v1/tasks -d '<payload>'`
* 打开：

  * API 文档 `http://localhost:8000/docs`
  * 指标 `http://localhost:8000/metrics`
  * Flower `http://localhost:5555`
  * MinIO 控制台
  * Grafana dashboard

---

## 验收标准

* 完整源码（分文件输出）
* README 清晰说明
* `.env.example`、`docker-compose.yml`、`prometheus.yml`、`Makefile`
* 单元测试覆盖两个 Runner（超分、评分），验证可插拔性

---

请严格遵循以上规范，特别是 **开闭原则 (OCP)**，将模型推理部分设计为易于替换与扩展的方式。

