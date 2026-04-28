from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
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


USERS = {
    "admin": {"id": 1, "username": "admin", "password": "admin123", "role": "ADMIN"},
    "operator": {"id": 2, "username": "operator", "password": "op123", "role": "OPERATOR"},
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
    "FARMER": [{"path": "/mini/farmer-home", "name": "农户测试首页"}],
    "PROVIDER": [
        {"path": "/mini/provider-home", "name": "服务方测试首页"},
        {"path": "/mini/provider-onboard", "name": "服务方入驻申请"},
    ],
}

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


@app.get("/admin")
def admin_login_page():
    return FileResponse(ADMIN_DIR / "index.html")


@app.get("/dashboard")
def admin_dashboard_page():
    return FileResponse(ADMIN_DIR / "dashboard.html")


@app.get("/system/login-log")
def admin_login_log_page():
    return FileResponse(ADMIN_DIR / "login-log.html")


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


@app.get("/mini/provider-onboard")
def mini_provider_onboard_page():
    return FileResponse(MINI_DIR / "provider-onboard.html")


@app.get("/operate/provider-audit")
def admin_provider_audit_page():
    return FileResponse(ADMIN_DIR / "provider-audit.html")


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


@app.get("/api/system/role")
def role_list(user=Depends(current_user)):
    if user["role"] != "ADMIN":
        raise HTTPException(status_code=403, detail="无权限")
    return {"items": ROLE_LIST}


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
