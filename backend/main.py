from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response
from pydantic import BaseModel

app = FastAPI(title="智枢农擎最小后端")
BASE_DIR = Path(__file__).resolve().parent.parent
ADMIN_DIR = BASE_DIR / "frontend" / "admin"
MINI_DIR = BASE_DIR / "frontend" / "mini"

Role = Literal["ADMIN", "OPERATOR", "FARMER", "PROVIDER"]
ClientType = Literal["PC", "MINI", "APP"]


class LoginRequest(BaseModel):
    username: str
    password: str
    client_type: ClientType = "PC"


class WechatLoginRequest(BaseModel):
    code: str


class ProviderOnboardSubmitRequest(BaseModel):
    real_name: str
    phone: str
    service_area: str
    credential_images: list[str] = []


class ProviderOnboardAuditRequest(BaseModel):
    action: Literal["APPROVE", "REJECT"]
    remark: str = ""


class ProviderApplySubmitRequest(BaseModel):
    providerName: str
    contactName: str
    contactPhone: str
    providerType: str
    regionCode: str | None = None
    address: str
    serviceTypes: list[str]
    serviceDescription: str = ""
    serviceArea: str = ""
    attachments: list[dict] = []


class ProviderApplyApproveRequest(BaseModel):
    applyId: int
    auditRemark: str = ""


class ProviderApplyRejectRequest(BaseModel):
    applyId: int
    rejectReason: str


class FileUploadRequest(BaseModel):
    fileName: str
    fileType: str
    fileSize: int = 0


class UserUpsertRequest(BaseModel):
    username: str
    password: str = "123456"
    role: str


class RoleUpsertRequest(BaseModel):
    code: str
    name: str


class AbilityUpsertRequest(BaseModel):
    id: int | None = None
    serviceType: str
    abilityName: str
    abilityDesc: str
    serviceArea: str
    regionCode: str = ""
    address: str = ""
    contactPhone: str = ""
    wechatNo: str = ""
    priceDesc: str = ""
    equipmentName: str = ""
    equipmentCount: int = 0
    dailyCapacity: str = ""
    availableStatus: str = "AVAILABLE"
    imageUrls: list[str] = []


class AbilitySwitchRequest(BaseModel):
    id: int


class ContactLogCreateRequest(BaseModel):
    providerId: int
    abilityId: int
    contactType: Literal["PHONE", "WECHAT"]
    sourcePage: str = "DETAIL"


USERS = {
    "admin": {"id": 1, "username": "admin", "password": "admin123", "role": "ADMIN"},
    "operator": {"id": 2, "username": "operator", "password": "op123", "role": "OPERATOR"},
    "gov": {"id": 3, "username": "gov", "password": "gov123", "role": "GOV_ADMIN"},
}
ROLE_LIST = [
    {"code": "ADMIN", "name": "系统管理员"},
    {"code": "OPERATOR", "name": "运营人员"},
    {"code": "FARMER", "name": "农户"},
    {"code": "PROVIDER", "name": "服务方"},
]
MENU_LIST = {
    "ADMIN": [
        {"path": "/dashboard", "name": "首页"},
        {"path": "/system/user", "name": "用户管理"},
        {"path": "/system/role", "name": "角色管理"},
        {"path": "/system/menu", "name": "菜单管理"},
        {"path": "/system/login-log", "name": "登录日志"},
        {"path": "/operate/provider-audit", "name": "服务方入驻审核"},
    ],
    "OPERATOR": [
        {"path": "/dashboard", "name": "首页"},
        {"path": "/system/login-log", "name": "登录日志"},
        {"path": "/operate/provider-audit", "name": "服务方入驻审核"},
    ],
    "FARMER": [
        {"path": "/mini/farmer-home", "name": "农户测试首页"},
        {"path": "/mini/farmer-index", "name": "找服务"},
    {"path": "/mini/farmer-demand-create", "name": "提交需求"},
    ],
    "PROVIDER": [
        {"path": "/mini/provider-home", "name": "服务方测试首页"},
        {"path": "/mini/provider-onboard", "name": "服务方入驻申请"},
        {"path": "/mini/provider-ability-list", "name": "服务能力管理"},
    {"path": "/mini/provider-demand-list", "name": "农户需求"},
    ],
}
MENU_LIST["ADMIN"] += [
    {"path": "/ops/service-ability", "name": "服务能力管理"},
    {"path": "/ops/contact-log", "name": "联系记录"},
    {"path": "/ops/demand", "name": "农户需求管理"},
    {"path": "/ops/service-record", "name": "服务记录管理"},
]
MENU_LIST["OPERATOR"] += [
    {"path": "/ops/service-ability", "name": "服务能力管理"},
    {"path": "/ops/contact-log", "name": "联系记录"},
    {"path": "/ops/demand", "name": "农户需求管理"},
    {"path": "/ops/service-record", "name": "服务记录管理"},
]

# 小程序测试用户映射：用 code 直接模拟绑定用户
WECHAT_CODE_USER = {
    "farmer-test-code": {"id": 101, "username": "farmer_01", "role": "FARMER", "openid": "openid_farmer_01"},
    "provider-test-code": {"id": 201, "username": "provider_01", "role": "PROVIDER", "openid": "openid_provider_01"},
}

# token -> 用户上下文（最小实现，内存态）
TOKENS: dict[str, dict] = {}

# 登录日志（最小实现，内存态）
LOGIN_LOGS: list[dict] = []
PROVIDER_ONBOARDS: list[dict] = []
PROVIDER_APPLIES: list[dict] = []
PROVIDERS: list[dict] = []
PROVIDER_AUDIT_LOGS: list[dict] = []
UPLOADED_FILES: dict[str, dict] = {}
SERVICE_CATEGORIES = [
    {"code": "AGRICULTURAL_MACHINERY", "name": "农机服务"},
    {"code": "SEEDLING", "name": "育秧服务"},
    {"code": "DRYING", "name": "烘干服务"},
    {"code": "STORAGE", "name": "仓储服务"},
    {"code": "PLANTING_GUIDE", "name": "种植指导"},
    {"code": "OTHER", "name": "其他服务"},
]
SERVICE_ABILITIES: list[dict] = []
SERVICE_CONTACT_LOGS: list[dict] = []


def _menus_by_role(role: str) -> list[dict]:
    return MENU_LIST.get(role, [])


def _create_token(user: dict, client_type: ClientType) -> str:
    token = uuid4().hex
    TOKENS[token] = {
        "user_id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "client_type": client_type,
        "login_at": datetime.now(timezone.utc).isoformat(),
    }
    LOGIN_LOGS.append(
        {
            "username": user["username"],
            "role": user["role"],
            "client_type": client_type,
            "login_at": TOKENS[token]["login_at"],
        }
    )
    return token


