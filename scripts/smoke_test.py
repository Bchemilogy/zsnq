import argparse
import json
import sys
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
            text = resp.read().decode("utf-8")
            return resp.status, json.loads(text)
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8")
        payload = json.loads(text) if text else {}
        return e.code, payload


def expect(condition: bool, message: str):
    if not condition:
        print(f"[FAIL] {message}")
        sys.exit(1)
    print(f"[OK] {message}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    status, data = request_json("GET", f"{base}/health")
    expect(status == 200 and data.get("ok") is True, "health 可用")

    status, data = request_json(
        "POST",
        f"{base}/api/auth/login",
        {"username": "admin", "password": "admin123", "client_type": "PC"},
    )
    expect(status == 200 and "token" in data, "PC 登录成功")
    admin_token = data["token"]

    status, data = request_json("GET", f"{base}/api/system/dashboard-stats", token=admin_token)
    expect(status == 200 and "loginCount" in data, "dashboard 统计可用")

    status, data = request_json("POST", f"{base}/api/auth/wechat-login", {"code": "provider-test-code"})
    expect(status == 200 and data.get("role") == "PROVIDER", "小程序服务方登录成功")
    provider_token = data["token"]

    submit = {
        "real_name": "测试服务方",
        "phone": "13800000000",
        "service_area": "测试区域",
        "credential_images": ["https://example.com/a.jpg"],
    }
    status, data = request_json("POST", f"{base}/api/provider/onboard-submit", submit, token=provider_token)
    expect(status == 200 and data.get("status") == "PENDING", "服务方入驻提交成功")
    onboard_id = data["id"]

    status, data = request_json("POST", f"{base}/api/admin/provider-onboard/{onboard_id}/audit", {"action": "APPROVE"}, token=admin_token)
    expect(status == 200 and data.get("status") == "APPROVED", "运营审核通过成功")

    status, data = request_json("GET", f"{base}/api/provider/onboard-status", token=provider_token)
    expect(status == 200 and data.get("status") == "APPROVED", "服务方可看到最新审核状态")

    print("\n全部关键链路自测通过。")


if __name__ == "__main__":
    main()
