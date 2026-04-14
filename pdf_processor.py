from __future__ import annotations
import base64
import json
import re
import logging
import os
from typing import List, Dict, Optional, Any
import httpx
import fitz  # PyMuPDF

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 日志文件
LOG_FILE = os.path.join(os.path.dirname(__file__), "debug.log")
if not any(
    isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", None) == os.path.abspath(LOG_FILE)
    for h in logger.handlers
):
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(file_handler)


PROMPT_CBC = """你是一个医疗报告数据提取助手。请仔细阅读这张血常规检验报告图片，提取所有检验指标数据。

请严格按照以下 JSON 格式输出，不要输出任何其他内容：
{
  "date": "报告日期，格式 YYYY-MM-DD，如果无法识别则填 null",
  "items": [
    {
      "name": "指标名称",
      "value": 数值(浮点数),
      "unit": "单位",
      "ref_low": 参考范围下限(浮点数，无则null),
      "ref_high": 参考范围上限(浮点数，无则null)
    }
  ]
}

注意：
1. value 必须是数字，不要包含单位
2. 如果指标有箭头标记（↑↓），仍然只提取数值
3. 尽可能提取报告中所有指标
4. 日期优先从报告头部或标题区域识别"""


PROMPT_BM_SMEAR = """你是血液科医疗报告结构化助手。请阅读这份“骨髓涂片/骨髓形态学/骨髓细胞学”报告图片，提取白血病随访最关键字段。

请严格输出 JSON（不要输出任何其他内容）：
{
  "date": "报告日期 YYYY-MM-DD，不确定则 null",
  "facts": [
    {"section":"bone_marrow","key":"结论","value_text":"例如 CR/未缓解/疑复发/骨髓抑制期/可疑","value_num":null,"unit":null,"ref_low":null,"ref_high":null},
    {"section":"bone_marrow","key":"原始细胞比例","value_text":null,"value_num": 12.3,"unit":"%","ref_low":null,"ref_high":null},
    {"section":"bone_marrow","key":"标本质量","value_text":"例如 可评估/稀释/干抽/不满意","value_num":null,"unit":null,"ref_low":null,"ref_high":null},
    {"section":"bone_marrow","key":"备注","value_text":"提取最关键一句描述（如见幼稚细胞/疑异常增生等）","value_num":null,"unit":null,"ref_low":null,"ref_high":null}
  ]
}

要求：
1) 优先提取“原始细胞(Blast)%/幼稚细胞%”的明确数值
2) 没有数值就填 null，不要编造
3) value_num 只能是数字"""


PROMPT_LP = """你是血液科医疗报告结构化助手。请阅读这份“腰穿/脑脊液(CSF)/鞘注”相关报告图片，提取关键字段。

严格输出 JSON：
{
  "date": "报告日期 YYYY-MM-DD，不确定则 null",
  "facts": [
    {"section":"lp","key":"结论","value_text":"例如 CNS1/CNS2/CNS3/阴性/阳性/可疑","value_num":null,"unit":null,"ref_low":null,"ref_high":null},
    {"section":"lp","key":"CSF白细胞","value_text":null,"value_num": 5.0,"unit":"10^6/L","ref_low":null,"ref_high":null},
    {"section":"lp","key":"CSF红细胞","value_text":null,"value_num": 0.0,"unit":"10^6/L","ref_low":null,"ref_high":null},
    {"section":"lp","key":"是否见幼稚细胞","value_text":"是/否/未提及","value_num":null,"unit":null,"ref_low":null,"ref_high":null},
    {"section":"lp","key":"备注","value_text":"提取一条最关键描述","value_num":null,"unit":null,"ref_low":null,"ref_high":null}
  ]
}
要求：value_num 必须为数字；无法识别填 null。"""


PROMPT_FLOW = """你是血液科医疗报告结构化助手。请阅读这份“流式细胞检测/免疫分型/MRD”报告图片，提取随访关键字段。

严格输出 JSON：
{
  "date": "报告日期 YYYY-MM-DD，不确定则 null",
  "facts": [
    {"section":"flow","key":"用途","value_text":"诊断/复查MRD/不确定","value_num":null,"unit":null,"ref_low":null,"ref_high":null},
    {"section":"flow","key":"MRD","value_text":null,"value_num": 0.0123,"unit":"%","ref_low":null,"ref_high":null},
    {"section":"flow","key":"阈值","value_text":null,"value_num": 0.01,"unit":"%","ref_low":null,"ref_high":null},
    {"section":"flow","key":"结论","value_text":"MRD阴性/MRD阳性/可疑/未提及","value_num":null,"unit":null,"ref_low":null,"ref_high":null},
    {"section":"flow","key":"关键表型","value_text":"提取最关键 marker（用逗号分隔，如 CD34+,CD117+,MPO+）","value_num":null,"unit":null,"ref_low":null,"ref_high":null}
  ]
}
要求：MRD 若报告提供定量则填 value_num；否则填 null。"""


