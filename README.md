# 检验随访工作台（血液肿瘤随访）

利用大模型（智谱 GLM-4V）识别各类检查 PDF，自动提取结构化数据，并以**时间轴卡片 + 趋势图 + 表格**的形式展示，便于白血病等血液肿瘤病人的长期随访。

## 功能特性

- **多病人管理**：支持创建/切换病人，所有记录按病人隔离展示
- **多类型报告**：支持“主要检查 / 日常检查 / 其他检查”的统一上传与展示
- **主要检查（时间轴卡片）**：骨穿/腰穿/流式/MRD、分子监测（WT1/iGH 等）、胸部 CT 等以“结论卡片”展示
- **日常检查（趋势图 + 表格）**：血常规、肝功能、肾功能、电解质等以“趋势图+可选列表格”展示
- **异常提示**：超出参考范围的数值自动标红（趋势图点位也会标红），参考范围以背景带显示
- **数据持久化**：SQLite 本地存储，无需额外数据库

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端框架 | FastAPI (Python) |
| PDF 处理 | PyMuPDF (fitz) |
| 大模型 | 智谱 GLM-4V-Flash（视觉模型） |
| 前端 | HTML + JavaScript + ECharts |
| 数据库 | SQLite |

## 项目结构

```
blood-test-analyzer/
├── app.py              # FastAPI 主应用，API 路由
├── pdf_processor.py    # PDF 转图片 + GLM API 调用（按 report_type 多 schema 抽取）
├── database.py         # SQLite 数据库操作
├── requirements.txt    # Python 依赖
├── .env                # 环境变量（API Key，本地使用，不要提交到仓库）
├── .env.example        # 环境变量模板
├── debug.log           # 调试日志（运行时生成）
├── .gitignore          # 忽略 .env / data / debug.log 等
├── static/
│   └── index.html      # 前端单页应用
└── data/
    └── blood_test.db   # SQLite 数据库（运行时生成）
```

## 安装部署

### 环境要求

