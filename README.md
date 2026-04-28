# 智枢农擎平台（最小后端原型）

## 运行

```bash
uv run uvicorn backend.main:app --reload
```

## 自测脚本（关键链路）

先启动服务，再执行：

```bash
uv run --no-project python scripts/smoke_test.py --base-url http://127.0.0.1:8000
```

## 第一阶段验收脚本

```bash
uv run --no-project python scripts/acceptance_check.py --base-url http://127.0.0.1:8000
```

## 当前已实现（第一阶段最小能力）

- PC 账号密码登录：`POST /api/auth/login`
- 小程序微信登录测试：`POST /api/auth/wechat-login`
- 获取当前用户：`GET /api/auth/current-user`
- 退出登录：`POST /api/auth/logout`
- 登录日志：`GET /api/system/login-log`
- 登录日志统计：`GET /api/system/login-log-summary`
- 健康检查：`GET /health`
- PC 后台最小页面：`GET /admin`（登录页）、`GET /dashboard`（首页）
- 登录日志页面：`GET /system/login-log`（日志列表页）
- 用户管理页面：`GET /system/user`（用户列表页）
- 用户管理接口：`GET /api/system/user`（仅 ADMIN）
- 角色管理页面：`GET /system/role`（角色列表页）
- 菜单管理页面：`GET /system/menu`（菜单列表页）
- 角色接口：`GET /api/system/role`（仅 ADMIN）
- 菜单接口：`GET /api/system/menu`（仅 ADMIN）
- 小程序登录测试页：`GET /mini/login`
- 绑定手机号预留页：`GET /mini/bind-phone`
- 身份选择页：`GET /mini/role-select`
- 农户测试首页：`GET /mini/farmer-home`
- 服务方测试首页：`GET /mini/provider-home`
- 服务方入驻申请页：`GET /mini/provider-onboard`
- 服务方入驻提交：`POST /api/provider/onboard-submit`（仅 PROVIDER）
- 服务方入驻状态：`GET /api/provider/onboard-status`（仅 PROVIDER）
- 服务方入驻审核页：`GET /operate/provider-audit`
- 服务方入驻审核列表：`GET /api/admin/provider-onboard`（ADMIN/OPERATOR）
- 服务方入驻审核动作：`POST /api/admin/provider-onboard/{id}/audit`（ADMIN/OPERATOR）
