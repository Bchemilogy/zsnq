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

    status, data = request_json("POST", f"{base}/api/auth/login", {"username": "admin", "password": "admin123", "client_type": "PC"})
    expect(status == 200 and "token" in data, "PC 登录成功")
    admin_token = data["token"]

    status, data = request_json("POST", f"{base}/api/auth/wechat-login", {"code": "provider-test-code"})
    expect(status == 200 and data.get("role") == "PROVIDER", "小程序服务方登录成功")
    provider_token = data["token"]

    submit = {
        "providerName": "李四农机合作社",
        "contactName": "李四",
        "contactPhone": "13800000000",
        "providerType": "COOPERATIVE",
        "regionCode": "360000",
        "address": "江西省某县某乡镇",
        "serviceTypes": ["AGRICULTURAL_MACHINERY", "DRYING"],
        "serviceDescription": "拥有收割机3台",
        "serviceArea": "某县及周边乡镇",
        "attachments": [{"fileType": "BUSINESS_LICENSE", "fileName": "营业执照.jpg", "fileUrl": "https://x/a.jpg"}],
    }
    status, data = request_json("POST", f"{base}/api/provider/apply/submit", submit, token=provider_token)
    expect(status == 200 and data.get("data", {}).get("auditStatus") == "PENDING", "服务方入驻提交成功")
    apply_id = data["data"]["applyId"]

    status, data = request_json("POST", f"{base}/api/admin/provider/apply/approve", {"applyId": apply_id, "auditRemark": "通过"}, token=admin_token)
    expect(status == 200, "运营审核通过成功")

    status, data = request_json("GET", f"{base}/api/provider/apply/status", token=provider_token)
    expect(status == 200 and data.get("auditStatus") == "APPROVED", "服务方状态变为 APPROVED")

    status, data = request_json("GET", f"{base}/api/provider/workbench", token=provider_token)
    expect(status == 200 and data.get("code") == 200, "服务方可进入工作台")

    print("\n第二闭环关键链路自测通过。")


if __name__ == "__main__":
    main()
