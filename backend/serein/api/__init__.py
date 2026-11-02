"""Versioned API router composition."""

from fastapi import APIRouter

# 用相对导入列出子模块，而不是 `from serein.api import ...` 或
# `import serein.api.x as x`。
#
# 这个包在被 `serein.main` 导入时仍处于初始化状态。前两种写法都要在
# `sys.modules` 里按绝对名解析 `serein.api` 的成员或子模块；本次修复的报错
# 正是 `import serein.api.auth as auth` 在 Python 3.12 上抛
# `ModuleNotFoundError: No module named 'serein.api.auth'`（3.13+ 能恢复，
# 本仓库的开发环境是 3.14，因此本地测不出来）。相对导入只解析当前包的
# `__path__`，不要求包已初始化完成，三种版本行为一致。
from . import ai, auth, entries, health, integrations, protected


api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(protected.router)
api_router.include_router(entries.router)
api_router.include_router(integrations.router)
api_router.include_router(ai.router)
