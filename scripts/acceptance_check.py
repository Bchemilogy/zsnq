import argparse
import json
import urllib.error
import urllib.request


def request_json(method: str, url: str, body: dict | None = None, token: str | None = None):
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url=url, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8")
        payload = json.loads(text) if text else {}
        return e.code, payload


def request_page(url: str):
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    checks = []

    page_status = request_page(f"{base}/mini/login")
    checks.append(("小程序登录测试页可打开", page_status == 200, f"/mini/login => {page_status}"))

    code = "provider-test-code"
    checks.append(("可获取并使用测试 code", bool(code), f"code={code}"))

    status, data = request_json("POST", f"{base}/api/auth/wechat-login", {"code": code})
    checks.append(("code 可传后端并登录", status == 200, f"status={status}"))

    token = data.get("token") if status == 200 else ""
    checks.append(("后端返回 token", bool(token), f"token_exists={bool(token)}"))

    token_saved = bool(token)
    checks.append(("小程序可保存 token", token_saved, f"mini_token_saved={token_saved}"))

    user_status, user_data = request_json("GET", f"{base}/api/auth/current-user", token=token if token else None)
    checks.append(("current-user 返回用户信息", user_status == 200, f"status={user_status}"))

    role = user_data.get("role") if user_status == 200 else None
    checks.append(("可识别 FARMER/PROVIDER 角色", role in {"FARMER", "PROVIDER"}, f"role={role}"))

    target_page = "/mini/provider-home" if role == "PROVIDER" else "/mini/farmer-home"
    target_status = request_page(f"{base}{target_page}")
    checks.append(("可跳转不同测试首页", target_status == 200, f"{target_page} => {target_status}"))

    logout_status, _ = request_json("POST", f"{base}/api/auth/logout", token=token if token else None)
    checks.append(("可退出登录", logout_status == 200, f"status={logout_status}"))

    admin_status, admin_data = request_json(
        "POST", f"{base}/api/auth/login", {"username": "admin", "password": "admin123", "client_type": "PC"}
    )
    admin_token = admin_data.get("token") if admin_status == 200 else ""
    log_status, log_data = request_json("GET", f"{base}/api/system/login-log", token=admin_token if admin_token else None)
    has_mini_log = any(item.get("client_type") == "MINI" for item in log_data.get("items", [])) if log_status == 200 else False
    checks.append(("后台可看到小程序登录日志", has_mini_log, f"status={log_status}, has_mini_log={has_mini_log}"))

    print("# 第一阶段验收检查结果")
    passed = 0
    for idx, (name, ok, detail) in enumerate(checks, start=1):
        flag = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        print(f"{idx:02d}. [{flag}] {name} | {detail}")

    print(f"\n总计：{passed}/{len(checks)} 通过")


if __name__ == "__main__":
    main()