def current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization.removeprefix("Bearer ").strip()
    user = TOKENS.get(token)
    if not user:
        raise HTTPException(status_code=401, detail="token 无效或已过期")
    return user


@app.get("/health")
def health():
    return {"ok": True}


app.mount("/admin-static", StaticFiles(directory=ADMIN_DIR), name="admin-static")


@app.get("/theme.css")
def theme_css():
    return FileResponse(BASE_DIR / "frontend" / "theme.css")


@app.get("/admin")
def admin_login_page():
    return FileResponse(ADMIN_DIR / "index.html")


@app.get("/dashboard")
def admin_dashboard_page():
    return FileResponse(ADMIN_DIR / "dashboard.html")


@app.get("/system/login-log")
def admin_login_log_page():
    return FileResponse(ADMIN_DIR / "login-log.html")


@app.get("/admin/progress")
def admin_progress_page():
    return FileResponse(ADMIN_DIR / "progress.html")


@app.get("/progress")
def progress_page():
    return FileResponse(ADMIN_DIR / "progress.html")


@app.get("/system/user")
def admin_user_page():
    return FileResponse(ADMIN_DIR / "user.html")


@app.get("/system/role")
def admin_role_page():
    return FileResponse(ADMIN_DIR / "role.html")


@app.get("/system/menu")
def admin_menu_page():
    return FileResponse(ADMIN_DIR / "menu.html")


@app.get("/mini/login")
def mini_login_page():
    return FileResponse(MINI_DIR / "login.html")


@app.get("/mini/bind-phone")
def mini_bind_phone_page():
    return FileResponse(MINI_DIR / "bind-phone.html")


@app.get("/mini/role-select")
def mini_role_select_page():
    return FileResponse(MINI_DIR / "role-select.html")


@app.get("/mini/farmer-home")
def mini_farmer_home_page():
    return FileResponse(MINI_DIR / "farmer-home.html")


@app.get("/mini/provider-home")
def mini_provider_home_page():
    return FileResponse(MINI_DIR / "provider-home.html")

@app.get("/mini/provider-profile")
def mini_provider_profile_page():
    return FileResponse(MINI_DIR / "provider-profile.html")


@app.get("/mini/provider-onboard")
def mini_provider_onboard_page():
    return FileResponse(MINI_DIR / "provider-onboard.html")


@app.get("/mini/provider-apply-status")
def mini_provider_apply_status_page():
    return FileResponse(MINI_DIR / "provider-apply-status.html")


@app.get("/mini/provider-apply-reject")
def mini_provider_apply_reject_page():
    return FileResponse(MINI_DIR / "provider-apply-reject.html")



@app.get("/mini/farmer-demand-create")
def mini_farmer_demand_create_page():
    return FileResponse(MINI_DIR / "farmer-demand-create.html")

@app.get("/mini/farmer-demand-list")
def mini_farmer_demand_list_page():
    return FileResponse(MINI_DIR / "farmer-demand-list.html")

@app.get("/mini/farmer-demand-detail")
def mini_farmer_demand_detail_page():
    return FileResponse(MINI_DIR / "farmer-demand-detail.html")

@app.get("/mini/provider-demand-list")
def mini_provider_demand_list_page():
    return FileResponse(MINI_DIR / "provider-demand-list.html")

@app.get("/mini/provider-record-create")
def mini_provider_record_create_page():
    return FileResponse(MINI_DIR / "provider-record-create.html")

@app.get("/ops/demand")
def admin_demand_page():
    return FileResponse(ADMIN_DIR / "demand.html")

@app.get("/ops/service-record")
def admin_service_record_page():
    return FileResponse(ADMIN_DIR / "service-record.html")

@app.get("/operate/provider-audit")
def admin_provider_audit_page():
    return FileResponse(ADMIN_DIR / "provider-audit.html")


@app.get("/ops/service-ability")
def admin_service_ability_page():
    return FileResponse(ADMIN_DIR / "service-ability.html")


@app.get("/ops/contact-log")
def admin_contact_log_page():
    return FileResponse(ADMIN_DIR / "contact-log.html")


@app.get("/mini/farmer-index")
def mini_farmer_index_page():
    return FileResponse(MINI_DIR / "farmer-index.html")


@app.get("/mini/farmer-service-list")
def mini_farmer_service_list_page():
    return FileResponse(MINI_DIR / "farmer-service-list.html")


@app.get("/mini/farmer-provider-detail")
def mini_farmer_provider_detail_page():
    return FileResponse(MINI_DIR / "farmer-provider-detail.html")


@app.get("/mini/provider-ability-list")
def mini_provider_ability_list_page():
    return FileResponse(MINI_DIR / "provider-ability-list.html")


@app.get("/mini/provider-ability-edit")
def mini_provider_ability_edit_page():
    return FileResponse(MINI_DIR / "provider-ability-edit.html")


@app.post("/api/auth/login")
def login(req: LoginRequest):
    user = USERS.get(req.username)
    if not user or user["password"] != req.password:
        raise HTTPException(status_code=401, detail="账号或密码错误")
    token = _create_token(user, req.client_type)
    return {"token": token, "role": user["role"]}


@app.post("/api/auth/wechat-login")
def wechat_login(req: WechatLoginRequest):
    # 最小测试实现：直接使用测试 code 映射用户与 openid
    user = WECHAT_CODE_USER.get(req.code)
    if not user:
        raise HTTPException(status_code=401, detail="微信 code 无效")
    token = _create_token(user, "MINI")
    return {"token": token, "openid": user["openid"], "role": user["role"]}


@app.get("/api/auth/current-user")
def get_current_user(user=Depends(current_user)):
    return {
        "id": user["user_id"],
        "username": user["username"],
        "role": user["role"],
        "clientType": user["client_type"],
        "menus": _menus_by_role(user["role"]),
    }


@app.post("/api/auth/logout")
def logout(user=Depends(current_user), authorization: str | None = Header(default=None)):
    token = authorization.removeprefix("Bearer ").strip()
    TOKENS.pop(token, None)
    return {"message": f"{user['username']} 已退出登录"}


@app.get("/api/system/login-log")
def login_logs(user=Depends(current_user)):
    if user["role"] not in {"ADMIN", "OPERATOR"}:
        raise HTTPException(status_code=403, detail="无权限")
    return {"items": LOGIN_LOGS}