- Python 3.8+（推荐 3.10+）
- 智谱 AI API Key（[获取地址](https://open.bigmodel.cn/)）

### 安装步骤

```bash
# 1. 进入项目目录
cd blood-test-analyzer

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 API Key
copy .env.example .env
# 编辑 .env 文件，填入你的智谱 API Key：
# ZHIPUAI_API_KEY=your_api_key_here

# 注意：请勿将 .env 提交到仓库（已在 .gitignore 中忽略）

# 4. 启动服务
python -m uvicorn app:app --reload --port 8000

# 5. 打开浏览器访问
# http://localhost:8000
```

## 使用说明

### 上传报告

1. 打开网页 `http://localhost:8000`
2. 先在右上角选择（或新建）病人
3. 选择「报告类型」（骨穿/腰穿/流式/MRD、WT1/iGH/NGS、血常规、肝肾电解质、胸部CT等）
4. 拖拽或点击上传对应的 PDF 报告
4. 等待 AI 解析（约 10-30 秒）
5. 解析成功后自动显示提取的指标，并写入该病人的历史记录

### 页面结构（按三大类）

- **主要检查**：骨穿/腰穿/流式/MRD、分子监测（WT1/iGH等）用“时间轴卡片”展示关键结论与数值
- **日常检查**：血常规/肝功能/肾功能/电解质用“趋势图 + 表格”展示
- **其他检查**：胸部 CT 等影像用“时间轴卡片”展示影像印象与关键阳性

### 查看趋势图（仅日常检查）

1. 上传多份不同日期的日常化验报告（血常规/肝功/肾功/电解质）
2. 在「日常检查」页右上角切换类型
3. 点击指标按钮选择要查看的指标（每个指标一张独立折线图）
4. 红色标记表示异常值（超出参考范围）

#### 默认展示的指标（可在页面中改选）

默认会优先展示以下 4 个指标（若数据中存在才会自动选中）：

- 白细胞
- 中性粒细胞绝对值（NEUT#）
- 血小板
- 红细胞

### 管理报告

- 报告列表以表格形式显示所有已上传的报告
- 点击「删除」可移除某次报告

#### 报告表格的默认列

报告表格默认列会跟“趋势图默认指标”保持一致（白细胞 / 中性粒细胞绝对值 / 血小板 / 红细胞），并支持在页面勾选要显示哪些指标列。

## API 接口

### 上传 PDF

```
POST /api/upload
Content-Type: multipart/form-data

参数：
- file: PDF 文件
- patient_id: 病人 ID（可选；不传则会归到默认病人“刘晨曦”）
- report_type: 报告类型（必传/推荐）

响应：
{
  "report_id": 1,
  "date": "2024-01-15",
  "item_count": 20,
  "fact_count": 0,
  "items": [...]
  "facts": [...]
}
```

### 获取病人列表

```
GET /api/patients
```

### 创建病人

```
POST /api/patients
Content-Type: multipart/form-data

参数：
- name: 姓名（必填）
- sex: 性别（可选）
- birthday: 出生日期（可选）
```

### 获取报告列表

```
GET /api/reports?patient_id=1&report_type=cbc

响应：
[
  {
    "id": 1,
    "patient_id": 1,
    "report_type": "cbc",
    "filename": "report.pdf",
    "report_date": "2024-01-15",
    "created_at": "2024-01-15T10:30:00",
    "items": [...]
  }
]
```

### 获取报告详情（含结构化 facts）

```
GET /api/reports/{report_id}
```

### 获取图表数据

```
GET /api/chart-data?patient_id=1&report_type=cbc

响应：
{
  "白细胞": {
    "unit": "10^9/L",
    "ref_low": 3.5,
    "ref_high": 9.5,
    "data": [
      {"date": "2024-01-01", "value": 5.2},
      {"date": "2024-01-15", "value": 6.1}
    ]
  }
}
```

### 获取时间轴数据（主要/其他检查）

```
GET /api/timeline?patient_id=1&report_type=bm_smear

响应：
[
  {
    "id": 12,
    "patient_id": 1,
    "report_type": "bm_smear",
    "filename": "...pdf",
    "report_date": "2026-04-13",
    "created_at": "...",
    "facts": [
      {"section":"bone_marrow","key":"结论","value_text":"CR",...}
    ]
  }
]
```

### 删除报告

```
DELETE /api/reports/{report_id}

响应：
{"ok": true}
```

## 数据库结构

### patients 表（病人）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| name | TEXT | 姓名 |
| sex | TEXT | 性别 |
| birthday | DATE | 出生日期 |
| created_at | TIMESTAMP | 创建时间 |

### reports 表（报告）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| patient_id | INTEGER | 关联病人 ID |
| filename | TEXT | 原始文件名 |
| report_date | DATE | 报告日期 |
| report_type | TEXT | 报告类型（如 cbc / bm_smear / flow / ct_chest） |
| created_at | TIMESTAMP | 创建时间 |

### test_items 表（检验指标）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| report_id | INTEGER | 关联报告 ID |
| name | TEXT | 指标名称 |
| value | REAL | 检测值 |
| unit | TEXT | 单位 |
| ref_low | REAL | 参考范围下限 |
| ref_high | REAL | 参考范围上限 |

### report_facts 表（结构化结论/关键字段）

用于骨穿/腰穿/流式/MRD、分子监测（WT1/iGH 等）、影像（胸部CT）等“结论型报告”的结构化字段存储。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| report_id | INTEGER | 关联报告 ID |
| section | TEXT | 模块（bone_marrow / flow / imaging 等） |
| key | TEXT | 字段名（如 结论、MRD、印象） |
| value_text | TEXT | 文本值 |
| value_num | REAL | 数值（如 Blast%、MRD%、WT1 数值） |
| unit | TEXT | 单位 |
| ref_low | REAL | 参考下限（可选） |
| ref_high | REAL | 参考上限（可选） |

## 常见问题

### 1. PDF 解析失败

**原因**：GLM 返回的 JSON 可能包含多余文本、代码块，或偶发截断导致 JSON 不完整

**解决**：
- 查看 `debug.log` 日志文件
- 确保 PDF 清晰可读
- 尝试重新上传

> 说明：项目已增强了 JSON 提取/修复能力（尽量从返回文本中提取出完整 JSON，并在末尾缺少 `]`/`}` 时尝试补全），但遇到极端截断仍可能失败。

### 2. API Key 无效

**原因**：智谱 API Key 未配置或已过期

**解决**：
- 检查 `.env` 文件中的 `ZHIPUAI_API_KEY`
- 确认 API Key 有效且有余额
- 在智谱开放平台检查：https://open.bigmodel.cn/

### 3. 服务无法启动

**原因**：端口被占用或依赖未安装

**解决**：
```bash
# 检查端口占用
netstat -ano | findstr :8000

# 更换端口启动
python -m uvicorn app:app --port 8080

# 重新安装依赖
pip install -r requirements.txt --force-reinstall
```

### 4. Python 版本兼容

**要求**：Python 3.8+

**检查版本**：
```bash
python --version
```

如果版本过低，建议升级 Python 或使用 conda 创建新环境：
```bash
conda create -n blood-test python=3.10
conda activate blood-test
pip install -r requirements.txt
```

## 费用说明

本项目使用智谱 GLM-4V-Flash 模型：

- **免费额度**：智谱为新用户提供免费额度
- **按量计费**：约 0.001 元/次调用（以官方为准）
- **费用查询**：https://open.bigmodel.cn/usage

## 扩展开发

### 添加新的检验类型

修改 `pdf_processor.py` 中的 `PROMPT_*` 与 `_get_prompt(report_type)`，为新 `report_type` 定义抽取 schema：

- **化验类（items）**：输出 `{"date": "...", "items": [...]}` → 写入 `test_items`
- **结论类（facts）**：输出 `{"date": "...", "facts": [...]}` → 写入 `report_facts`

### 更换大模型

本项目目前默认使用智谱的 OpenAPI（`chat/completions` 风格）调用视觉模型做 PDF 结构化抽取。

#### 需要改哪些地方

主要集中在 `pdf_processor.py` 的 `extract_report_data()`：

- **API 地址**：`ZHIPU_API_URL`
- **模型名**：`payload["model"]`（当前为 `glm-4v-flash`）
- **鉴权方式**：`headers["Authorization"]`（当前为 `Bearer <API_KEY>`）
- **请求体格式**：
  - `messages[0].content` 由 `text + image_url(data:image/png;base64,...)` 组成
  - 如果换成别的厂商 API，通常需要把图片字段、role/content 的结构按其文档调整
- **响应解析**：当前取 `data["choices"][0]["message"]["content"]`，换 API 时需要同步修改

#### 更换智谱模型（同一 API 体系内）

仅需改 `payload["model"]`：

- `glm-4v`：更强视觉能力
- `glm-4v-flash`：更快速度，免费额度更多

#### 更换为其他大模型 / 其他 API（不同厂商）

建议做法：

1) 在 `pdf_processor.py` 中新增一个“适配器函数”（比如 `call_llm_api(prompt, images, api_key)`），把**HTTP 调用与响应解析**集中封装  
2) 保持 `extract_report_data()` 输出结构不变：
   - **化验类**：`{"date": "...", "items": [...]}`（写入 `test_items`）
   - **结论类**：`{"date": "...", "facts": [...]}`（写入 `report_facts`）

