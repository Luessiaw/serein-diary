"""Versioned API router composition."""

from fastapi import APIRouter

# 逐个 `import serein.api.X`，而不是 `from serein.api import X, Y, ...`。
#
# 两种写法在当前解释器上都可用，但语义不同：后者要求 `serein.api` 这个包对象
# 上已经挂好 `auth` 等属性，也就是要求本次导入开始前包已初始化完毕。只要某个
# 子模块（或它拉进来的其他包）在这期间回头经过一次 `serein.api`，Python 3.12
# 就会报 `ImportError: cannot import name 'auth' from partially initialized
# module 'serein.api'`，而 3.13+ 会从 sys.modules 恢复。显式导入子模块不依赖
# 包属性，因此与版本无关。
import serein.api.auth as auth
import serein.api.entries as entries
import serein.api.health as health
import serein.api.integrations as integrations
import serein.api.protected as protected


api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(protected.router)
api_router.include_router(entries.router)
api_router.include_router(integrations.router)