@app.get("/api/system/login-log-summary")
def login_log_summary(user=Depends(current_user)):
    if user["role"] not in {"ADMIN", "OPERATOR"}:
        raise HTTPException(status_code=403, detail="无权限")
    by_client: dict[str, int] = {}
    for item in LOGIN_LOGS:
        by_client[item["client_type"]] = by_client.get(item["client_type"], 0) + 1
    return {"total": len(LOGIN_LOGS), "byClientType": by_client}


@app.get("/api/system/dashboard-stats")
def dashboard_stats(user=Depends(current_user)):
    if user["role"] not in {"ADMIN", "OPERATOR"}:
        raise HTTPException(status_code=403, detail="无权限")
    approved_provider_count = sum(1 for r in PROVIDER_ONBOARDS if r["status"] == "APPROVED")
    return {
        "userCount": len(USERS),
        "providerOnboardCount": len(PROVIDER_ONBOARDS),
        "providerApprovedCount": approved_provider_count,
        "loginCount": len(LOGIN_LOGS),
    }


@app.get("/api/system/user")
def user_list(user=Depends(current_user)):
    if user["role"] != "ADMIN":
        raise HTTPException(status_code=403, detail="无权限")
    items = [{"id": u["id"], "username": u["username"], "role": u["role"]} for u in USERS.values()]
    return {"items": items}


@app.post("/api/system/user")
def user_create(req: UserUpsertRequest, user=Depends(current_user)):
    if user["role"] != "ADMIN":
        raise HTTPException(status_code=403, detail="无权限")
    if req.username in USERS:
        raise HTTPException(status_code=400, detail="用户名已存在")
    new_id = max(u["id"] for u in USERS.values()) + 1 if USERS else 1
    USERS[req.username] = {"id": new_id, "username": req.username, "password": req.password, "role": req.role}
    return {"message": "新增成功"}


@app.put("/api/system/user/{username}")
def user_update(username: str, req: UserUpsertRequest, user=Depends(current_user)):
    if user["role"] != "ADMIN":
        raise HTTPException(status_code=403, detail="无权限")
    target = USERS.get(username)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    target["password"] = req.password
    target["role"] = req.role
    return {"message": "修改成功"}


@app.delete("/api/system/user/{username}")
def user_delete(username: str, user=Depends(current_user)):
    if user["role"] != "ADMIN":
        raise HTTPException(status_code=403, detail="无权限")
    if username == "admin":
        raise HTTPException(status_code=400, detail="admin 不可删除")
    if username not in USERS:
        raise HTTPException(status_code=404, detail="用户不存在")
    USERS.pop(username)
    return {"message": "删除成功"}


@app.get("/api/system/role")
def role_list(user=Depends(current_user)):
    if user["role"] != "ADMIN":
        raise HTTPException(status_code=403, detail="无权限")
    return {"items": ROLE_LIST}


@app.post("/api/system/role")
def role_create(req: RoleUpsertRequest, user=Depends(current_user)):
    if user["role"] != "ADMIN":
        raise HTTPException(status_code=403, detail="无权限")
    if any(x["code"] == req.code for x in ROLE_LIST):
        raise HTTPException(status_code=400, detail="角色编码已存在")
    ROLE_LIST.append({"code": req.code, "name": req.name})
    if req.code not in MENU_LIST:
        MENU_LIST[req.code] = [{"path": "/dashboard", "name": "首页"}]
    return {"message": "新增成功"}


@app.put("/api/system/role/{code}")
def role_update(code: str, req: RoleUpsertRequest, user=Depends(current_user)):
    if user["role"] != "ADMIN":
        raise HTTPException(status_code=403, detail="无权限")
    target = next((x for x in ROLE_LIST if x["code"] == code), None)
    if not target:
        raise HTTPException(status_code=404, detail="角色不存在")
    target["name"] = req.name
    return {"message": "修改成功"}


@app.delete("/api/system/role/{code}")
def role_delete(code: str, user=Depends(current_user)):
    if user["role"] != "ADMIN":
        raise HTTPException(status_code=403, detail="无权限")
    if code in {"ADMIN", "OPERATOR", "FARMER", "PROVIDER"}:
        raise HTTPException(status_code=400, detail="内置角色不可删除")
    idx = next((i for i, x in enumerate(ROLE_LIST) if x["code"] == code), -1)
    if idx < 0:
        raise HTTPException(status_code=404, detail="角色不存在")
    ROLE_LIST.pop(idx)
    MENU_LIST.pop(code, None)
    for u in USERS.values():
        if u["role"] == code:
            u["role"] = "OPERATOR"
    return {"message": "删除成功"}


@app.get("/api/system/menu")
def menu_list(user=Depends(current_user)):
    if user["role"] != "ADMIN":
        raise HTTPException(status_code=403, detail="无权限")
    items = []
    for role_code, menus in MENU_LIST.items():
        for m in menus:
            items.append({"role": role_code, "path": m["path"], "name": m["name"]})
    return {"items": items}


@app.post("/api/provider/onboard-submit")
def provider_onboard_submit(req: ProviderOnboardSubmitRequest, user=Depends(current_user)):
    if user["role"] != "PROVIDER":
        raise HTTPException(status_code=403, detail="仅服务方可提交入驻")
    record = {
        "id": len(PROVIDER_ONBOARDS) + 1,
        "provider_user_id": user["user_id"],
        "provider_username": user["username"],
        "real_name": req.real_name,
        "phone": req.phone,
        "service_area": req.service_area,
        "credential_images": req.credential_images,
        "status": "PENDING",
        "audit_remark": "",
        "submitted_at": datetime.now(timezone.utc).isoformat(),
    }
    PROVIDER_ONBOARDS.append(record)
    return {"id": record["id"], "status": record["status"]}


@app.get("/api/provider/onboard-status")
def provider_onboard_status(user=Depends(current_user)):
    if user["role"] != "PROVIDER":
        raise HTTPException(status_code=403, detail="仅服务方可查看入驻状态")
    items = [r for r in PROVIDER_ONBOARDS if r["provider_user_id"] == user["user_id"]]
    if not items:
        return {"status": "NONE", "latest": None}
    latest = items[-1]
    return {"status": latest["status"], "latest": latest}


@app.get("/api/admin/provider-onboard")
def admin_provider_onboards(user=Depends(current_user)):
    if user["role"] not in {"ADMIN", "OPERATOR"}:
        raise HTTPException(status_code=403, detail="无权限")
    return {"items": PROVIDER_ONBOARDS}


