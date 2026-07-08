"""JWT 鉴权 + API Key 兼容 + 登录接口 """
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from jose import jwt, JWTError

from agent_hemo.settings import (
    JWT_SECRET,
    JWT_ALGORITHM,
    JWT_EXPIRE_MINUTES,
    AUTH_USERNAME,
    AUTH_PASSWORD,
    API_KEY,
)

router = APIRouter()
bearer_scheme = HTTPBearer(auto_error=False)

# --Pydantic Models─────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"

# ── JWT 工具函数 ────────────────────────────────────────
def create_access_token(subject: dict) -> str:
    print(subject)
    """ 生成 JWT, subject 一般是用户名 """
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def _decode_token(token: str) -> str:
    """ 解码 JWT, 返回username 失败抛401 """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        print(payload)
        username: str | None = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="JWT 缺少 sub 字段")
        return username
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"JWT 无效或已过期")

# -- 统一鉴权 Depends ────────────────────────────────────
async def verify_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    """
    优先级：
    1. JWT（Authorization: Bearer xxx）
    2. API Key（X-Api-Key: xxx）—— 向后兼容
    3. 都没配 → 开发模式跳过
    """
    # 情况 1： 有JWT
    if credentials and credentials.credentials:
        return _decode_token(credentials.credentials)

    # 情况 2： 有 API Key （向后兼容
    api_key = request.headers.get("X-Api-Key")
    if api_key and api_key == API_KEY:
        return "api-key-user"
    
    # 情况 3: JWT_SECRET 和 API_KEY 都没配 → 开发模式
    if not JWT_SECRET and not API_KEY:
        return "dev-mode"
    
    # 情况 4: 啥也没传 且有配置 -> 拒绝
    raise HTTPException(status_code=401, detail="请提供 JWT（Authorization: Bearer xxx）或 API Key（X-Api-Key: xxx）")


# -- 登录接口 ────────────────────────────────────────
@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest):
    if not JWT_SECRET:
        raise HTTPException(status_code=401, detail="请配置 JWT_SECRET，无法登录")
    if body.username != AUTH_USERNAME or body.password != AUTH_PASSWORD:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_access_token(body.username)
    return TokenResponse(access_token=token)

    