PROMPT_MOLECULAR = """你是血液科医疗报告结构化助手。请阅读这份“分子监测/WT1/iGH重排/融合基因定量”等报告图片，提取关键字段。

严格输出 JSON：
{
  "date": "报告日期 YYYY-MM-DD，不确定则 null",
  "facts": [
    {"section":"molecular","key":"项目","value_text":"例如 WT1 / iGH重排 / 融合基因 / 其他","value_num":null,"unit":null,"ref_low":null,"ref_high":null},
    {"section":"molecular","key":"结果","value_text":"例如 阴性/阳性/未检出/检出/可疑/数值见下","value_num":null,"unit":null,"ref_low":null,"ref_high":null},
    {"section":"molecular","key":"数值","value_text":null,"value_num": null,"unit":"如 % 或 copies 或 其他","ref_low":null,"ref_high":null},
    {"section":"molecular","key":"备注","value_text":"提取最关键一句（如检测方法/灵敏度/LOD）","value_num":null,"unit":null,"ref_low":null,"ref_high":null}
  ]
}
要求：如果报告明确给出 WT1 或 iGH 的定量，填写到 key=数值 的 value_num 与 unit；否则置 null。"""


PROMPT_CT_CHEST = """你是医疗报告结构化助手。请阅读这份“胸部CT/影像学”报告图片，提取随访关键结论。

严格输出 JSON：
{
  "date": "报告日期 YYYY-MM-DD，不确定则 null",
  "facts": [
    {"section":"imaging","key":"检查部位","value_text":"胸部CT","value_num":null,"unit":null,"ref_low":null,"ref_high":null},
    {"section":"imaging","key":"印象","value_text":"提取放射科 Impression/结论一段（尽量完整但精简）","value_num":null,"unit":null,"ref_low":null,"ref_high":null},
    {"section":"imaging","key":"关键阳性","value_text":"用逗号列出关键阳性：实变/磨玻璃影/结节/空洞/胸腔积液/未见明显异常 等","value_num":null,"unit":null,"ref_low":null,"ref_high":null}
  ]
}"""


def _get_prompt(report_type: str) -> str:
    rt = (report_type or "").strip().lower()
    if rt in ("cbc", "liver", "kidney", "electrolyte"):
        # 这几类都是“化验数值表”，暂时复用 items schema（后续可做更精细的分组展示）
        return PROMPT_CBC
    if rt in ("bm_smear", "bone_marrow"):
        return PROMPT_BM_SMEAR
    if rt in ("lp", "lumbar_puncture"):
        return PROMPT_LP
    if rt in ("flow", "mrd"):
        return PROMPT_FLOW
    if rt in ("molecular", "wt1", "igh", "ngs", "fusion"):
        return PROMPT_MOLECULAR
    if rt in ("ct_chest", "ct", "imaging"):
        return PROMPT_CT_CHEST
    return PROMPT_CBC

ZHIPU_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


def pdf_to_images_base64(pdf_bytes: bytes) -> List[str]:
    """将 PDF 每一页转为 base64 编码的 PNG 图片"""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []
    for page in doc:
        pix = page.get_pixmap(dpi=200)
        img_bytes = pix.tobytes("png")
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        images.append(b64)
    doc.close()
    return images