@app.post("/api/admin/provider-onboard/{onboard_id}/audit")
def admin_provider_onboard_audit(onboard_id: int, req: ProviderOnboardAuditRequest, user=Depends(current_user)):
    if user["role"] not in {"ADMIN", "OPERATOR"}:
        raise HTTPException(status_code=403, detail="无权限")
    target = next((r for r in PROVIDER_ONBOARDS if r["id"] == onboard_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="记录不存在")
    target["status"] = "APPROVED" if req.action == "APPROVE" else "REJECTED"
    target["audit_remark"] = req.remark
    target["audited_by"] = user["username"]
    target["audited_at"] = datetime.now(timezone.utc).isoformat()
    return {"id": target["id"], "status": target["status"]}


def _latest_apply_by_user(user_id: int) -> dict | None:
    items = [x for x in PROVIDER_APPLIES if x["userId"] == user_id]
    return items[-1] if items else None


@app.get("/api/provider/apply/status")
def provider_apply_status(user=Depends(current_user)):
    if user["role"] != "PROVIDER":
        raise HTTPException(status_code=403, detail="仅服务方可访问")
    latest = _latest_apply_by_user(user["user_id"])
    if not latest:
        return {"auditStatus": "NOT_SUBMITTED"}
    return {"auditStatus": latest["auditStatus"], "applyId": latest["applyId"], "rejectReason": latest.get("rejectReason", "")}


@app.post("/api/provider/apply/submit")
def provider_apply_submit(req: ProviderApplySubmitRequest, user=Depends(current_user)):
    if user["role"] != "PROVIDER":
        raise HTTPException(status_code=403, detail="仅服务方可提交入驻")
    apply_id = len(PROVIDER_APPLIES) + 10001
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "applyId": apply_id,
        "userId": user["user_id"],
        "providerName": req.providerName,
        "contactName": req.contactName,
        "contactPhone": req.contactPhone,
        "providerType": req.providerType,
        "regionCode": req.regionCode,
        "address": req.address,
        "serviceTypes": req.serviceTypes,
        "serviceDescription": req.serviceDescription,
        "serviceArea": req.serviceArea,
        "attachments": req.attachments,
        "auditStatus": "PENDING",
        "rejectReason": "",
        "auditUserName": "",
        "auditTime": None,
        "createTime": now,
        "updateTime": now,
    }
    PROVIDER_APPLIES.append(record)
    return {"code": 200, "message": "入驻申请已提交，请等待审核", "data": {"applyId": apply_id, "auditStatus": "PENDING"}}


@app.get("/api/provider/apply/detail")
def provider_apply_detail(user=Depends(current_user)):
    if user["role"] != "PROVIDER":
        raise HTTPException(status_code=403, detail="仅服务方可访问")
    latest = _latest_apply_by_user(user["user_id"])
    if not latest:
        raise HTTPException(status_code=404, detail="暂无入驻申请")
    return {"code": 200, "data": latest}


@app.post("/api/provider/apply/resubmit")
def provider_apply_resubmit(req: ProviderApplySubmitRequest, user=Depends(current_user)):
    if user["role"] != "PROVIDER":
        raise HTTPException(status_code=403, detail="仅服务方可重提")
    latest = _latest_apply_by_user(user["user_id"])
    if not latest or latest["auditStatus"] != "REJECTED":
        raise HTTPException(status_code=400, detail="仅驳回状态可重提")
    latest.update(
        {
            "providerName": req.providerName,
            "contactName": req.contactName,
            "contactPhone": req.contactPhone,
            "providerType": req.providerType,
            "regionCode": req.regionCode,
            "address": req.address,
            "serviceTypes": req.serviceTypes,
            "serviceDescription": req.serviceDescription,
            "serviceArea": req.serviceArea,
            "attachments": req.attachments,
            "auditStatus": "PENDING",
            "rejectReason": "",
            "auditUserName": "",
            "auditTime": None,
            "updateTime": datetime.now(timezone.utc).isoformat(),
        }
    )
    return {"code": 200, "message": "已重新提交", "data": {"applyId": latest["applyId"], "auditStatus": "PENDING"}}


@app.get("/api/provider/workbench")
def provider_workbench(user=Depends(current_user)):
    if user["role"] != "PROVIDER":
        raise HTTPException(status_code=403, detail="仅服务方可访问")
    latest = _latest_apply_by_user(user["user_id"])
    if not latest or latest["auditStatus"] != "APPROVED":
        raise HTTPException(status_code=403, detail="尚未审核通过，无法进入工作台")
    provider = next((x for x in PROVIDERS if x["userId"] == user["user_id"]), None)
    if not provider:
        raise HTTPException(status_code=404, detail="服务方主体不存在")
    return {
        "code": 200,
        "data": {
            "providerId": provider["providerId"],
            "providerName": provider["providerName"],
            "auditStatus": "APPROVED",
            "serviceTypes": provider["serviceTypes"],
            "contactPhone": provider["contactPhone"],
            "serviceArea": provider["serviceArea"],
            "profileCompletion": 80,
        },
    }


@app.get("/api/admin/provider/apply/list")
def admin_provider_apply_list(user=Depends(current_user)):
    if user["role"] not in {"ADMIN", "OPERATOR", "GOV_ADMIN"}:
        raise HTTPException(status_code=403, detail="无权限")
    return {"code": 200, "data": PROVIDER_APPLIES}


@app.get("/api/admin/provider/apply/detail")
def admin_provider_apply_detail(applyId: int, user=Depends(current_user)):
    if user["role"] not in {"ADMIN", "OPERATOR", "GOV_ADMIN"}:
        raise HTTPException(status_code=403, detail="无权限")
    target = next((x for x in PROVIDER_APPLIES if x["applyId"] == applyId), None)
    if not target:
        raise HTTPException(status_code=404, detail="申请不存在")
    logs = [x for x in PROVIDER_AUDIT_LOGS if x["applyId"] == applyId]
    return {"code": 200, "data": {"apply": target, "auditLogs": logs}}