这样后端/前端/数据库不需要跟着厂商 API 改动。

#### API Key 配置方式

目前后端从环境变量读取：

- `.env`：`ZHIPUAI_API_KEY=...`（不要提交）
- `app.py`：`API_KEY = os.getenv("ZHIPUAI_API_KEY")`

如果你改成其他厂商，建议把变量名改为通用的（例如 `LLM_API_KEY`、`LLM_API_URL`），并同步更新 `.env.example` 与 `README`。

### 自定义图表样式

修改 `static/index.html` 中的 ECharts 配置项，调整图表颜色、样式等。

## 更新记录（本次改动汇总）

- **安全**：
  - 新增 `.gitignore`，默认忽略 `.env`、`data/`、`debug.log` 等，避免提交密钥/数据库/日志。
  - `README` 明确提示 `.env` 仅本地使用。
- **日志**：
  - `pdf_processor.py` 的日志文件改为项目目录下的 `debug.log`（跨平台），并避免 `--reload` 时重复添加 handler。
  - 修复“页数”日志输出：改为读取 PDF 的实际 `page_count`。
- **解析稳定性**：
  - 增强 GLM 返回内容的 JSON 提取与修复：支持从混杂文本/代码块中提取 JSON，并在输出被截断时尝试补齐括号后解析。
- **指标名称规范化**：
  - 后端对指标名做基础规范化（例如 `白细胞-WBC` 归一为 `白细胞`），便于趋势图与表格聚合展示。
- **前端展示**：
  - 报告记录改为“表格 + 列选择”，默认列与趋势图默认指标保持一致。
  - 趋势图改为“每个指标单独一张折线图”，默认优先展示：白细胞 / 中性粒细胞绝对值（NEUT#）/ 血小板 / 红细胞。
  - 新增“主要/日常/其他”三大标签页：主要/其他用时间轴卡片，日常用趋势图+表格。

## 许可证

MIT License

## 联系方式

如有问题或建议，请提交 Issue。
