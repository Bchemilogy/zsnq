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


def print_check(idx: int, title: str, ok: bool, detail: str):
    flag = "PASS" if ok else "FAIL"
    print(f"{idx:02d}. [{flag}] {title} | {detail}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    idx = 1
    passed = 0

    _, p = request_json("POST", f"{base}/api/auth/wechat-login", {"code": "provider-test-code"})
    provider_token = p.get("token", "")

    s, d = request_json("GET", f"{base}/api/provider/apply/status", token=provider_token)
    ok = s == 200 and d.get("auditStatus") in {"NOT_SUBMITTED", "PENDING", "APPROVED", "REJECTED", "DISABLED"}
    print_check(idx, "服务方状态接口可用", ok, str(d)); passed += ok; idx += 1

    submit_payload = {
        "providerName": "李四农机合作社",
        "contactName": "李四",
        "contactPhone": "13800000000",
        "providerType": "COOPERATIVE",
        "regionCode": "360000",
        "address": "江西省某县某乡镇",
        "serviceTypes": ["AGRICULTURAL_MACHINERY"],
        "serviceDescription": "测试",
        "serviceArea": "某县",
        "attachments": [{"fileType": "DEVICE_PHOTO", "fileName": "a.jpg", "fileUrl": "https://x/a.jpg"}],
    }
    s, d = request_json("POST", f"{base}/api/provider/apply/submit", submit_payload, token=provider_token)
    apply_id = d.get("data", {}).get("applyId") if s == 200 else None
    ok = s == 200 and d.get("data", {}).get("auditStatus") == "PENDING"
    print_check(idx, "服务方可提交入驻申请", ok, str(d)); passed += ok; idx += 1

    s, d = request_json("POST", f"{base}/api/auth/login", {"username": "operator", "password": "op123", "client_type": "PC"})
    operator_token = d.get("token", "") if s == 200 else ""
    ok = s == 200 and bool(operator_token)
    print_check(idx, "运营账号可登录后台", ok, str(d)); passed += ok; idx += 1

    s, d = request_json("GET", f"{base}/api/admin/provider/apply/list", token=operator_token)
    ok = s == 200 and isinstance(d.get("data"), list)
    print_check(idx, "PC可查看入驻申请列表", ok, f"count={len(d.get('data', []))}"); passed += ok; idx += 1

    s, d = request_json("GET", f"{base}/api/admin/provider/apply/detail?applyId={apply_id}", token=operator_token)
    ok = s == 200 and d.get("data", {}).get("apply", {}).get("applyId") == apply_id
    print_check(idx, "PC可查看申请详情", ok, str(d)); passed += ok; idx += 1

    s, d = request_json("POST", f"{base}/api/admin/provider/apply/reject", {"applyId": apply_id, "rejectReason": "资料不清晰"}, token=operator_token)
    ok = s == 200
    print_check(idx, "可驳回并保存原因", ok, str(d)); passed += ok; idx += 1

    s, d = request_json("GET", f"{base}/api/provider/apply/status", token=provider_token)
    ok = s == 200 and d.get("auditStatus") == "REJECTED"
    print_check(idx, "小程序侧可看到驳回状态", ok, str(d)); passed += ok; idx += 1

    s, d = request_json("POST", f"{base}/api/provider/apply/resubmit", submit_payload, token=provider_token)
    ok = s == 200 and d.get("data", {}).get("auditStatus") == "PENDING"
    print_check(idx, "驳回后可重提", ok, str(d)); passed += ok; idx += 1

    s, d = request_json("POST", f"{base}/api/admin/provider/apply/approve", {"applyId": apply_id, "auditRemark": "通过"}, token=operator_token)
    ok = s == 200
    print_check(idx, "可审核通过", ok, str(d)); passed += ok; idx += 1

    s, d = request_json("GET", f"{base}/api/provider/workbench", token=provider_token)
    ok = s == 200 and d.get("code") == 200
    print_check(idx, "通过后可进入工作台", ok, str(d)); passed += ok; idx += 1

    print(f"\n总计：{passed}/10 通过")


if __name__ == "__main__":
    main()