@app.post("/api/admin/provider/apply/approve")
def admin_provider_apply_approve(req: ProviderApplyApproveRequest, user=Depends(current_user)):
    if user["role"] not in {"ADMIN", "OPERATOR"}:
        raise HTTPException(status_code=403, detail="无权限审核")
    target = next((x for x in PROVIDER_APPLIES if x["applyId"] == req.applyId), None)
    if not target:
        raise HTTPException(status_code=404, detail="申请不存在")
    target["auditStatus"] = "APPROVED"
    target["auditUserName"] = user["username"]
    target["auditTime"] = datetime.now(timezone.utc).isoformat()
    target["rejectReason"] = ""
    provider = next((x for x in PROVIDERS if x["userId"] == target["userId"]), None)
    if not provider:
        provider = {"providerId": len(PROVIDERS) + 20001, "userId": target["userId"]}
        PROVIDERS.append(provider)
    provider.update(
        {
            "providerName": target["providerName"],
            "contactName": target["contactName"],
            "contactPhone": target["contactPhone"],
            "providerType": target["providerType"],
            "serviceTypes": target["serviceTypes"],
            "serviceArea": target["serviceArea"],
            "serviceDescription": target["serviceDescription"],
            "status": "NORMAL",
            "auditStatus": "APPROVED",
        }
    )
    PROVIDER_AUDIT_LOGS.append(
        {
            "applyId": req.applyId,
            "auditStatus": "APPROVED",
            "auditUserName": user["username"],
            "auditRemark": req.auditRemark,
            "createTime": datetime.now(timezone.utc).isoformat(),
        }
    )
    return {"code": 200, "message": "审核通过"}


@app.post("/api/admin/provider/apply/reject")
def admin_provider_apply_reject(req: ProviderApplyRejectRequest, user=Depends(current_user)):
    if user["role"] not in {"ADMIN", "OPERATOR"}:
        raise HTTPException(status_code=403, detail="无权限审核")
    if not req.rejectReason.strip():
        raise HTTPException(status_code=400, detail="驳回原因不能为空")
    target = next((x for x in PROVIDER_APPLIES if x["applyId"] == req.applyId), None)
    if not target:
        raise HTTPException(status_code=404, detail="申请不存在")
    target["auditStatus"] = "REJECTED"
    target["rejectReason"] = req.rejectReason
    target["auditUserName"] = user["username"]
    target["auditTime"] = datetime.now(timezone.utc).isoformat()
    PROVIDER_AUDIT_LOGS.append(
        {
            "applyId": req.applyId,
            "auditStatus": "REJECTED",
            "auditUserName": user["username"],
            "auditRemark": req.rejectReason,
            "createTime": datetime.now(timezone.utc).isoformat(),
        }
    )
    return {"code": 200, "message": "审核驳回"}


@app.get("/api/admin/provider/list")
def admin_provider_list(user=Depends(current_user)):
    if user["role"] not in {"ADMIN", "OPERATOR", "GOV_ADMIN"}:
        raise HTTPException(status_code=403, detail="无权限")
    return {"code": 200, "data": PROVIDERS}


@app.get("/api/admin/provider/detail")
def admin_provider_detail(providerId: int, user=Depends(current_user)):
    if user["role"] not in {"ADMIN", "OPERATOR", "GOV_ADMIN"}:
        raise HTTPException(status_code=403, detail="无权限")
    target = next((x for x in PROVIDERS if x["providerId"] == providerId), None)
    if not target:
        raise HTTPException(status_code=404, detail="服务方不存在")
    return {"code": 200, "data": target}


@app.post("/api/file/upload")
async def file_upload(
    file: UploadFile = File(...),
    fileType: str = Form(default=""),
    user=Depends(current_user),
):
    ext = (fileType or file.filename.rsplit(".", 1)[-1]).lower()
    if ext not in {"jpg", "jpeg", "png", "pdf"}:
        raise HTTPException(status_code=400, detail="仅支持 jpg/jpeg/png/pdf")
    content = await file.read()
    file_id = uuid4().hex
    UPLOADED_FILES[file_id] = {
        "content": content,
        "fileName": file.filename,
        "fileType": ext,
    }
    return {
        "code": 200,
        "data": {
            "fileName": file.filename,
            "fileUrl": f"/api/file/download/{file_id}",
            "fileSize": len(content),
            "fileType": ext,
            "fileId": file_id,
        },
    }


@app.get("/api/file/download/{file_id}")
def file_download(file_id: str, user=Depends(current_user)):
    target = UPLOADED_FILES.get(file_id)
    if not target:
        raise HTTPException(status_code=404, detail="文件不存在")
    content_type = "application/pdf" if target["fileType"] == "pdf" else f"image/{'jpeg' if target['fileType'] == 'jpg' else target['fileType']}"
    return Response(
        content=target["content"],
        media_type=content_type,
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{target['fileName']}"},
    )


def _provider_guard(user_ctx: dict) -> dict:
    if user_ctx["role"] != "PROVIDER":
        raise HTTPException(status_code=403, detail="仅服务方可操作")
    latest = _latest_apply_by_user(user_ctx["user_id"])
    if not latest or latest["auditStatus"] != "APPROVED":
        raise HTTPException(status_code=403, detail="服务方尚未审核通过，暂不能维护服务能力")
    provider = next((x for x in PROVIDERS if x["userId"] == user_ctx["user_id"]), None)
    if not provider or provider.get("status", "NORMAL") != "NORMAL":
        raise HTTPException(status_code=403, detail="服务方状态异常")
    return provider


@app.get("/api/provider/ability/list")
def provider_ability_list(user=Depends(current_user)):
    provider = _provider_guard(user)
    items = [x for x in SERVICE_ABILITIES if x["providerId"] == provider["providerId"]]
    return {"code": 200, "data": items}


@app.post("/api/provider/ability/create")
def provider_ability_create(req: AbilityUpsertRequest, user=Depends(current_user)):
    provider = _provider_guard(user)
    new_id = len(SERVICE_ABILITIES) + 20001
    item = req.model_dump()
    item.update({"id": new_id, "providerId": provider["providerId"], "userId": user["user_id"], "status": "ENABLE"})
    SERVICE_ABILITIES.append(item)
    return {"code": 200, "message": "新增成功", "data": {"id": new_id}}


@app.post("/api/provider/ability/update")
def provider_ability_update(req: AbilityUpsertRequest, user=Depends(current_user)):
    provider = _provider_guard(user)
    target = next((x for x in SERVICE_ABILITIES if x["id"] == req.id), None)
    if not target or target["providerId"] != provider["providerId"]:
        raise HTTPException(status_code=404, detail="服务能力不存在")
    status = target["status"]
    target.update(req.model_dump())
    target["status"] = status
    return {"code": 200, "message": "修改成功"}


@app.post("/api/provider/ability/enable")
def provider_ability_enable(req: AbilitySwitchRequest, user=Depends(current_user)):
    provider = _provider_guard(user)
    target = next((x for x in SERVICE_ABILITIES if x["id"] == req.id), None)
    if not target or target["providerId"] != provider["providerId"]:
        raise HTTPException(status_code=404, detail="服务能力不存在")
    target["status"] = "ENABLE"
    return {"code": 200, "message": "已启用"}


