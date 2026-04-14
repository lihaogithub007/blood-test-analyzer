from datetime import datetime
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Query, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from pathlib import Path
from pydantic import BaseModel, Field

from database import (
    init_db,
    save_report,
    get_all_reports,
    get_chart_data,
    delete_report,
    get_report_detail,
    get_reports_with_facts,
    save_report_facts,
    list_patients,
    create_patient,
    ensure_default_patient,
    save_llm_settings_patch,
)
from pdf_processor import extract_report_data
from settings import get_effective_llm_config, get_llm_settings_for_api, get_admin_password

load_dotenv()

app = FastAPI(title="血常规 PDF 分析器")

# 初始化数据库
init_db()

STATIC_DIR = Path(__file__).resolve().parent / "static"


class LLMSettingsUpdate(BaseModel):
    """部分更新：未包含的字段保持不变；api_key 传空字符串表示清除已保存的密钥。"""

    api_key: Optional[str] = Field(default=None, description="新密钥；省略则不修改；空字符串清除库内密钥")
    api_base_url: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None


@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/patients")
async def get_patients():
    # 确保默认病人存在，避免前端初次打开没有可选项
    ensure_default_patient()
    return list_patients()


@app.post("/api/patients")
async def add_patient(
    name: str = Form(...),
    sex: Optional[str] = Form(None),
    birthday: Optional[str] = Form(None),
):
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="病人姓名不能为空")
    pid = create_patient(name.strip(), sex=sex, birthday=birthday)
    return {"id": pid}


@app.post("/api/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    patient_id: Optional[int] = Form(None),
    report_type: str = Form("cbc"),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="请上传 PDF 文件")

    llm = get_effective_llm_config()
    if not llm.get("api_key"):
        raise HTTPException(
            status_code=500,
            detail="未配置 API Key：请在「模型配置」中填写，或设置环境变量 ZHIPUAI_API_KEY",
        )

    pdf_bytes = await file.read()

    try:
        result = extract_report_data(pdf_bytes, llm["api_key"], report_type=report_type, llm=llm)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF 解析失败: {str(e)}")

    report_date = result.get("date") or datetime.now().strftime("%Y-%m-%d")
    items = result.get("items", [])
    facts = result.get("facts", [])

    if not items and not facts:
        raise HTTPException(status_code=400, detail="未能从 PDF 中提取到可用数据")

    report_id = save_report(file.filename, report_date, items, patient_id=patient_id, report_type=report_type)
    if facts:
        save_report_facts(report_id, facts)

    return {
        "report_id": report_id,
        "date": report_date,
        "item_count": len(items),
        "fact_count": len(facts),
        "items": items,
        "facts": facts,
    }


@app.get("/api/reports")
async def list_reports(
    patient_id: Optional[int] = Query(None),
    report_type: Optional[str] = Query(None),
):
    reports = get_all_reports(patient_id=patient_id, report_type=report_type)
    for r in reports:
        detail = get_report_detail(r["id"])
        r["items"] = detail["items"] if detail else []
    return reports


@app.get("/api/chart-data")
async def chart_data(
    patient_id: Optional[int] = Query(None),
    report_type: Optional[str] = Query(None),
):
    return get_chart_data(patient_id=patient_id, report_type=report_type)


@app.get("/api/reports/{report_id}")
async def report_detail(report_id: int):
    detail = get_report_detail(report_id)
    if not detail:
        raise HTTPException(status_code=404, detail="报告不存在")
    return detail


@app.get("/api/timeline")
async def timeline(
    patient_id: Optional[int] = Query(None),
    report_type: Optional[str] = Query(None),
):
    return get_reports_with_facts(patient_id=patient_id, report_type=report_type)


@app.delete("/api/reports/{report_id}")
async def remove_report(report_id: int):
    if not delete_report(report_id):
        raise HTTPException(status_code=404, detail="报告不存在")
    return {"ok": True}


@app.get("/api/settings/llm")
async def get_llm_settings():
    """返回当前生效的大模型连接参数（不含 API Key 明文）。"""
    return get_llm_settings_for_api()


@app.put("/api/settings/llm")
async def put_llm_settings(
    body: LLMSettingsUpdate,
    x_admin_password: Optional[str] = Header(default=None, alias="X-Admin-Password"),
):
    admin_pw = get_admin_password()
    if not admin_pw:
        raise HTTPException(status_code=500, detail="未配置 ADMIN_PASSWORD，无法在页面修改模型配置")
    if (x_admin_password or "") != admin_pw:
        raise HTTPException(status_code=401, detail="管理员密码错误")
    patch = body.model_dump(exclude_unset=True)
    save_llm_settings_patch(patch)
    return get_llm_settings_for_api()


# 静态文件
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