def extract_json_from_text(text: str) -> str:
    """从文本中提取 JSON 对象"""
    def _extract_first_balanced_json_object(raw: str) -> Optional[str]:
        start = raw.find("{")
        if start == -1:
            return None

        in_string = False
        escape = False
        depth = 0
        for i in range(start, len(raw)):
            ch = raw[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
                continue

            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return raw[start : i + 1]

        return None

    # 方法1: 提取 markdown 代码块中的 JSON
    if "```json" in text:
        match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
        if match:
            return match.group(1).strip()

    if "```" in text:
        match = re.search(r'```\s*([\s\S]*?)\s*```', text)
        if match:
            return match.group(1).strip()

    # 方法2: 查找 { } 包裹的 JSON 对象
    balanced = _extract_first_balanced_json_object(text)
    if balanced:
        return balanced

    # 兜底：找到第一个 { 和最后一个 }（可能不完整）
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    return text


def fix_json(text: str) -> str:
    """尝试修复常见的 JSON 格式问题"""
    # 移除尾随逗号 (如 ", }" 或 ", ]")
    text = re.sub(r',\s*}', '}', text)
    text = re.sub(r',\s*]', ']', text)
    # 移除注释
    text = re.sub(r'//.*', '', text)
    text = re.sub(r'/\*[\s\S]*?\*/', '', text)

    # 尝试补全被截断的结尾括号/方括号（只在不在字符串内时统计）
    in_string = False
    escape = False
    stack: List[str] = []
    for ch in text:
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue

        if ch == "{":
            stack.append("}")
        elif ch == "[":
            stack.append("]")
        elif ch == "}" and stack and stack[-1] == "}":
            stack.pop()
        elif ch == "]" and stack and stack[-1] == "]":
            stack.pop()

    if stack:
        text = text.rstrip() + "".join(reversed(stack))

    return text


def extract_report_data(
    pdf_bytes: bytes,
    api_key: str,
    report_type: str = "cbc",
    *,
    llm: Optional[Dict[str, Any]] = None,
) -> Dict:
    """
    从 PDF 中提取报告数据（按 report_type 选择抽取 schema）
    返回: {"date": "YYYY-MM-DD", "items": [...] } 或 {"date": "...", "facts": [...]}
    """
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            page_count = doc.page_count
    except Exception:
        page_count = None

    logger.info("开始处理 PDF，页数: %s", page_count if page_count is not None else "未知")

    images = pdf_to_images_base64(pdf_bytes)
    logger.info("PDF 转图片完成，共 %d 页", len(images))

    prompt = _get_prompt(report_type)
    content = [{"type": "text", "text": prompt}]
    for img_b64 in images:
        content.append({
            "type": "image_url",
            "image_url": {"url": "data:image/png;base64,{}".format(img_b64)}
        })

    cfg = llm or {}
    api_url = (cfg.get("api_base_url") or "").strip() or ZHIPU_API_URL
    model_name = (cfg.get("model") or "").strip() or "glm-4v-flash"
    temp = cfg.get("temperature")
    if temp is None:
        temp_f = 0.1
    else:
        try:
            temp_f = float(temp)
        except (TypeError, ValueError):
            temp_f = 0.1

    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": content}],
        "temperature": temp_f,
    }

    headers = {
        "Authorization": "Bearer {}".format(api_key),
        "Content-Type": "application/json",
    }

    logger.info("调用视觉模型 API: %s model=%s", api_url, model_name)
    resp = httpx.post(api_url, json=payload, headers=headers, timeout=120)
    logger.info("API 响应状态: %d", resp.status_code)

    if resp.status_code != 200:
        logger.error("API 调用失败: %s", resp.text)
        raise Exception("API 调用失败: {}".format(resp.status_code))

    data = resp.json()
    text = data["choices"][0]["message"]["content"].strip()

    # 记录原始返回内容
    logger.info("===== GLM 原始返回 =====")
    logger.info(text)
    logger.info("========================")

    # 提取 JSON
    json_str = extract_json_from_text(text)
    logger.info("提取的 JSON: %s", json_str[:500] if len(json_str) > 500 else json_str)

    # 尝试修复 JSON
    json_str = fix_json(json_str)

    try:
        result = json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error("JSON 解析失败: %s", str(e))
        logger.error("尝试解析的内容: %s", json_str)
        raise Exception("JSON 解析失败: {}".format(str(e)))

    # 确保数值类型正确（items / facts）
    for item in result.get("items", []):
        if item.get("value") is not None:
            try:
                item["value"] = float(item["value"])
            except (ValueError, TypeError):
                item["value"] = None
        if item.get("ref_low") is not None:
            try:
                item["ref_low"] = float(item["ref_low"])
            except (ValueError, TypeError):
                item["ref_low"] = None
        if item.get("ref_high") is not None:
            try:
                item["ref_high"] = float(item["ref_high"])
            except (ValueError, TypeError):
                item["ref_high"] = None

    for f in result.get("facts", []):
        for k in ("value_num", "ref_low", "ref_high"):
            if f.get(k) is not None:
                try:
                    f[k] = float(f[k])
                except (ValueError, TypeError):
                    f[k] = None

    logger.info(
        "解析成功：items=%d, facts=%d",
        len(result.get("items", [])),
        len(result.get("facts", [])),
    )
    return result


# 兼容旧函数名（v1.1/v1.2 调用）
def extract_blood_test_data(pdf_bytes: bytes, api_key: str) -> Dict:
    return extract_report_data(pdf_bytes, api_key, report_type="cbc")