@app.post("/api/provider/ability/disable")
def provider_ability_disable(req: AbilitySwitchRequest, user=Depends(current_user)):
    provider = _provider_guard(user)
    target = next((x for x in SERVICE_ABILITIES if x["id"] == req.id), None)
    if not target or target["providerId"] != provider["providerId"]:
        raise HTTPException(status_code=404, detail="服务能力不存在")
    target["status"] = "DISABLE"
    return {"code": 200, "message": "已停用"}


@app.get("/api/provider/ability/detail")
def provider_ability_detail(id: int, user=Depends(current_user)):
    provider = _provider_guard(user)
    target = next((x for x in SERVICE_ABILITIES if x["id"] == id and x["providerId"] == provider["providerId"]), None)
    if not target:
        raise HTTPException(status_code=404, detail="服务能力不存在")
    return {"code": 200, "data": target}


@app.get("/api/farmer/service/category/list")
def farmer_service_category_list(user=Depends(current_user)):
    if user["role"] != "FARMER":
        raise HTTPException(status_code=403, detail="仅农户可访问")
    return {"code": 200, "data": SERVICE_CATEGORIES}


@app.get("/api/farmer/provider/list")
def farmer_provider_list(serviceType: str = "", regionCode: str = "", keyword: str = "", availableStatus: str = "", pageNum: int = 1, pageSize: int = 20, user=Depends(current_user)):
    if user["role"] != "FARMER":
        raise HTTPException(status_code=403, detail="仅农户可访问")
    items = []
    for a in SERVICE_ABILITIES:
        if a["status"] != "ENABLE":
            continue
        p = next((x for x in PROVIDERS if x["providerId"] == a["providerId"]), None)
        if not p or p.get("auditStatus") != "APPROVED" or p.get("status", "NORMAL") != "NORMAL":
            continue
        if serviceType and a["serviceType"] != serviceType:
            continue
        if regionCode and a.get("regionCode") != regionCode:
            continue
        if availableStatus and a.get("availableStatus") != availableStatus:
            continue
        if keyword and keyword not in f"{p.get('providerName','')}{a.get('abilityName','')}{a.get('abilityDesc','')}":
            continue
        profile_score = len([k for k in [a.get("contactPhone"), a.get("wechatNo"), a.get("priceDesc"), a.get("dailyCapacity")] if k])
        items.append({"providerId": p["providerId"], "providerName": p["providerName"], "serviceType": a["serviceType"], "abilityId": a["id"], "abilityName": a["abilityName"], "abilityDesc": a["abilityDesc"], "serviceArea": a["serviceArea"], "availableStatus": a.get("availableStatus", "AVAILABLE"), "contactPhone": a.get("contactPhone", p.get("contactPhone", "")), "profileScore": profile_score, "updateTime": a.get("updateTime", "")})
    order = {"AVAILABLE": 0, "BUSY": 1, "STOPPED": 2}
    items.sort(key=lambda x: (order.get(x.get("availableStatus", "AVAILABLE"), 9), -x.get("profileScore", 0), x.get("updateTime", "")), reverse=False)
    start = (pageNum - 1) * pageSize
    return {"code": 200, "data": {"total": len(items), "items": items[start:start + pageSize]}}


@app.get("/api/farmer/provider/detail")
def farmer_provider_detail(providerId: int, abilityId: int, user=Depends(current_user)):
    if user["role"] != "FARMER":
        raise HTTPException(status_code=403, detail="仅农户可访问")
    p = next((x for x in PROVIDERS if x["providerId"] == providerId and x.get("auditStatus") == "APPROVED"), None)
    a = next((x for x in SERVICE_ABILITIES if x["id"] == abilityId and x["providerId"] == providerId and x["status"] == "ENABLE"), None)
    if not p or not a:
        raise HTTPException(status_code=404, detail="服务信息不存在")
    return {"code": 200, "data": {"provider": p, "ability": a}}


@app.post("/api/farmer/contact-log/create")
def farmer_contact_log_create(req: ContactLogCreateRequest, user=Depends(current_user)):
    if user["role"] != "FARMER":
        raise HTTPException(status_code=403, detail="仅农户可访问")
    a = next((x for x in SERVICE_ABILITIES if x["id"] == req.abilityId and x["providerId"] == req.providerId), None)
    p = next((x for x in PROVIDERS if x["providerId"] == req.providerId), None)
    if not a or a["status"] != "ENABLE" or not p or p.get("auditStatus") != "APPROVED":
        raise HTTPException(status_code=400, detail="该服务暂不可联系")
    SERVICE_CONTACT_LOGS.append({"id": len(SERVICE_CONTACT_LOGS) + 30001, "farmerUserId": user["user_id"], "providerId": req.providerId, "abilityId": req.abilityId, "contactType": req.contactType, "sourcePage": req.sourcePage, "createTime": datetime.now(timezone.utc).isoformat()})
    a["contactCount"] = a.get("contactCount", 0) + 1
    return {"code": 200, "message": "联系记录已保存"}


@app.get("/api/admin/service-ability/list")
def admin_service_ability_list(serviceType: str = "", providerName: str = "", status: str = "", user=Depends(current_user)):
    if user["role"] not in {"ADMIN", "OPERATOR", "GOV_ADMIN"}:
        raise HTTPException(status_code=403, detail="无权限")
    items = SERVICE_ABILITIES
    if serviceType:
        items = [x for x in items if x.get("serviceType") == serviceType]
    if status:
        items = [x for x in items if x.get("status") == status]
    if providerName:
        items = [x for x in items if providerName in next((p.get("providerName", "") for p in PROVIDERS if p["providerId"] == x["providerId"]), "")]
    return {"code": 200, "data": items}


@app.get("/api/admin/service-ability/detail")
def admin_service_ability_detail(id: int, user=Depends(current_user)):
    if user["role"] not in {"ADMIN", "OPERATOR", "GOV_ADMIN"}:
        raise HTTPException(status_code=403, detail="无权限")
    target = next((x for x in SERVICE_ABILITIES if x["id"] == id), None)
    if not target:
        raise HTTPException(status_code=404, detail="服务能力不存在")
    return {"code": 200, "data": target}


@app.post("/api/admin/service-ability/disable")
def admin_service_ability_disable(req: AbilitySwitchRequest, user=Depends(current_user)):
    if user["role"] not in {"ADMIN", "OPERATOR"}:
        raise HTTPException(status_code=403, detail="无权限")
    target = next((x for x in SERVICE_ABILITIES if x["id"] == req.id), None)
    if not target:
        raise HTTPException(status_code=404, detail="服务能力不存在")
    target["status"] = "DISABLE"
    return {"code": 200, "message": "已下架"}


@app.get("/api/admin/contact-log/list")
def admin_contact_log_list(providerId: int = 0, serviceType: str = "", user=Depends(current_user)):
    if user["role"] not in {"ADMIN", "OPERATOR", "GOV_ADMIN"}:
        raise HTTPException(status_code=403, detail="无权限")
    items = SERVICE_CONTACT_LOGS
    if providerId:
        items = [x for x in items if x.get("providerId") == providerId]
    if serviceType:
        ability_map = {a["id"]: a.get("serviceType", "") for a in SERVICE_ABILITIES}
        items = [x for x in items if ability_map.get(x.get("abilityId")) == serviceType]
    return {"code": 200, "data": items}


@app.get("/api/admin/contact-log/stat")
def admin_contact_log_stat(user=Depends(current_user)):
    if user["role"] not in {"ADMIN", "OPERATOR", "GOV_ADMIN"}:
        raise HTTPException(status_code=403, detail="无权限")
    stat: dict[int, int] = {}
    for x in SERVICE_CONTACT_LOGS:
        stat[x["providerId"]] = stat.get(x["providerId"], 0) + 1
    return {"code": 200, "data": stat}

# 第四闭环：需求与留痕
SERVICE_DEMANDS: list[dict] = []
SERVICE_RECORDS: list[dict] = []
SERVICE_EVIDENCES: list[dict] = []
SERVICE_DEMAND_LOGS: list[dict] = []


class FarmerDemandCreateRequest(BaseModel):
    providerId: int
    abilityId: int
    serviceType: str
    contactName: str
    contactPhone: str
    regionCode: str = ""
    serviceAddress: str
    quantity: float
    unit: str
    expectedTime: str
    remark: str = ""


class DemandActionRequest(BaseModel):
    demandId: int


class EvidenceItem(BaseModel):
    evidenceType: str
    fileName: str
    fileUrl: str


class ServiceRecordCreateRequest(BaseModel):
    demandId: int
    serviceType: str
    serviceAddress: str
    processQuantity: float
    unit: str
    startTime: str
    endTime: str
    description: str = ""
    evidences: list[EvidenceItem]


def _append_demand_log(demand_id: int, user: dict, before_status: str, after_status: str, action: str):
    SERVICE_DEMAND_LOGS.append({"id": len(SERVICE_DEMAND_LOGS) + 50001, "demandId": demand_id, "operatorUserId": user["user_id"], "operatorRole": user["role"], "beforeStatus": before_status, "afterStatus": after_status, "action": action, "createTime": datetime.now(timezone.utc).isoformat()})


@app.post('/api/farmer/demand/create')
def farmer_demand_create(req: FarmerDemandCreateRequest, user=Depends(current_user)):
    if user['role'] != 'FARMER':
        raise HTTPException(status_code=403, detail='仅农户可操作')
    if req.quantity <= 0 or not req.contactPhone.strip():
        raise HTTPException(status_code=400, detail='数量和联系电话必须有效')
    provider = next((x for x in PROVIDERS if x['providerId'] == req.providerId and x.get('auditStatus') == 'APPROVED'), None)
    ability = next((x for x in SERVICE_ABILITIES if x['id'] == req.abilityId and x['providerId'] == req.providerId and x['status'] == 'ENABLE'), None)
    if not provider or not ability:
        raise HTTPException(status_code=400, detail='服务方或服务能力无效')
    demand_id = len(SERVICE_DEMANDS) + 30001
    item = req.model_dump()
    item.update({'id': demand_id, 'farmerUserId': user['user_id'], 'status': 'SUBMITTED', 'createTime': datetime.now(timezone.utc).isoformat()})
    SERVICE_DEMANDS.append(item)
    _append_demand_log(demand_id, user, '', 'SUBMITTED', 'CREATE')
    return {'code': 200, 'message': '需求提交成功', 'data': {'demandId': demand_id, 'status': 'SUBMITTED'}}


@app.get('/api/farmer/demand/list')
def farmer_demand_list(user=Depends(current_user)):
    if user['role'] != 'FARMER':
        raise HTTPException(status_code=403, detail='仅农户可访问')
    items = [x for x in SERVICE_DEMANDS if x['farmerUserId'] == user['user_id']]
    return {'code': 200, 'data': items}


@app.get('/api/farmer/demand/detail')
def farmer_demand_detail(id: int, user=Depends(current_user)):
    if user['role'] != 'FARMER':
        raise HTTPException(status_code=403, detail='仅农户可访问')
    item = next((x for x in SERVICE_DEMANDS if x['id'] == id and x['farmerUserId'] == user['user_id']), None)
    if not item:
        raise HTTPException(status_code=404, detail='需求不存在')
    return {'code': 200, 'data': item}


@app.post('/api/provider/demand/contacted')
def provider_demand_contacted(req: DemandActionRequest, user=Depends(current_user)):
    provider = _provider_guard(user)
    item = next((x for x in SERVICE_DEMANDS if x['id'] == req.demandId and x['providerId'] == provider['providerId']), None)
    if not item:
        raise HTTPException(status_code=404, detail='需求不存在')
    before = item['status']; item['status'] = 'CONTACTED'; item['contactedTime'] = datetime.now(timezone.utc).isoformat()
    _append_demand_log(item['id'], user, before, 'CONTACTED', 'CONTACTED')
    return {'code': 200, 'message': '已标记联系'}


@app.post('/api/provider/demand/start-service')
def provider_demand_start(req: DemandActionRequest, user=Depends(current_user)):
    provider = _provider_guard(user)
    item = next((x for x in SERVICE_DEMANDS if x['id'] == req.demandId and x['providerId'] == provider['providerId']), None)
    if not item:
        raise HTTPException(status_code=404, detail='需求不存在')
    before = item['status']; item['status'] = 'SERVICING'; item['serviceStartTime'] = datetime.now(timezone.utc).isoformat()
    _append_demand_log(item['id'], user, before, 'SERVICING', 'START_SERVICE')
    return {'code': 200, 'message': '已标记服务中'}


@app.get('/api/provider/demand/list')
def provider_demand_list(status: str = '', serviceType: str = '', user=Depends(current_user)):
    provider = _provider_guard(user)
    items = [x for x in SERVICE_DEMANDS if x['providerId'] == provider['providerId']]
    if status: items = [x for x in items if x.get('status') == status]
    if serviceType: items = [x for x in items if x.get('serviceType') == serviceType]
    return {'code': 200, 'data': items}


@app.post('/api/provider/service-record/create')
def provider_record_create(req: ServiceRecordCreateRequest, user=Depends(current_user)):
    provider = _provider_guard(user)
    demand = next((x for x in SERVICE_DEMANDS if x['id'] == req.demandId and x['providerId'] == provider['providerId']), None)
    if not demand or demand.get('status') == 'CANCELLED':
        raise HTTPException(status_code=400, detail='需求不可提交记录')
    if req.processQuantity <= 0 or req.endTime < req.startTime:
        raise HTTPException(status_code=400, detail='处理量或时间无效')
    if not any(x.evidenceType == 'WORK_PHOTO' for x in req.evidences):
        raise HTTPException(status_code=400, detail='至少上传一张作业照片')
    record_id = len(SERVICE_RECORDS) + 40001
    rec = req.model_dump(); rec.update({'id': record_id, 'providerId': provider['providerId'], 'farmerUserId': demand['farmerUserId'], 'abilityId': demand['abilityId'], 'recordStatus': 'SUBMITTED', 'createTime': datetime.now(timezone.utc).isoformat()})
    SERVICE_RECORDS.append(rec)
    for ev in req.evidences:
        SERVICE_EVIDENCES.append({'id': len(SERVICE_EVIDENCES)+60001,'recordId':record_id,'demandId':demand['id'],'providerId':provider['providerId'],'farmerUserId':demand['farmerUserId'], **ev.model_dump()})
    before = demand['status']; demand['status'] = 'COMPLETED'; demand['completedTime'] = datetime.now(timezone.utc).isoformat()
    _append_demand_log(demand['id'], user, before, 'COMPLETED', 'UPLOAD_RECORD')
    return {'code': 200, 'message': '服务记录已提交', 'data': {'recordId': record_id, 'demandStatus': 'COMPLETED'}}


@app.get('/api/admin/demand/list')
def admin_demand_list(status: str = '', serviceType: str = '', user=Depends(current_user)):
    if user['role'] not in {'ADMIN','OPERATOR','GOV_ADMIN'}: raise HTTPException(status_code=403, detail='无权限')
    items = SERVICE_DEMANDS
    if status: items = [x for x in items if x.get('status') == status]
    if serviceType: items = [x for x in items if x.get('serviceType') == serviceType]
    return {'code': 200, 'data': items}


@app.get('/api/admin/service-record/list')
def admin_record_list(user=Depends(current_user)):
    if user['role'] not in {'ADMIN','OPERATOR','GOV_ADMIN'}: raise HTTPException(status_code=403, detail='无权限')
    return {'code': 200, 'data': SERVICE_RECORDS}


@app.get('/api/admin/evidence-chain/detail')
def admin_evidence_chain_detail(recordId: int, user=Depends(current_user)):
    if user['role'] not in {'ADMIN','OPERATOR','GOV_ADMIN'}: raise HTTPException(status_code=403, detail='无权限')
    record = next((x for x in SERVICE_RECORDS if x['id'] == recordId), None)
    if not record: raise HTTPException(status_code=404, detail='记录不存在')
    demand = next((x for x in SERVICE_DEMANDS if x['id'] == record['demandId']), None)
    evs = [x for x in SERVICE_EVIDENCES if x['recordId'] == recordId]
    logs = [x for x in SERVICE_DEMAND_LOGS if x['demandId'] == record['demandId']]
    return {'code': 200, 'data': {'demand': demand, 'record': record, 'evidences': evs, 'logs': logs}}


@app.post('/api/farmer/demand/cancel')
def farmer_demand_cancel(req: DemandActionRequest, user=Depends(current_user)):
    if user['role'] != 'FARMER':
        raise HTTPException(status_code=403, detail='仅农户可操作')
    item = next((x for x in SERVICE_DEMANDS if x['id'] == req.demandId and x['farmerUserId'] == user['user_id']), None)
    if not item:
        raise HTTPException(status_code=404, detail='需求不存在')
    if item['status'] not in {'SUBMITTED','CONTACTED'}:
        raise HTTPException(status_code=400, detail='当前状态不可取消')
    before=item['status'];item['status']='CANCELLED';item['cancelTime']=datetime.now(timezone.utc).isoformat()
    _append_demand_log(item['id'], user, before, 'CANCELLED', 'CANCEL')
    return {'code':200,'message':'已取消'}

@app.get('/api/provider/demand/detail')
def provider_demand_detail(id: int, user=Depends(current_user)):
    provider=_provider_guard(user)
    item=next((x for x in SERVICE_DEMANDS if x['id']==id and x['providerId']==provider['providerId']),None)
    if not item: raise HTTPException(status_code=404, detail='需求不存在')
    return {'code':200,'data':item}

@app.get('/api/provider/service-record/list')
def provider_record_list(user=Depends(current_user)):
    provider=_provider_guard(user)
    return {'code':200,'data':[x for x in SERVICE_RECORDS if x['providerId']==provider['providerId']]}

@app.get('/api/provider/service-record/detail')
def provider_record_detail(id:int,user=Depends(current_user)):
    provider=_provider_guard(user)
    item=next((x for x in SERVICE_RECORDS if x['id']==id and x['providerId']==provider['providerId']),None)
    if not item: raise HTTPException(status_code=404, detail='服务记录不存在')
    evs=[x for x in SERVICE_EVIDENCES if x['recordId']==id]
    return {'code':200,'data':{'record':item,'evidences':evs}}

@app.get('/api/admin/demand/detail')
def admin_demand_detail(id:int,user=Depends(current_user)):
    if user['role'] not in {'ADMIN','OPERATOR','GOV_ADMIN'}: raise HTTPException(status_code=403, detail='无权限')
    item=next((x for x in SERVICE_DEMANDS if x['id']==id),None)
    if not item: raise HTTPException(status_code=404, detail='需求不存在')
    return {'code':200,'data':item}

@app.get('/api/admin/service-record/detail')
def admin_service_record_detail(id:int,user=Depends(current_user)):
    if user['role'] not in {'ADMIN','OPERATOR','GOV_ADMIN'}: raise HTTPException(status_code=403, detail='无权限')
    item=next((x for x in SERVICE_RECORDS if x['id']==id),None)
    if not item: raise HTTPException(status_code=404, detail='服务记录不存在')
    return {'code':200,'data':item}

@app.get('/api/admin/evidence/list')
def admin_evidence_list(recordId:int=0,user=Depends(current_user)):
    if user['role'] not in {'ADMIN','OPERATOR','GOV_ADMIN'}: raise HTTPException(status_code=403, detail='无权限')
    items=SERVICE_EVIDENCES
    if recordId: items=[x for x in items if x['recordId']==recordId]
    return {'code':200,'data':items}
