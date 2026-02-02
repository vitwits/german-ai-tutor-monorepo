"""
Custom admin router for FastAPI - replaces Flask-Admin with enhanced functionality
"""
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, and_
import os
import datetime
import uuid
from typing import Optional
from datetime import timedelta
from pydantic import BaseModel

from ..database import get_db
from ..models import User, Sentence, SentenceBatch, TempSentence, TTSLog, LLMModel, TTSModel, LLMPrice, TTSVoice, AIPreference, ModelPrompt
from ..dependencies import get_current_user
from ..security import verify_password, create_access_token
from sqlalchemy import delete

router = APIRouter(prefix="/admin", tags=["admin"])

# Pydantic models for API requests
class ModelPromptCreate(BaseModel):
    name: str
    page: str
    prompt: str

class ModelPromptUpdate(BaseModel):
    name: Optional[str] = None
    page: Optional[str] = None
    prompt: Optional[str] = None

# Dependency to check admin access - returns None if not authenticated
async def get_admin_user(request: Request, db: AsyncSession = Depends(get_db)) -> Optional[User]:
    """Try to get current admin user from token, return None if not authenticated"""
    try:
        # Try to extract token from cookie or header
        token = None
        
        # Check Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
        
        # Check cookies as fallback
        if not token:
            token = request.cookies.get("admin_token")
        
        if not token:
            return None
        
        # Decode token and get user
        from ..security import SECRET_KEY, ALGORITHM
        from jose import jwt, JWTError
        
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id: str = payload.get("uid")
            if user_id is None:
                return None
        except JWTError:
            return None
        
        # Get user from database
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if user and user.is_admin:
            return user
        return None
    except Exception:
        return None


async def check_admin_access(admin_user: Optional[User] = Depends(get_admin_user)) -> User:
    """Ensure user is authenticated and is admin"""
    if not admin_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return admin_user



@router.get("/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    """Admin login page"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Login</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto;
            }
            .login-container {
                background: white;
                padding: 40px;
                border-radius: 8px;
                box-shadow: 0 10px 25px rgba(0,0,0,0.2);
                width: 100%;
                max-width: 400px;
            }
            .login-header {
                text-align: center;
                margin-bottom: 30px;
            }
            .login-header h1 {
                font-size: 2em;
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 10px;
            }
            .login-header p {
                color: #7f8c8d;
                font-size: 0.9em;
            }
            .form-group label {
                font-weight: 500;
                color: #2c3e50;
            }
            .btn-login {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border: none;
                padding: 10px;
                font-weight: 500;
                width: 100%;
                margin-top: 10px;
            }
            .btn-login:hover {
                background: linear-gradient(135deg, #5568d3 0%, #6a3f8f 100%);
                color: white;
            }
            .alert {
                margin-bottom: 20px;
            }
        </style>
    </head>
    <body>
        <div class="login-container">
            <div class="login-header">
                <h1>🎓 Admin Panel</h1>
                <p>German AI Tutor Administration</p>
            </div>
            
            <form action="/admin/login" method="POST">
                <div class="form-group">
                    <label for="email">Email Address</label>
                    <input type="email" class="form-control" id="email" name="email" placeholder="admin@example.com" required>
                </div>
                <div class="form-group">
                    <label for="password">Password</label>
                    <input type="password" class="form-control" id="password" name="password" placeholder="Enter your password" required>
                </div>
                <button type="submit" class="btn btn-primary btn-login">Sign In</button>
            </form>
        </div>
    </body>
    </html>
    """
    return html


@router.post("/login")
async def admin_login(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle admin login"""
    try:
        form = await request.form()
        email = form.get("email")
        password = form.get("password")
        
        if not email or not password:
            raise HTTPException(status_code=400, detail="Email and password required")
        
        # Find user by email
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        
        if not user or not user.is_admin:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Verify password
        if not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Create token
        access_token_expires = timedelta(days=7)
        access_token = create_access_token(
            data={"uid": user.id},
            expires_delta=access_token_expires
        )
        
        # Redirect to dashboard with token in cookie
        response = RedirectResponse(url="/admin/", status_code=302)
        response.set_cookie(
            key="admin_token",
            value=access_token,
            max_age=60*60*24*7,  # 7 days
            httponly=True,
            samesite="Lax"
        )
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {e}")
        raise HTTPException(status_code=500, detail=f"Login error: {str(e)}")


@router.get("/logout")
async def admin_logout():
    """Logout - clear admin token"""
    response = RedirectResponse(url="/admin/login", status_code=302)
    response.delete_cookie("admin_token")
    return response


@router.get("/caching-stats", response_class=HTMLResponse)
async def caching_stats(
    period: str = Query("all", regex="^(today|month|all)$"),
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """TTS Caching Statistics"""
    query = select(TTSLog.language, TTSLog.source, func.count(TTSLog.id), func.sum(TTSLog.chars))
    
    # Apply period filter
    if period == "today":
        start_date = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        query = query.where(TTSLog.created_at >= start_date)
    elif period == "month":
        today = datetime.datetime.utcnow()
        start_date = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        query = query.where(TTSLog.created_at >= start_date)
    
    result = await db.execute(query.group_by(TTSLog.language, TTSLog.source))
    rows = result.all()
    
    # Process data
    stats_map = {}
    for lang, source, count, chars in rows:
        if lang not in stats_map:
            stats_map[lang] = {"api_req": 0, "api_chars": 0, "cache_req": 0, "cache_chars": 0}
        
        c_val = int(chars) if chars else 0
        if source == "api":
            stats_map[lang]["api_req"] += count
            stats_map[lang]["api_chars"] += c_val
        else:
            stats_map[lang]["cache_req"] += count
            stats_map[lang]["cache_chars"] += c_val
    
    # Build stats list
    lang_map = {"de": ("German", "🇩🇪"), "en": ("English", "🇬🇧"), "uk": ("Ukrainian", "🇺🇦")}
    data = []
    grand = {"api_req": 0, "api_chars": 0, "cache_req": 0, "cache_chars": 0, "total_req": 0, "total_chars": 0}
    
    for lang_code in ["de", "en", "uk"]:
        s = stats_map.get(lang_code, {"api_req": 0, "api_chars": 0, "cache_req": 0, "cache_chars": 0})
        
        total_req = s["api_req"] + s["cache_req"]
        total_chars = s["api_chars"] + s["cache_chars"]
        pct = 0
        if total_req > 0:
            pct = round((s["cache_req"] / total_req) * 100, 1)
        
        lang_name, emoji = lang_map.get(lang_code, (lang_code.upper(), ""))
        
        data.append({
            "lang_code": lang_code,
            "lang_name": lang_name,
            "emoji": emoji,
            "api_req": s["api_req"],
            "api_chars": s["api_chars"],
            "cache_req": s["cache_req"],
            "cache_chars": s["cache_chars"],
            "total_req": total_req,
            "total_chars": total_chars,
            "pct": pct
        })
        
        grand["api_req"] += s["api_req"]
        grand["api_chars"] += s["api_chars"]
        grand["cache_req"] += s["cache_req"]
        grand["cache_chars"] += s["cache_chars"]
        grand["total_req"] += total_req
        grand["total_chars"] += total_chars
    
    grand_pct = 0
    if grand["total_req"] > 0:
        grand_pct = round((grand["cache_req"] / grand["total_req"]) * 100, 1)
    
    # Build rows HTML
    rows_html = ""
    for s in data:
        rows_html += f"""
        <tr>
            <td style="font-weight: bold;">{s["emoji"]} {s["lang_name"]}</td>
            <td style="text-align: center;">{s["api_req"]} <span style="color: #999;">({s["api_chars"]:,})</span></td>
            <td style="text-align: center; color: #2e7d32; font-weight: bold;">{s["cache_req"]} <span style="color: #999; font-weight: normal;">({s["cache_chars"]:,})</span></td>
            <td style="text-align: center;">{s["total_req"]} <span style="color: #999;">({s["total_chars"]:,})</span></td>
            <td>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <div style="flex: 1; height: 24px; background: #e0e0e0; border-radius: 4px; position: relative; overflow: hidden;">
                        <div style="height: 100%; background: linear-gradient(90deg, #4caf50, #45a049); width: {s["pct"]}%; display: flex; align-items: center; justify-content: center; color: white; font-size: 12px; font-weight: bold;">
                            {s["pct"]}%
                        </div>
                    </div>
                </div>
            </td>
        </tr>
        """
    
    # Total row
    rows_html += f"""
        <tr style="background-color: #f5f5f5; font-weight: bold; border-top: 2px solid #ddd;">
            <td>TOTAL</td>
            <td style="text-align: center;">{grand["api_req"]} <span style="color: #999;">({grand["api_chars"]:,})</span></td>
            <td style="text-align: center; color: #2e7d32;">{grand["cache_req"]} <span style="color: #999; font-weight: normal;">({grand["cache_chars"]:,})</span></td>
            <td style="text-align: center;">{grand["total_req"]} <span style="color: #999;">({grand["total_chars"]:,})</span></td>
            <td>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <div style="flex: 1; height: 24px; background: #e0e0e0; border-radius: 4px; position: relative; overflow: hidden;">
                        <div style="height: 100%; background: linear-gradient(90deg, #2196F3, #1976D2); width: {grand_pct}%; display: flex; align-items: center; justify-content: center; color: white; font-size: 12px; font-weight: bold;">
                            {grand_pct}%
                        </div>
                    </div>
                </div>
            </td>
        </tr>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto; background-color: #f5f7fa; }}
            .navbar {{ display: block!important; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 30px; }}
            .navbar-container {{ display: flex; align-items: center; justify-content: flex-start; padding: 0 30px; height: 50px; gap: 40px; }}
            .navbar-brand {{ font-size: 1.5em; font-weight: 700; color: white; text-decoration: none; display: flex; align-items: center; gap: 10px; white-space: nowrap; }}
            .navbar-brand:hover {{ color: #f0f0f0; }}
            .nav-menu {{ display: flex; gap: 0; list-style: none; margin: 0; padding: 0; }}
            .nav-item {{ position: relative; }}
            .nav-link {{ color: rgba(255,255,255,0.9); text-decoration: none; padding: 15px 12px; font-size: 0.9em; font-weight: 500; transition: all 0.3s; border-bottom: 3px solid transparent; height: 50px; display: flex; align-items: center; white-space: nowrap; }}
            .nav-link:hover {{ color: white; background-color: rgba(255,255,255,0.1); border-bottom-color: rgba(255,255,255,0.3); }}
            .nav-link.active {{ color: white; background-color: rgba(255,255,255,0.15); border-bottom-color: white; }}
            .nav-right {{ display: flex; gap: 8px; align-items: center; margin-left: auto; color: white; font-size: 0.85em; white-space: nowrap; }}
            .nav-right a.nav-link {{ padding: 8px 12px; height: auto; border-bottom: none; }}
            .container-main {{ max-width: 1400px; margin: 0 auto; padding: 0 30px; }}
            h1 {{ font-size: 2em; color: #2c3e50; margin-bottom: 10px; font-weight: 700; }}
            .subtitle {{ color: #999; font-size: 0.9em; margin-bottom: 30px; }}
            .period-buttons {{ margin-bottom: 30px; display: flex; gap: 10px; }}
            .period-btn {{ padding: 8px 16px; border: 1px solid #ddd; background: white; border-radius: 6px; cursor: pointer; text-decoration: none; color: #333; font-weight: 500; transition: all 0.2s; }}
            .period-btn:hover {{ border-color: #667eea; color: #667eea; }}
            .period-btn.active {{ background: #667eea; color: white; border-color: #667eea; }}
            .table-responsive {{ background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); overflow: hidden; }}
            table {{ margin: 0; width: 100%; border-collapse: collapse; }}
            table thead {{ background-color: #f8f9fa; border-bottom: 2px solid #e9ecef; }}
            table th {{ padding: 15px; font-weight: 600; color: #2c3e50; text-align: left; }}
            table td {{ padding: 15px; border-bottom: 1px solid #e9ecef; }}
            table tbody tr:hover {{ background-color: #fafafa; }}
        </style>
    </head>
    <body>
        <nav class="navbar">
            <div class="navbar-container">
                <a class="navbar-brand" href="/admin">🎓 Admin</a>
                <ul class="nav-menu">
                    <li class="nav-item"><a class="nav-link" href="/admin">Dashboard</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/sentence/list">Sentences</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/reported">Reported</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/users">Users</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/llm-prices">LLM Prices</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/llm-models">LLM Models</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/tts-models">TTS Models</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/tts-voices">TTS Voices</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/ai-preferences">AI Preferences</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/generate">Generate</a></li>
                    <li class="nav-item"><a class="nav-link active" href="/admin/caching-stats">Stats</a></li>
                </ul>
                <div class="nav-right">
                    <span title="{current_user.email}">{current_user.email.split("@")[0]}</span>
                    <a class="nav-link" href="/admin/logout">Logout</a>
                </div>
            </div>
        </nav>
        
        <div class="container-main">
            <h1>TTS Caching Statistics</h1>
            <p class="subtitle">Efficiency of local audio caching vs Google TTS API calls.</p>
            
            <div class="period-buttons">
                <a href="?period=today" class="period-btn {'active' if period == 'today' else ''}">Today</a>
                <a href="?period=month" class="period-btn {'active' if period == 'month' else ''}">This Month</a>
                <a href="?period=all" class="period-btn {'active' if period == 'all' else ''}">All Time</a>
            </div>
            
            <div class="table-responsive">
                <table>
                    <thead>
                        <tr>
                            <th style="vertical-align: middle;">Language</th>
                            <th style="text-align: center;">Google TTS (API)<br><small style="font-weight: normal; color: #999;">Requests (Tokens)</small></th>
                            <th style="text-align: center;">Cached<br><small style="font-weight: normal; color: #999;">Requests (Tokens)</small></th>
                            <th style="text-align: center;">Total<br><small style="font-weight: normal; color: #999;">Requests (Tokens)</small></th>
                            <th>Cache Efficiency (%)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """
    return html


@router.get("/", response_class=HTMLResponse)
async def admin_index(
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Admin dashboard"""
    sentence_count = (await db.execute(select(func.count(Sentence.id)))).scalar() or 0
    user_count = (await db.execute(select(func.count(User.id)))).scalar() or 0
    reported_count = (await db.execute(
        select(func.count(Sentence.id)).where(Sentence.reported == 1)
    )).scalar() or 0
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Dashboard</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" rel="stylesheet">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto; background-color: #f5f7fa; }}
            .navbar {{ display: block!important; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 30px; }}
            .navbar-container {{ display: flex; align-items: center; justify-content: flex-start; padding: 0 30px; height: 50px; gap: 40px; }}
            .navbar-brand {{ font-size: 1.5em; font-weight: 700; color: white; text-decoration: none; display: flex; align-items: center; gap: 10px; white-space: nowrap; }}
            .navbar-brand:hover {{ color: #f0f0f0; }}
            .nav-menu {{ display: flex; gap: 0; list-style: none; margin: 0; padding: 0; }}
            .nav-item {{ position: relative; }}
            .nav-link {{ color: rgba(255,255,255,0.9); text-decoration: none; padding: 15px 12px; font-size: 0.9em; font-weight: 500; transition: all 0.3s; border-bottom: 3px solid transparent; height: 50px; display: flex; align-items: center; white-space: nowrap; }}
            .nav-link:hover {{ color: white; background-color: rgba(255,255,255,0.1); border-bottom-color: rgba(255,255,255,0.3); }}
            .nav-link.active {{ color: white; background-color: rgba(255,255,255,0.15); border-bottom-color: white; }}
            .nav-right {{ display: flex; gap: 8px; align-items: center; margin-left: auto; color: white; font-size: 0.85em; white-space: nowrap; }}
            .nav-right a.nav-link {{ padding: 8px 12px; height: auto; border-bottom: none; }}
            .container-main {{ max-width: 1400px; margin: 0 auto; padding: 0 30px; }}
            h1 {{ font-size: 2em; color: #2c3e50; margin-bottom: 30px; font-weight: 700; }}
            .stat-card {{ padding: 20px; text-align: center; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); background: white; border: 1px solid #e9ecef; }}
            .stat-number {{ font-size: 2.5em; font-weight: 700; color: #667eea; margin-bottom: 10px; }}
        </style>
    </head>
    <body>
        <nav class="navbar">
            <div class="navbar-container">
                <a class="navbar-brand" href="/admin">🎓 Admin</a>
                <ul class="nav-menu">
                    <li class="nav-item"><a class="nav-link active" href="/admin">Dashboard</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/sentence/list">Sentences</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/reported">Reported</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/users">Users</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/llm-prices">LLM Prices</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/llm-models">LLM Models</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/tts-models">TTS Models</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/tts-voices">TTS Voices</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/ai-preferences">AI Preferences</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/generate">Generate</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/caching-stats">Stats</a></li>
                </ul>
                <div class="nav-right">
                    <span title="{current_user.email}">{current_user.email.split("@")[0]}</span>
                    <a class="nav-link" href="/admin/logout">Logout</a>
                </div>
            </div>
        </nav>
        
        <div class="container-main">
            <h1>Dashboard</h1>
            <div class="row">
                <div class="col-md-3">
                    <div class="card stat-card">
                        <div class="stat-number">{sentence_count}</div>
                        <div>Total Sentences</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card stat-card">
                        <div class="stat-number">{user_count}</div>
                        <div>Total Users</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card stat-card">
                        <div class="stat-number" style="color: #e74c3c;">{reported_count}</div>
                        <div>Reported Issues</div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html


@router.get("/sentence/list", response_class=HTMLResponse)
async def sentence_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    search: Optional[str] = None,
    level: Optional[str] = None,
    topic: Optional[str] = None,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """List sentences with filtering and pagination"""
    query = select(Sentence)
    
    if search:
        search_term = f"%{search}%"
        query = query.where(
            (Sentence.text_de.ilike(search_term)) |
            (Sentence.text_uk.ilike(search_term)) |
            (Sentence.topic.ilike(search_term))
        )
    
    if level:
        query = query.where(Sentence.level == level)
    
    if topic:
        query = query.where(Sentence.topic == topic)
    
    # Get total count
    count_query = select(func.count(Sentence.id))
    if search:
        search_term = f"%{search}%"
        count_query = count_query.where(
            (Sentence.text_de.ilike(search_term)) |
            (Sentence.text_uk.ilike(search_term)) |
            (Sentence.topic.ilike(search_term))
        )
    if level:
        count_query = count_query.where(Sentence.level == level)
    if topic:
        count_query = count_query.where(Sentence.topic == topic)
    
    total = (await db.execute(count_query)).scalar() or 0
    offset = (page - 1) * page_size
    
    result = await db.execute(
        query.order_by(Sentence.id.desc()).offset(offset).limit(page_size)
    )
    sentences = result.scalars().all()
    
    total_pages = (total + page_size - 1) // page_size
    
    # Get unique levels and topics for filters
    levels_result = await db.execute(select(Sentence.level).distinct())
    levels = levels_result.scalars().all()
    
    topics_result = await db.execute(select(Sentence.topic).distinct())
    topics = topics_result.scalars().all()
    
    rows_html = ""
    for s in sentences:
        audio_urls = [s.audio_uk, s.audio_en, s.audio_de]
        audio_urls = [f"'/static/audio/sentences/{url}'" for url in audio_urls if url]
        
        # Шляхи до аудіо з префіксом для JavaScript
        uk_audio = f"'/static/audio/sentences/{s.audio_uk}'" if s.audio_uk else "''"
        en_audio = f"'/static/audio/sentences/{s.audio_en}'" if s.audio_en else "''"
        de_audio = f"'/static/audio/sentences/{s.audio_de}'" if s.audio_de else "''"
        
        rows_html += f"""
        <tr data-audio-uk={uk_audio} data-audio-en={en_audio} data-audio-de={de_audio}>
            <td><input type="checkbox" name="rowid" value="{s.id}"></td>
            <td class="col-play"><button class="play-btn" onclick="playSequence(this)">▶</button></td>
            <td class="col-text-uk">{s.text_uk or ''}</td>
            <td class="col-text-en">{s.text_en or ''}</td>
            <td class="col-text-de">{s.text_de or ''}</td>
            <td class="col-id">{s.id}</td>
            <td class="col-level">{s.level or ''}</td>
            <td class="col-topic">{s.topic or ''}</td>
            <td class="col-actions">
                <div style="display: flex; gap: 8px; align-items: center; justify-content: center;">
                    <a href="/admin/sentence/{s.id}/edit" class="btn btn-primary action-btn" title="Edit">
                        <span class="material-symbols-outlined">edit</span>
                    </a>
                    <form action="/admin/sentence/{s.id}/delete" method="POST" style="display:inline;" onsubmit="return confirm('Delete sentence?');">
                        <button type="submit" class="btn btn-danger action-btn" title="Delete">
                            <span class="material-symbols-outlined">delete</span>
                        </button>
                    </form>
                </div>
            </td>
        </tr>
        """
    
    # Build pagination HTML
    pagination_html = ""
    if page > 1:
        pagination_html += f'<li class="page-item"><a class="page-link" href="/admin/sentence/list?page=1&page_size={page_size}">«</a></li>'
        pagination_html += f'<li class="page-item"><a class="page-link" href="/admin/sentence/list?page={page-1}&page_size={page_size}">&lt;</a></li>'
    else:
        pagination_html += '<li class="page-item disabled"><a class="page-link" href="#">«</a></li>'
        pagination_html += '<li class="page-item disabled"><a class="page-link" href="#">&lt;</a></li>'
    
    for p in range(1, min(total_pages + 1, 10)):
        if p == page:
            pagination_html += f'<li class="page-item active"><a class="page-link" href="#">{p}</a></li>'
        else:
            pagination_html += f'<li class="page-item"><a class="page-link" href="/admin/sentence/list?page={p}&page_size={page_size}">{p}</a></li>'
    
    if page < total_pages:
        pagination_html += f'<li class="page-item"><a class="page-link" href="/admin/sentence/list?page={page+1}&page_size={page_size}">&gt;</a></li>'
        pagination_html += f'<li class="page-item"><a class="page-link" href="/admin/sentence/list?page={total_pages}&page_size={page_size}">»</a></li>'
    else:
        pagination_html += '<li class="page-item disabled"><a class="page-link" href="#">&gt;</a></li>'
        pagination_html += '<li class="page-item disabled"><a class="page-link" href="#">»</a></li>'
    
    filter_options_level = "".join([f'<option value="{l}">{l}</option>' for l in levels if l])
    filter_options_topic = "".join([f'<option value="{t}">{t}</option>' for t in topics if t])
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Sentences Admin</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" rel="stylesheet">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto; background-color: #f5f7fa; }}
            .navbar {{display: block!important; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 30px; }}
            .navbar-container {{ display: flex; align-items: center; justify-content: flex-start; padding: 0 30px; height: 50px; gap: 40px; }}
            .navbar-brand {{ font-size: 1.5em; font-weight: 700; color: white; text-decoration: none; display: flex; align-items: center; gap: 10px; white-space: nowrap; }}
            .navbar-brand:hover {{ color: #f0f0f0; }}
            .nav-menu {{ display: flex; gap: 0; list-style: none; margin: 0; padding: 0; }}
            .nav-item {{ position: relative; }}
            .nav-link {{ color: rgba(255,255,255,0.9); text-decoration: none; padding: 15px 12px; font-size: 0.9em; font-weight: 500; transition: all 0.3s; border-bottom: 3px solid transparent; height: 50px; display: flex; align-items: center; white-space: nowrap; }}
            .nav-link:hover {{ color: white; background-color: rgba(255,255,255,0.1); border-bottom-color: rgba(255,255,255,0.3); }}
            .nav-link.active {{ color: white; background-color: rgba(255,255,255,0.15); border-bottom-color: white; }}
            .nav-right {{ display: flex; gap: 8px; align-items: center; margin-left: auto; color: white; font-size: 0.85em; white-space: nowrap; }}
            .nav-right a.nav-link {{ padding: 8px 12px; height: auto; border-bottom: none; }}
            .container-main {{ max-width: 1400px; margin: 0 auto; padding: 0 30px; }}
            h1 {{ font-size: 2em; color: #2c3e50; margin-bottom: 30px; font-weight: 700; }}
            .controls {{ margin: 30px 0; display: flex; gap: 15px; align-items: center; flex-wrap: wrap; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
            .controls form {{ margin: 0; display: flex; gap: 10px; flex: 1; min-width: 300px; flex-wrap: wrap; }}
            .table-responsive {{ background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); overflow: hidden; }}
            table {{ margin: 0; width: 100%; }}
            table thead {{ background-color: #f8f9fa; border-bottom: 2px solid #e9ecef; }}
            table th {{ padding: 15px; font-weight: 600; color: #2c3e50; text-align: left; }}
            table td {{ padding: 15px; border-bottom: 1px solid #e9ecef; }}
            table tbody tr:hover {{ background-color: #f8f9fa; }}
            .playing-row {{ background-color: #e3f2fd !important; }}
            .play-btn {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 50%; width: 38px; height: 38px; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 0.8em; box-shadow: 0 2px 4px rgba(102,126,234,0.3); transition: all 0.2s; }}
            .play-btn:hover {{ transform: scale(1.1); box-shadow: 0 4px 8px rgba(102,126,234,0.4); }}
            .btn-primary {{ background: #667eea; border: none; color: white; }}
            .btn-primary:hover {{ background: #5568d3; }}
            .btn-danger {{ background: #f56565; border: none; color: white; }}
            .btn-danger:hover {{ background: #e53e3e; }}
            .pagination {{ margin-top: 30px; }}
        </style>
    </head>
    <body>
        <nav class="navbar">
            <div class="navbar-container">
                <a class="navbar-brand" href="/admin">🎓 Admin</a>
                <ul class="nav-menu">
                    <li class="nav-item"><a class="nav-link" href="/admin">Dashboard</a></li>
                    <li class="nav-item"><a class="nav-link active" href="/admin/sentence/list">Sentences</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/reported">Reported</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/users">Users</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/llm-prices">LLM Prices</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/llm-models">LLM Models</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/tts-models">TTS Models</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/tts-voices">TTS Voices</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/ai-preferences">AI Preferences</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/generate">Generate</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/caching-stats">Stats</a></li>
                </ul>
                <div class="nav-right">
                    <span title="{current_user.email}">{current_user.email.split("@")[0]}</span>
                    <a class="nav-link" href="/admin/logout">Logout</a>
                </div>
            </div>
        </nav>
        
        <div class="container-main">
            <h1>Sentences ({total})</h1>
            
            <div class="controls">
                <form method="GET" action="/admin/sentence/list" style="flex: 1; display: flex; gap: 10px; flex-wrap: wrap;">
                    <input type="text" name="search" class="form-control" placeholder="Search German, Ukrainian, Topic" value="{search or ''}" style="flex: 1; min-width: 200px;">
                    <select name="level" class="form-control" style="width: auto;">
                        <option value="">All Levels</option>
                        {filter_options_level}
                    </select>
                    <select name="topic" class="form-control" style="width: auto;">
                        <option value="">All Topics</option>
                        {filter_options_topic}
                    </select>
                    <button type="submit" class="btn btn-secondary">Search</button>
                </form>
                <select onchange="changePageSize(this.value)" class="form-control" style="width: auto;">
                    <option value="20" {"selected" if page_size == 20 else ""}>20 items</option>
                    <option value="50" {"selected" if page_size == 50 else ""}>50 items</option>
                    <option value="100" {"selected" if page_size == 100 else ""}>100 items</option>
                </select>
            </div>
            
            <div class="table-responsive">
                <table class="table table-striped table-bordered table-hover">
                    <thead>
                        <tr>
                            <th style="width: 30px;"><input type="checkbox" id="select-all"></th>
                            <th>Play</th>
                            <th>Ukrainian</th>
                            <th>English</th>
                            <th>German</th>
                            <th>ID</th>
                            <th>Level</th>
                            <th>Topic</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
            
            <ul class="pagination">
                {pagination_html}
            </ul>
        </div>
        
        <script>
            let currentAudio = null;
            let currentRow = null;
            let stopPlayback = false;
            
            async function playSequence(btn) {{
                const rowElement = btn.closest('tr');
                const isPauseAction = (currentRow === rowElement);
                
                // Зупинити поточне аудіо
                if (currentAudio) {{
                    currentAudio.pause();
                    currentAudio.onended = null;
                }}
                
                // Очистити попередній рядок
                if (currentRow) {{
                    currentRow.classList.remove('playing-row');
                    const oldBtn = currentRow.querySelector('.play-btn');
                    if (oldBtn) oldBtn.innerHTML = '▶';
                }}
                
                // Якщо клік на той самий рядок - припинити
                stopPlayback = true;
                await new Promise(r => setTimeout(r, 50));
                
                if (isPauseAction) {{
                    currentRow = null;
                    currentAudio = null;
                    return;
                }}
                
                // Почати програвання з цього рядка та наступних
                stopPlayback = false;
                let activeRow = rowElement;
                
                while (activeRow && !stopPlayback) {{
                    // Отримуємо кнопку для поточного рядка
                    const btn_elem = activeRow.querySelector('.play-btn');
                    if (!btn_elem) break;
                    
                    currentRow = activeRow;
                    activeRow.classList.add('playing-row');
                    btn_elem.innerHTML = '⏸';
                    
                    // Отримуємо всі аудіо URL'и з data атрибутів рядка
                    const row_urls = [];
                    const uk_url = activeRow.getAttribute('data-audio-uk');
                    const en_url = activeRow.getAttribute('data-audio-en');
                    const de_url = activeRow.getAttribute('data-audio-de');
                    
                    if (uk_url && uk_url !== "''") row_urls.push(uk_url);
                    if (en_url && en_url !== "''") row_urls.push(en_url);
                    if (de_url && de_url !== "''") row_urls.push(de_url);
                    
                    // Програємо 3 мови для ЦЬОГО рядка
                    for (const url of row_urls) {{
                        if (stopPlayback) break;
                        if (!url) continue;
                        
                        await new Promise((resolve) => {{
                            currentAudio = new Audio(url);
                            currentAudio.onended = resolve;
                            currentAudio.onerror = resolve;
                            currentAudio.play();
                        }});
                        
                        if (stopPlayback) break;
                        await new Promise(r => setTimeout(r, 500));
                    }}
                    
                    if (stopPlayback) break;
                    
                    // Очистити розмітку з поточного рядка
                    activeRow.classList.remove('playing-row');
                    btn_elem.innerHTML = '▶';
                    
                    // Переходимо на наступний TR рядок
                    do {{
                        activeRow = activeRow.nextElementSibling;
                    }} while (activeRow && activeRow.tagName !== 'TR');
                }}
                
                currentRow = null;
                currentAudio = null;
                stopPlayback = false;
            }}
            
            function changePageSize(size) {{
                window.location.href = '/admin/sentence/list?page=1&page_size=' + size;
            }}
            
            document.getElementById('select-all').addEventListener('change', function() {{
                const checkboxes = document.querySelectorAll('input[name="rowid"]');
                checkboxes.forEach(cb => cb.checked = this.checked);
            }});
        </script>
    </body>
    </html>
    """
    return html


@router.get("/reported", response_class=HTMLResponse)
async def reported_sentences(
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """List reported sentences"""
    result = await db.execute(select(Sentence).where(Sentence.reported == 1))
    sentences = result.scalars().all()
    
    rows_html = ""
    for s in sentences:
        audio_urls = [s.audio_uk, s.audio_en, s.audio_de]
        audio_urls = [f"'/static/audio/sentences/{url}'" for url in audio_urls if url]
        
        uk_audio = f"'/static/audio/sentences/{s.audio_uk}'" if s.audio_uk else "''"
        en_audio = f"'/static/audio/sentences/{s.audio_en}'" if s.audio_en else "''"
        de_audio = f"'/static/audio/sentences/{s.audio_de}'" if s.audio_de else "''"
        
        rows_html += f"""
        <tr data-audio-uk={uk_audio} data-audio-en={en_audio} data-audio-de={de_audio}>
            <td class="col-play"><button class="play-btn" onclick="playSequence(this)">▶</button></td>
            <td>{s.text_de or ''}</td>
            <td>{s.text_en or ''}</td>
            <td>{s.text_uk or ''}</td>
            <td>{s.topic or ''}</td>
            <td>
                <div style="display: flex; gap: 8px;">
                    <a href="/admin/sentence/{s.id}/edit" class="btn btn-primary action-btn" title="Edit">
                        <span class="material-symbols-outlined">edit</span>
                    </a>
                    <button type="button" class="btn btn-warning action-btn" title="Un-report" onclick="unreportSentence({s.id}, this)">✓</button>
                    <form action="/admin/sentence/{s.id}/delete" method="POST" style="display:inline;">
                        <button type="submit" class="btn btn-danger action-btn" title="Delete">
                            <span class="material-symbols-outlined">delete</span>
                        </button>
                    </form>
                </div>
            </td>
        </tr>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Reported Sentences</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" rel="stylesheet">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto; background-color: #f5f7fa; }}
            .navbar {{display: block!important; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 30px; }}
            .navbar-container {{ display: flex; align-items: center; justify-content: flex-start; padding: 0 30px; height: 50px; gap: 40px; }}
            .navbar-brand {{ font-size: 1.5em; font-weight: 700; color: white; text-decoration: none; display: flex; align-items: center; gap: 10px; white-space: nowrap; }}
            .navbar-brand:hover {{ color: #f0f0f0; }}
            .nav-menu {{ display: flex; gap: 0; list-style: none; margin: 0; padding: 0; }}
            .nav-item {{ position: relative; }}
            .nav-link {{ color: rgba(255,255,255,0.9); text-decoration: none; padding: 15px 12px; font-size: 0.9em; font-weight: 500; transition: all 0.3s; border-bottom: 3px solid transparent; height: 50px; display: flex; align-items: center; white-space: nowrap; }}
            .nav-link:hover {{ color: white; background-color: rgba(255,255,255,0.1); border-bottom-color: rgba(255,255,255,0.3); }}
            .nav-link.active {{ color: white; background-color: rgba(255,255,255,0.15); border-bottom-color: white; }}
            .nav-right {{ display: flex; gap: 8px; align-items: center; margin-left: auto; color: white; font-size: 0.85em; white-space: nowrap; }}
            .nav-right a.nav-link {{ padding: 8px 12px; height: auto; border-bottom: none; }}
            .container-main {{ max-width: 1400px; margin: 0 auto; padding: 0 30px; }}
            h1 {{ font-size: 2em; color: #2c3e50; margin-bottom: 30px; font-weight: 700; }}
            .table-responsive {{ background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); overflow: hidden; }}
            table {{ margin: 0; width: 100%; }}
            table thead {{ background-color: #f8f9fa; border-bottom: 2px solid #e9ecef; }}
            table th {{ padding: 15px; font-weight: 600; color: #2c3e50; text-align: left; }}
            table td {{ padding: 15px; border-bottom: 1px solid #e9ecef; }}
            table tbody tr:hover {{ background-color: #f8f9fa; }}
            .playing-row {{ background-color: #e3f2fd !important; }}
            .play-btn {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 50%; width: 38px; height: 38px; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 0.8em; box-shadow: 0 2px 4px rgba(102,126,234,0.3); transition: all 0.2s; }}
            .play-btn:hover {{ transform: scale(1.1); box-shadow: 0 4px 8px rgba(102,126,234,0.4); }}
            .btn-primary {{ background: #667eea; border: none; color: white; }}
            .btn-primary:hover {{ background: #5568d3; }}
            .btn-danger {{ background: #f56565; border: none; color: white; }}
            .btn-danger:hover {{ background: #e53e3e; }}
            .btn-warning {{ background: #f39c12; border: none; color: white; }}
            .btn-warning:hover {{ background: #d68910; }}
            .action-btn {{ width: 36px; height: 36px; padding: 0; display: inline-flex; align-items: center; justify-content: center; border-radius: 6px; }}
        </style>
    </head>
    <body>
        <nav class="navbar">
            <div class="navbar-container">
                <a class="navbar-brand" href="/admin">🎓 Admin</a>
                <ul class="nav-menu">
                    <li class="nav-item"><a class="nav-link" href="/admin">Dashboard</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/sentence/list">Sentences</a></li>
                    <li class="nav-item"><a class="nav-link active" href="/admin/reported">Reported</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/users">Users</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/llm-prices">LLM Prices</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/llm-models">LLM Models</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/tts-models">TTS Models</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/tts-voices">TTS Voices</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/ai-preferences">AI Preferences</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/generate">Generate</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/caching-stats">Stats</a></li>
                </ul>
                <div class="nav-right">
                    <span title="{current_user.email}">{current_user.email.split("@")[0]}</span>
                    <a class="nav-link" href="/admin/logout">Logout</a>
                </div>
            </div>
        </nav>
        
        <div class="container-main">
            <h1>Reported Sentences ({len(sentences)})</h1>
            <div class="table-responsive">
                <table class="table table-striped table-bordered table-hover">
                    <thead>
                        <tr>
                            <th>Play</th>
                            <th>German</th>
                            <th>English</th>
                            <th>Ukrainian</th>
                            <th>Topic</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
        </div>
        
        <script>
            let currentAudio = null;
            let currentRow = null;
            let stopPlayback = false;
            
            async function playSequence(btn) {{
                const rowElement = btn.closest('tr');
                const isPauseAction = (currentRow === rowElement);
                
                if (currentAudio) {{
                    currentAudio.pause();
                    currentAudio.onended = null;
                }}
                
                if (currentRow) {{
                    currentRow.classList.remove('playing-row');
                    const oldBtn = currentRow.querySelector('.play-btn');
                    if (oldBtn) oldBtn.innerHTML = '▶';
                }}
                
                stopPlayback = true;
                await new Promise(r => setTimeout(r, 50));
                
                if (isPauseAction) {{
                    currentRow = null;
                    currentAudio = null;
                    return;
                }}
                
                stopPlayback = false;
                let activeRow = rowElement;
                
                while (activeRow && !stopPlayback) {{
                    const btn_elem = activeRow.querySelector('.play-btn');
                    if (!btn_elem) break;
                    
                    currentRow = activeRow;
                    activeRow.classList.add('playing-row');
                    btn_elem.innerHTML = '⏸';
                    
                    const row_urls = [];
                    const uk_url = activeRow.getAttribute('data-audio-uk');
                    const en_url = activeRow.getAttribute('data-audio-en');
                    const de_url = activeRow.getAttribute('data-audio-de');
                    
                    if (uk_url && uk_url !== "''") row_urls.push(uk_url);
                    if (en_url && en_url !== "''") row_urls.push(en_url);
                    if (de_url && de_url !== "''") row_urls.push(de_url);
                    
                    for (const url of row_urls) {{
                        if (stopPlayback) break;
                        if (!url) continue;
                        
                        await new Promise((resolve) => {{
                            currentAudio = new Audio(url);
                            currentAudio.onended = resolve;
                            currentAudio.onerror = resolve;
                            currentAudio.play();
                        }});
                        
                        if (stopPlayback) break;
                        await new Promise(r => setTimeout(r, 500));
                    }}
                    
                    if (stopPlayback) break;
                    
                    activeRow.classList.remove('playing-row');
                    btn_elem.innerHTML = '▶';
                    
                    do {{
                        activeRow = activeRow.nextElementSibling;
                    }} while (activeRow && activeRow.tagName !== 'TR');
                }}
                
                currentRow = null;
                currentAudio = null;
                stopPlayback = false;
            }}
            
            async function unreportSentence(sentenceId, btn) {{
                try {{
                    const response = await fetch(`/admin/sentence/${{sentenceId}}/unreport`, {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}}
                    }});
                    
                    if (response.ok) {{
                        const row = btn.closest('tr');
                        row.remove();
                    }} else {{
                        alert('Error un-reporting sentence');
                    }}
                }} catch (error) {{
                    alert('Error: ' + error.message);
                }}
            }}
        </script>
    </body>
    </html>
    """
    return html


@router.get("/users", response_class=HTMLResponse)
async def admin_users(
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """List all users"""
    result = await db.execute(select(User))
    users = result.scalars().all()
    
    rows_html = ""
    for u in users:
        rows_html += f"""
        <tr>
            <td>{u.email}</td>
            <td>{u.level}</td>
            <td>{u.credits:.2f}</td>
            <td>{"Yes" if u.is_admin else "No"}</td>
            <td><a href="/admin/user/{u.id}/edit" class="btn btn-sm btn-primary">Edit</a></td>
        </tr>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Users</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" rel="stylesheet">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto; background-color: #f5f7fa; }}
            .navbar {{display: block!important; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 30px; }}
            .navbar-container {{ display: flex; align-items: center; justify-content: flex-start; padding: 0 30px; height: 50px; gap: 40px; }}
            .navbar-brand {{ font-size: 1.5em; font-weight: 700; color: white; text-decoration: none; display: flex; align-items: center; gap: 10px; white-space: nowrap; }}
            .navbar-brand:hover {{ color: #f0f0f0; }}
            .nav-menu {{ display: flex; gap: 0; list-style: none; margin: 0; padding: 0; }}
            .nav-item {{ position: relative; }}
            .nav-link {{ color: rgba(255,255,255,0.9); text-decoration: none; padding: 15px 12px; font-size: 0.9em; font-weight: 500; transition: all 0.3s; border-bottom: 3px solid transparent; height: 50px; display: flex; align-items: center; white-space: nowrap; }}
            .nav-link:hover {{ color: white; background-color: rgba(255,255,255,0.1); border-bottom-color: rgba(255,255,255,0.3); }}
            .nav-link.active {{ color: white; background-color: rgba(255,255,255,0.15); border-bottom-color: white; }}
            .nav-right {{ display: flex; gap: 8px; align-items: center; margin-left: auto; color: white; font-size: 0.85em; white-space: nowrap; }}
            .nav-right a.nav-link {{ padding: 8px 12px; height: auto; border-bottom: none; }}
            .container-main {{ max-width: 1400px; margin: 0 auto; padding: 0 30px; }}
            h1 {{ font-size: 2em; color: #2c3e50; margin-bottom: 30px; font-weight: 700; }}
            .table-responsive {{ background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); overflow: hidden; }}
            table {{ margin: 0; width: 100%; }}
            table thead {{ background-color: #f8f9fa; border-bottom: 2px solid #e9ecef; }}
            table th {{ padding: 15px; font-weight: 600; color: #2c3e50; text-align: left; }}
            table td {{ padding: 15px; border-bottom: 1px solid #e9ecef; }}
            table tbody tr:hover {{ background-color: #f8f9fa; }}
            .btn-primary {{ background: #667eea; border: none; color: white; }}
            .btn-primary:hover {{ background: #5568d3; }}
        </style>
    </head>
    <body>
        <nav class="navbar">
            <div class="navbar-container">
                <a class="navbar-brand" href="/admin">🎓 Admin</a>
                <ul class="nav-menu">
                    <li class="nav-item"><a class="nav-link" href="/admin">Dashboard</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/sentence/list">Sentences</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/reported">Reported</a></li>
                    <li class="nav-item"><a class="nav-link active" href="/admin/users">Users</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/llm-prices">LLM Prices</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/llm-models">LLM Models</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/tts-models">TTS Models</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/tts-voices">TTS Voices</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/ai-preferences">AI Preferences</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/generate">Generate</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/caching-stats">Stats</a></li>
                </ul>
                <div class="nav-right">
                    <span title="{current_user.email}">{current_user.email.split("@")[0]}</span>
                    <a class="nav-link" href="/admin/logout">Logout</a>
                </div>
            </div>
        </nav>
        
        <div class="container-main">
            <h1>Users ({len(users)})</h1>
            <div class="table-responsive">
                <table class="table table-striped table-bordered table-hover">
                    <thead>
                        <tr>
                            <th>Email</th>
                            <th>Level</th>
                            <th>Credits</th>
                            <th>Admin</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>{rows_html}</tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """
    return html


@router.get("/user/{user_id}/edit", response_class=HTMLResponse)
async def edit_user(
    user_id: str,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Edit user form"""
    try:
        # Validate UUID format but use string for DB query
        uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Edit User</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto; background-color: #f5f7fa; }}
            .navbar {{display: block!important; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 30px; }}
            .navbar-container {{ display: flex; align-items: center; justify-content: flex-start; padding: 0 30px; height: 50px; gap: 40px; }}
            .navbar-brand {{ font-size: 1.5em; font-weight: 700; color: white; text-decoration: none; display: flex; align-items: center; gap: 10px; white-space: nowrap; }}
            .navbar-brand:hover {{ color: #f0f0f0; }}
            .nav-menu {{ display: flex; gap: 0; list-style: none; margin: 0; padding: 0; }}
            .nav-item {{ position: relative; }}
            .nav-link {{ color: rgba(255,255,255,0.9); text-decoration: none; padding: 15px 12px; font-size: 0.9em; font-weight: 500; transition: all 0.3s; border-bottom: 3px solid transparent; height: 50px; display: flex; align-items: center; white-space: nowrap; }}
            .nav-link:hover {{ color: white; background-color: rgba(255,255,255,0.1); border-bottom-color: rgba(255,255,255,0.3); }}
            .nav-link.active {{ color: white; background-color: rgba(255,255,255,0.15); border-bottom-color: white; }}
            .nav-right {{ display: flex; gap: 8px; align-items: center; margin-left: auto; color: white; font-size: 0.85em; white-space: nowrap; }}
            .nav-right a.nav-link {{ padding: 8px 12px; height: auto; border-bottom: none; }}
            .container-main {{ max-width: 600px; margin: 0 auto; padding: 0 30px; }}
            h1 {{ font-size: 2em; color: #2c3e50; margin-bottom: 30px; font-weight: 700; }}
            .card {{ box-shadow: 0 1px 3px rgba(0,0,0,0.05); border: none; }}
            .form-group label {{ font-weight: 600; color: #2c3e50; }}
            .form-control {{ border: 1px solid #ddd; border-radius: 6px; }}
            .form-control:focus {{ border-color: #667eea; box-shadow: 0 0 0 0.2rem rgba(102,126,234,0.25); }}
            .btn-primary {{ background: #667eea; border: none; color: white; }}
            .btn-primary:hover {{ background: #5568d3; }}
            .btn-secondary {{ background: #6c757d; border: none; color: white; }}
            .btn-secondary:hover {{ background: #5a6268; }}
        </style>
    </head>
    <body>
        <nav class="navbar">
            <div class="navbar-container">
                <a class="navbar-brand" href="/admin">🎓 Admin</a>
                <ul class="nav-menu">
                    <li class="nav-item"><a class="nav-link" href="/admin">Dashboard</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/sentence/list">Sentences</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/reported">Reported</a></li>
                    <li class="nav-item"><a class="nav-link active" href="/admin/users">Users</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/llm-prices">LLM Prices</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/llm-models">LLM Models</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/tts-models">TTS Models</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/tts-voices">TTS Voices</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/ai-preferences">AI Preferences</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/generate">Generate</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/caching-stats">Stats</a></li>
                </ul>
                <div class="nav-right">
                    <span title="{current_user.email}">{current_user.email.split("@")[0]}</span>
                    <a class="nav-link" href="/admin/logout">Logout</a>
                </div>
            </div>
        </nav>
        
        <div class="container-main">
            <h1>Edit User #{user_id}</h1>
            <div class="card">
                <div class="card-body">
                    <form method="POST" action="/admin/user/{user_id}/update">
                        <div class="form-group">
                            <label>Email</label>
                            <input type="email" name="email" class="form-control" value="{user.email}" readonly>
                        </div>
                        <div class="form-group">
                            <label>Level</label>
                            <select name="level" class="form-control" required>
                                <option value="">-- Select Level --</option>
                                <option value="A1" {"selected" if user.level == "A1" else ""}>A1</option>
                                <option value="A2" {"selected" if user.level == "A2" else ""}>A2</option>
                                <option value="B1" {"selected" if user.level == "B1" else ""}>B1</option>
                                <option value="B2" {"selected" if user.level == "B2" else ""}>B2</option>
                                <option value="C1" {"selected" if user.level == "C1" else ""}>C1</option>
                                <option value="C2" {"selected" if user.level == "C2" else ""}>C2</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Credits</label>
                            <input type="number" name="credits" class="form-control" step="0.01" value="{user.credits}" required>
                        </div>
                        <div class="form-group">
                            <div class="custom-control custom-checkbox">
                                <input type="checkbox" class="custom-control-input" id="isAdmin" name="is_admin" value="true" {"checked" if user.is_admin else ""}>
                                <label class="custom-control-label" for="isAdmin">
                                    Is Admin
                                </label>
                            </div>
                        </div>
                        <div style="margin-top: 30px;">
                            <button type="submit" class="btn btn-primary">Save</button>
                            <a href="/admin/users" class="btn btn-secondary">Cancel</a>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html


@router.post("/user/{user_id}/update")
async def update_user(
    user_id: str,
    request: Request,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Update user"""
    try:
        # Validate UUID format but use string for DB query
        uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    form = await request.form()
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.level = form.get("level", user.level)
    user.credits = float(form.get("credits", user.credits))
    user.is_admin = form.get("is_admin") == "true"
    
    await db.commit()
    return RedirectResponse(url="/admin/users", status_code=302)


@router.post("/sentence/{sentence_id}/delete")
async def delete_sentence(
    sentence_id: int,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Delete a sentence"""
    result = await db.execute(select(Sentence).where(Sentence.id == sentence_id))
    sentence = result.scalar_one_or_none()
    
    if not sentence:
        raise HTTPException(status_code=404, detail="Sentence not found")
    
    # Delete audio files if they exist
    base_static = os.path.join(os.path.dirname(__file__), "../../static/audio/sentences")
    for audio_path in [sentence.audio_de, sentence.audio_en, sentence.audio_uk]:
        if audio_path:
            full_path = os.path.join(base_static, audio_path)
            try:
                if os.path.exists(full_path):
                    os.remove(full_path)
            except Exception as e:
                print(f"Error deleting file {full_path}: {e}")
    
    # Видалити саму речення
    await db.delete(sentence)
    await db.commit()
    
    return RedirectResponse(url="/admin/reported", status_code=302)


@router.post("/sentence/{sentence_id}/unreport")
async def unreport_sentence(
    sentence_id: int,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Un-report a sentence"""
    result = await db.execute(select(Sentence).where(Sentence.id == sentence_id))
    sentence = result.scalar_one_or_none()
    
    if not sentence:
        raise HTTPException(status_code=404, detail="Sentence not found")
    
    sentence.reported = 0
    await db.commit()
    
    return {"ok": True}


@router.get("/sentence/{sentence_id}/edit", response_class=HTMLResponse)
async def edit_sentence(
    sentence_id: int,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Edit sentence form"""
    result = await db.execute(select(Sentence).where(Sentence.id == sentence_id))
    sentence = result.scalar_one_or_none()
    
    if not sentence:
        raise HTTPException(status_code=404, detail="Sentence not found")
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Edit Sentence</title>
        <meta charset="utf-8">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ padding: 20px; }}
            .navbar {{ background-color: #2c3e50; margin-bottom: 20px; }}
        </style>
    </head>
    <body>
        <nav class="navbar navbar-dark bg-dark">
            <a class="navbar-brand" href="/admin">🎓 DE Tutor Admin</a>
        </nav>
        <div class="container">
            <h1>Edit Sentence #{sentence_id}</h1>
            <form method="POST" action="/admin/sentence/{sentence_id}/update">
                <div class="form-group">
                    <label>German</label>
                    <input type="text" name="text_de" class="form-control" value="{sentence.text_de or ''}">
                </div>
                <div class="form-group">
                    <label>English</label>
                    <input type="text" name="text_en" class="form-control" value="{sentence.text_en or ''}">
                </div>
                <div class="form-group">
                    <label>Ukrainian</label>
                    <input type="text" name="text_uk" class="form-control" value="{sentence.text_uk or ''}">
                </div>
                <div class="form-group">
                    <label>Level</label>
                    <input type="text" name="level" class="form-control" value="{sentence.level or ''}">
                </div>
                <div class="form-group">
                    <label>Topic</label>
                    <input type="text" name="topic" class="form-control" value="{sentence.topic or ''}">
                </div>
                <button type="submit" class="btn btn-primary">Save</button>
                <a href="/admin/sentence/list" class="btn btn-secondary">Cancel</a>
            </form>
        </div>
    </body>
    </html>
    """
    return html


@router.post("/sentence/{sentence_id}/update")
async def update_sentence(
    sentence_id: int,
    request: Request,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Update sentence"""
    form = await request.form()
    result = await db.execute(select(Sentence).where(Sentence.id == sentence_id))
    sentence = result.scalar_one_or_none()
    
    if not sentence:
        raise HTTPException(status_code=404, detail="Sentence not found")
    
    sentence.text_de = form.get("text_de")
    sentence.text_en = form.get("text_en")
    sentence.text_uk = form.get("text_uk")
    sentence.level = form.get("level")
    sentence.topic = form.get("topic")
    
    await db.commit()
    return {"ok": True}


@router.get("/batch/{batch_id}/preview", response_class=HTMLResponse)
async def batch_preview(
    batch_id: int,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Preview temporary sentences in a batch before audio generation"""
    # Отримуємо батч
    result = await db.execute(select(SentenceBatch).where(SentenceBatch.id == batch_id))
    batch = result.scalar_one_or_none()
    
    if not batch:
        return "<h1>Batch not found</h1>"
    
    # Отримуємо тимчасові речення
    result = await db.execute(
        select(TempSentence).where(TempSentence.batch_id == batch_id).order_by(TempSentence.id)
    )
    temp_sentences = result.scalars().all()
    
    # Генеруємо HTML таблицю
    rows_html = ""
    for i, s in enumerate(temp_sentences, 1):
        rows_html += f"""
        <tr>
            <td>{i}</td>
            <td>{s.de}</td>
            <td>{s.en}</td>
            <td>{s.uk}</td>
            <td>{s.topic or ''}</td>
            <td>
                <button class="btn btn-sm btn-warning" onclick="editTempSentence({s.id}, {batch_id})">✏️ Edit</button>
                <button class="btn btn-sm btn-danger" onclick="deleteTempSentence({s.id}, {batch_id})">🗑️ Delete</button>
            </td>
        </tr>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Batch {batch_id} Preview</title>
        <meta charset="utf-8">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ padding: 20px; }}
            .navbar {{ background-color: #2c3e50; margin-bottom: 20px; }}
            table {{ font-size: 14px; }}
        </style>
    </head>
    <body>
        <nav class="navbar navbar-dark bg-dark">
            <a class="navbar-brand" href="/admin">🎓 DE Tutor Admin</a>
        </nav>
        <div class="container-fluid">
            <div class="row mb-3">
                <div class="col-md-8">
                    <h2>Batch {batch.name}</h2>
                    <p><strong>Level:</strong> {batch.level}</p>
                    <p><strong>Status:</strong> <span class="badge badge-info">{batch.status}</span></p>
                    <p><strong>Sentences:</strong> {len(temp_sentences)} of {batch.target_count}</p>
                </div>
                <div class="col-md-4 text-right">
                    <a href="/admin/generate" class="btn btn-secondary">← Back</a>
                    <button id="audio-btn" class="btn {('btn-success' if batch.status == 'text_ready' else 'btn-secondary disabled')}" onclick="generateAudio({batch_id})" {'' if batch.status == 'text_ready' else 'disabled'}>
                        Generate Audio
                    </button>
                </div>
            </div>
            
            <table class="table table-striped table-hover">
                <thead class="thead-dark">
                    <tr>
                        <th>#</th>
                        <th>German</th>
                        <th>English</th>
                        <th>Ukrainian</th>
                        <th>Topic</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
        
        <script>
        function generateAudio(batchId) {{
            if (confirm('Generate audio for this batch? This may take a while...')) {{
                fetch(`/admin/generate-audio/${{batchId}}`, {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}}
                }})
                .then(r => r.json())
                .then(data => {{
                    if (data.ok) {{
                        alert(`Audio generation started for batch ${{batchId}}`);
                        setTimeout(() => location.reload(), 1000);
                    }} else {{
                        alert(`Error: ${{data.error}}`);
                    }}
                }})
                .catch(err => alert(`Error: ${{err}}`));
            }}
        }}

        function deleteTempSentence(sentenceId, batchId) {{
            if (confirm('Delete this sentence?')) {{
                fetch(`/admin/temp-sentence/${{sentenceId}}`, {{
                    method: 'DELETE',
                    headers: {{'Content-Type': 'application/json'}}
                }})
                .then(r => r.json())
                .then(data => {{
                    if (data.ok) {{
                        alert('Sentence deleted');
                        location.reload();
                    }} else {{
                        alert(`Error: ${{data.error}}`);
                    }}
                }})
                .catch(err => alert(`Error: ${{err}}`));
            }}
        }}

        function editTempSentence(sentenceId, batchId) {{
            alert('Edit feature coming soon');
            // TODO: Implement edit modal
        }}
        </script>
    </body>
    </html>
    """
    return html


@router.get("/generate", response_class=HTMLResponse)
async def generate_view(
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Sentence generation interface"""
    result = await db.execute(
        select(SentenceBatch).order_by(SentenceBatch.created_at.desc()).limit(10)
    )
    batches = result.scalars().all()
    
    batches_html = ""
    for batch in batches:
        audio_btn = ""
        if batch.status in ["text_ready", "generating_audio", "audio_ready"]:
            if batch.status == "text_ready":
                audio_btn = f'<button class="btn btn-sm btn-success" onclick="generateAudio({batch.id})">🔊 Generate Audio</button>'
            elif batch.status == "generating_audio":
                audio_btn = f'<button class="btn btn-sm btn-secondary" disabled style="cursor: not-allowed; opacity: 0.6;">⏳ Generating...</button>'
            else:  # audio_ready
                audio_btn = f'<button class="btn btn-sm btn-secondary" disabled style="cursor: not-allowed; opacity: 0.6;">✓ Audio Ready</button>'
        
        status_color = {
            "pending": "secondary",
            "generating": "info",
            "text_ready": "success",
            "generating_audio": "warning",
            "audio_ready": "success"
        }.get(batch.status, "secondary")
        
        batches_html += f"""
        <tr>
            <td><strong>{batch.name}</strong></td>
            <td><span class="badge badge-info">{batch.level}</span></td>
            <td>{batch.target_count}</td>
            <td><span class="badge badge-{status_color}">{batch.status}</span></td>
            <td>
                <a href="/admin/batch/{batch.id}/preview" class="btn btn-sm btn-info">View</a>
                {audio_btn}
                <button class="btn btn-sm btn-danger" onclick="deleteBatch({batch.id}, '{batch.name}')">🗑️ Delete</button>
            </td>
        </tr>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Generate Sentences</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto; background-color: #f5f7fa; }}
            .navbar {{display: block!important; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 30px; }}
            .navbar-container {{ display: flex; align-items: center; justify-content: flex-start; padding: 0 30px; height: 50px; gap: 40px; }}
            .navbar-brand {{ font-size: 1.5em; font-weight: 700; color: white; text-decoration: none; display: flex; align-items: center; gap: 10px; white-space: nowrap; }}
            .navbar-brand:hover {{ color: #f0f0f0; }}
            .nav-menu {{ display: flex; gap: 0; list-style: none; margin: 0; padding: 0; }}
            .nav-item {{ position: relative; }}
            .nav-link {{ color: rgba(255,255,255,0.9); text-decoration: none; padding: 15px 12px; font-size: 0.9em; font-weight: 500; transition: all 0.3s; border-bottom: 3px solid transparent; height: 50px; display: flex; align-items: center; white-space: nowrap; }}
            .nav-link:hover {{ color: white; background-color: rgba(255,255,255,0.1); border-bottom-color: rgba(255,255,255,0.3); }}
            .nav-link.active {{ color: white; background-color: rgba(255,255,255,0.15); border-bottom-color: white; }}
            .nav-right {{ display: flex; gap: 8px; align-items: center; margin-left: auto; color: white; font-size: 0.85em; white-space: nowrap; }}
            .nav-right a.nav-link {{ padding: 8px 12px; height: auto; border-bottom: none; }}
            .container-main {{ max-width: 1400px; margin: 0 auto; padding: 0 30px; }}
            h1 {{ font-size: 2em; color: #2c3e50; margin-bottom: 30px; font-weight: 700; }}
            .card {{ box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
            .table-responsive {{ background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); overflow: hidden; }}
            table {{ margin: 0; width: 100%; }}
            table thead {{ background-color: #f8f9fa; border-bottom: 2px solid #e9ecef; }}
            table th {{ padding: 15px; font-weight: 600; color: #2c3e50; text-align: left; }}
            table td {{ padding: 15px; border-bottom: 1px solid #e9ecef; }}
            table tbody tr:hover {{ background-color: #f8f9fa; }}
            .btn-primary {{ background: #667eea; border: none; color: white; }}
            .btn-primary:hover {{ background: #5568d3; }}
        </style>
    </head>
    <body>
        <nav class="navbar">
            <div class="navbar-container">
                <a class="navbar-brand" href="/admin">🎓 Admin</a>
                <ul class="nav-menu">
                    <li class="nav-item"><a class="nav-link" href="/admin">Dashboard</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/sentence/list">Sentences</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/reported">Reported</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/users">Users</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/llm-prices">LLM Prices</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/llm-models">LLM Models</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/tts-models">TTS Models</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/tts-voices">TTS Voices</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/ai-preferences">AI Preferences</a></li>
                    <li class="nav-item"><a class="nav-link active" href="/admin/generate">Generate</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/caching-stats">Stats</a></li>
                </ul>
                <div class="nav-right">
                    <span title="{current_user.email}">{current_user.email.split("@")[0]}</span>
                    <a class="nav-link" href="/admin/logout">Logout</a>
                </div>
            </div>
        </nav>
        
        <div class="container-main">
            <h1>Generate Sentences & Audio</h1>
            
            <!-- Stage 1: Text Generation -->
            <div class="card" style="margin-top: 20px;">
                <div class="card-header bg-primary text-white">
                    <h5>Stage 1: Generate Sentences</h5>
                </div>
                <div class="card-body">
                    <p>Generate German sentences with translations (DE, EN, UK)</p>
                    <form id="textGenForm" onsubmit="startGeneration(event)">
                        <div class="row">
                            <div class="col-md-6">
                                <div class="form-group">
                                    <label>Level</label>
                                    <select name="level" class="form-control" required>
                                        <option>A1</option>
                                        <option>A2</option>
                                        <option>B1</option>
                                        <option>B2</option>
                                        <option>C1</option>
                                        <option>C2</option>
                                    </select>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="form-group">
                                    <label>Count</label>
                                    <input type="number" name="count" class="form-control" value="10" min="1" max="500" required>
                                </div>
                            </div>
                        </div>
                        <button type="submit" class="btn btn-primary" id="submitBtn">Generate Text</button>
                        <small class="form-text text-muted">This will generate sentences and save them to a batch</small>
                        <div id="genStatus" style="margin-top: 10px; display: none;">
                            <div class="alert alert-info">
                                <strong>Status:</strong> <span id="statusText"></span>
                            </div>
                        </div>
                    </form>
                </div>
            </div>
            
            <!-- Batches List -->
            <h2 style="margin-top: 30px;">Batches</h2>
            <table class="table table-striped table-hover">
                <thead class="thead-dark">
                    <tr>
                        <th>Name</th>
                        <th>Level</th>
                        <th>Count</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>{batches_html}</tbody>
            </table>
            
            <!-- Stage 2: Audio Generation -->
            <div class="card" style="margin-top: 30px;">
                <div class="card-header bg-success text-white">
                    <h5>Stage 2: Generate Audio</h5>
                </div>
                <div class="card-body">
                    <p>Generate audio files (OGG Opus format) for sentences with text_ready status</p>
                    <div class="alert alert-info">
                        <strong>Instructions:</strong>
                        <ol>
                            <li>Generate sentences in Stage 1</li>
                            <li>Review and edit sentences in the batch</li>
                            <li>Once satisfied, click "Generate Audio" button in the batch actions</li>
                        </ol>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
        function generateAudio(batchId) {{
            if (confirm('Generate audio for this batch? This may take a while...')) {{
                fetch(`/admin/generate-audio/${{batchId}}`, {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}}
                }})
                .then(r => r.json())
                .then(data => {{
                    if (data.ok) {{
                        alert(`Audio generation started for batch ${{batchId}}`);
                        setTimeout(() => location.reload(), 1000);
                    }} else {{
                        alert(`Error: ${{data.error}}`);
                    }}
                }})
                .catch(err => alert(`Error: ${{err}}`));
            }}
        }}

        function deleteBatch(batchId, batchName) {{
            if (confirm(`Видалити батч "${{batchName}}" і всі тимчасові речення?`)) {{
                fetch(`/admin/batch/${{batchId}}`, {{
                    method: 'DELETE',
                    headers: {{'Content-Type': 'application/json'}}
                }})
                .then(r => r.json())
                .then(data => {{
                    if (data.ok) {{
                        alert(`Батч видалено`);
                        location.reload();
                    }} else {{
                        alert(`Помилка: ${{data.error}}`);
                    }}
                }})
                .catch(err => alert(`Помилка: ${{err}}`));
            }}
        }}

        function startGeneration(event) {{
            event.preventDefault();
            
            const form = document.getElementById('textGenForm');
            const formData = new FormData(form);
            const level = formData.get('level');
            const count = formData.get('count');
            
            const statusDiv = document.getElementById('genStatus');
            const statusText = document.getElementById('statusText');
            const submitBtn = document.getElementById('submitBtn');
            
            // Показуємо статус
            statusDiv.style.display = 'block';
            statusText.innerHTML = 'Запускаємо генерацію...';
            submitBtn.disabled = true;
            
            fetch('/admin/generate/start', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                body: `level=${{level}}&count=${{count}}`
            }})
            .then(r => r.json())
            .then(data => {{
                if (data.ok) {{
                    statusText.innerHTML = `✓ Генерація батча #${{data.batch_id}} розпочата! Список поновлюється через 3 сек...`;
                    // Перезавантажуємо сторінку щоб побачити новий батч
                    setTimeout(() => location.reload(), 3000);
                }} else {{
                    statusText.innerHTML = `✗ Помилка: ${{data.error}}`;
                    submitBtn.disabled = false;
                }}
            }})
            .catch(err => {{
                statusText.innerHTML = `✗ Помилка: ${{err}}`;
                submitBtn.disabled = false;
            }});
        }}
        </script>
    </body>
    </html>
    """
    return html


@router.delete("/temp-sentence/{sentence_id}")
async def delete_temp_sentence(
    sentence_id: int,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Delete a temporary sentence from a batch"""
    try:
        result = await db.execute(select(TempSentence).where(TempSentence.id == sentence_id))
        temp_sentence = result.scalar_one_or_none()
        
        if not temp_sentence:
            return {"ok": False, "error": "Sentence not found"}
        
        batch_id = temp_sentence.batch_id
        
        # Видаляємо речення
        await db.delete(temp_sentence)
        
        # Оновлюємо processed_count батча
        result = await db.execute(select(SentenceBatch).where(SentenceBatch.id == batch_id))
        batch = result.scalar_one_or_none()
        if batch:
            batch.processed_count = max(0, batch.processed_count - 1)
        
        await db.commit()
        
        return {
            "ok": True,
            "message": f"Sentence {sentence_id} deleted"
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e)
        }


@router.post("/generate/start")
async def start_generation(
    request: Request,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Start a generation batch using subprocess"""
    import subprocess
    import sys
    from pathlib import Path
    import datetime
    import os
    
    try:
        form = await request.form()
        level = form.get("level", "A1").upper()
        count = int(form.get("count", 10))
        
        # Визначаємо правильний Python interpreter (з venv або системний)
        python_executable = sys.executable
        venv_path = Path(sys.prefix) / "bin" / "python"
        if venv_path.exists():
            python_executable = str(venv_path)
        
        # Create initial batch record
        batch = SentenceBatch(
            name=f"{level}_{count}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}",
            level=level,
            target_count=count,
            status="generating"
        )
        db.add(batch)
        await db.commit()
        batch_id = batch.id
        
        # Run generation script in background
        script_path = Path(__file__).parent.parent.parent / "scripts" / "generate_and_save.py"
        
        # Start subprocess (non-blocking)
        subprocess.Popen([
            python_executable,
            str(script_path),
            str(batch_id),
            level,
            str(count)
        ])
        
        return {
            "ok": True,
            "batch_id": batch_id,
            "message": f"Generation started for {count} {level} sentences",
            "status": "generating"
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e)
        }


@router.post("/generate-audio/{batch_id}")
async def start_audio_generation(
    batch_id: int,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Start audio generation for a batch"""
    import subprocess
    import sys
    from pathlib import Path
    
    try:
        # Перевіряємо, що батч існує
        result = await db.execute(select(SentenceBatch).where(SentenceBatch.id == batch_id))
        batch = result.scalar_one_or_none()
        
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        
        # Перевіряємо, що генерація вже не йде
        if batch.status == "generating_audio":
            return {
                "ok": False,
                "error": f"Audio generation is already in progress for batch {batch_id}"
            }
        
        # Перевіряємо, що текст вже було згенеровано
        if batch.status != "text_ready":
            return {
                "ok": False,
                "error": f"Batch must be in 'text_ready' status before audio generation. Current status: {batch.status}"
            }
        
        # Визначаємо правильний Python interpreter (з venv або системний)
        python_executable = sys.executable
        venv_path = Path(sys.prefix) / "bin" / "python"
        if venv_path.exists():
            python_executable = str(venv_path)
        
        # Оновлюємо статус батча
        batch.status = "generating_audio"
        await db.commit()
        
        # Run audio generation script in background
        script_path = Path(__file__).parent.parent.parent / "scripts" / "generate_audio_batch.py"
        
        # Start subprocess (non-blocking)
        subprocess.Popen([
            python_executable,
            str(script_path),
            str(batch_id)
        ])
        
        return {
            "ok": True,
            "batch_id": batch_id,
            "message": f"Audio generation started for batch {batch_id}",
            "status": "generating_audio"
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e)
        }


@router.delete("/batch/{batch_id}")
async def delete_batch(
    batch_id: int,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Delete a batch and all associated temp sentences"""
    from sqlalchemy import delete
    
    try:
        # Отримуємо батч
        result = await db.execute(select(SentenceBatch).where(SentenceBatch.id == batch_id))
        batch = result.scalar_one_or_none()
        
        if not batch:
            return {"ok": False, "error": "Batch not found"}
        
        # Видаляємо всі тимчасові речення батча
        await db.execute(
            delete(TempSentence).where(TempSentence.batch_id == batch_id)
        )
        
        # Видаляємо сам батч
        await db.delete(batch)
        await db.commit()
        
        return {
            "ok": True,
            "message": f"Batch {batch_id} and all temp sentences deleted"
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e)
        }


# ============= AI RESOURCES MANAGEMENT =============

@router.get("/llm-prices", response_class=HTMLResponse)
async def llm_prices_list(
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """LLM Prices management page"""
    result = await db.execute(
        select(LLMPrice)
        .join(LLMModel, LLMPrice.llm_model_id == LLMModel.id)
        .order_by(LLMPrice.id.desc())
    )
    prices = result.scalars().all()
    
    # Отримуємо всі LLM моделі для dropdown
    models_result = await db.execute(select(LLMModel).order_by(LLMModel.human_name))
    llm_models = models_result.scalars().all()
    
    rows_html = ""
    for p in prices:
        status = "✅ Active" if p.is_active else "⏸️ Inactive"
        price_display = f"{p.price_per_unit:g}"
        # Отримуємо ім'я моделі
        model_result = await db.execute(select(LLMModel).where(LLMModel.id == p.llm_model_id))
        model = model_result.scalar_one_or_none()
        model_name = model.human_name if model else "Unknown"
        
        rows_html += f"""
        <tr data-id="{p.id}" data-price="{p.price_per_unit}" data-active="{p.is_active}" data-llm-model-id="{p.llm_model_id}">
            <td>{p.human_name}</td>
            <td>{model_name}</td>
            <td>{p.direction}</td>
            <td>{p.data_type}</td>
            <td>${price_display}</td>
            <td>{status}</td>
            <td>
                <button class="btn btn-sm btn-warning" onclick="editPrice({p.id})">Edit</button>
                <button class="btn btn-sm btn-danger" onclick="deletePrice({p.id})">Delete</button>
            </td>
        </tr>
        """
    
    models_options = "".join([f'<option value="{m.id}">{m.human_name}</option>' for m in llm_models])
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>LLM Prices</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto; background-color: #f5f7fa; }}
            .navbar {{display: block!important; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 30px; }}
            .navbar-container {{ display: flex; align-items: center; justify-content: flex-start; padding: 0 30px; height: 50px; gap: 40px; }}
            .navbar-brand {{ font-size: 1.5em; font-weight: 700; color: white; text-decoration: none; display: flex; align-items: center; gap: 10px; white-space: nowrap; }}
            .navbar-brand:hover {{ color: #f0f0f0; }}
            .nav-menu {{ display: flex; gap: 0; list-style: none; margin: 0; padding: 0; }}
            .nav-item {{ position: relative; }}
            .nav-link {{ color: rgba(255,255,255,0.9); text-decoration: none; padding: 15px 12px; font-size: 0.9em; font-weight: 500; transition: all 0.3s; border-bottom: 3px solid transparent; height: 50px; display: flex; align-items: center; white-space: nowrap; }}
            .nav-link:hover {{ color: white; background-color: rgba(255,255,255,0.1); border-bottom-color: rgba(255,255,255,0.3); }}
            .nav-link.active {{ color: white; background-color: rgba(255,255,255,0.15); border-bottom-color: white; }}
            .nav-right {{ display: flex; gap: 8px; align-items: center; margin-left: auto; color: white; font-size: 0.85em; white-space: nowrap; }}
            .nav-right a.nav-link {{ padding: 8px 12px; height: auto; border-bottom: none; }}
            .container-main {{ max-width: 1400px; margin: 0 auto; padding: 30px; }}
            h1 {{ font-size: 2em; color: #2c3e50; margin-bottom: 30px; font-weight: 700; }}
            .btn-add {{ margin-bottom: 20px; }}
            table {{ background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.05); border-radius: 8px; overflow: hidden; }}
            .modal {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; align-items: center; justify-content: center; overflow: auto; }}
            .modal.show {{ display: flex; }}
            .modal-content {{ background: white; padding: 30px; border-radius: 8px; width: 90%; max-width: 600px; max-height: 90vh; overflow-y: auto; box-shadow: 0 4px 12px rgba(0,0,0,0.15); margin: auto 0; }}
            .modal-header {{ margin-bottom: 20px; font-size: 1.5em; font-weight: 700; }}
            .form-group {{ margin-bottom: 15px; }}
            label {{ font-weight: 600; margin-bottom: 5px; display: block; }}
            input, select {{ width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 1em; }}
            input:focus, select:focus {{ outline: none; border-color: #667eea; box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1); }}
            .modal-footer {{ display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; }}
            .btn {{ padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-weight: 600; }}
            .btn-primary {{ background: #667eea; color: white; }}
            .btn-primary:hover {{ background: #5568d3; }}
            .btn-secondary {{ background: #6c757d; color: white; }}
            .btn-secondary:hover {{ background: #5a6268; }}
            .btn-danger {{ background: #dc3545; color: white; padding: 5px 10px; font-size: 0.85em; }}
            .btn-warning {{ background: #ffc107; color: black; padding: 5px 10px; font-size: 0.85em; }}
        </style>
    </head>
    <body>
        <nav class="navbar">
            <div class="navbar-container">
                <a class="navbar-brand" href="/admin">🎓 Admin</a>
                <ul class="nav-menu">
                    <li class="nav-item"><a class="nav-link" href="/admin">Dashboard</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/sentence/list">Sentences</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/reported">Reported</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/users">Users</a></li>
                    <li class="nav-item"><a class="nav-link active" href="/admin/llm-prices">LLM Prices</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/llm-models">LLM Models</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/tts-models">TTS Models</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/tts-voices">TTS Voices</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/ai-preferences">AI Preferences</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/generate">Generate</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/caching-stats">Stats</a></li>
                </ul>
                <div class="nav-right">
                    <span>{current_user.email.split("@")[0]}</span>
                    <a class="nav-link" href="/admin/logout">Logout</a>
                </div>
            </div>
        </nav>

        <div class="container-main">
            <h1>LLM Prices</h1>
            <button class="btn btn-primary btn-add" onclick="openAddModal()">+ Add LLM Price</button>
            
            <table class="table table-striped table-bordered">
                <thead class="table-dark">
                    <tr>
                        <th>Human Name</th>
                        <th>LLM Model</th>
                        <th>Direction</th>
                        <th>Data Type</th>
                        <th>Price</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html if rows_html else '<tr><td colspan="7" style="text-align: center; padding: 20px; color: #999;">No LLM prices yet. Click "Add" to create one.</td></tr>'}
                </tbody>
            </table>
        </div>

        <!-- Add/Edit Modal -->
        <div id="modal" class="modal">
            <div class="modal-content">
                <div class="modal-header" id="modalTitle">Add LLM Price</div>
                
                <form id="priceForm" onsubmit="submitForm(event)">
                    <input type="hidden" id="priceId" value="">
                    
                    <div class="form-group">
                        <label for="humanName">Human Name *</label>
                        <input type="text" id="humanName" required placeholder="e.g., GPT-4 Input">
                    </div>
                    
                    <div class="form-group">
                        <label for="llmModelId">LLM Model *</label>
                        <select id="llmModelId" required>
                            <option value="">Select LLM Model</option>
                            {models_options}
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="direction">Direction *</label>
                        <select id="direction" required>
                            <option value="">Select direction</option>
                            <option value="input">Input</option>
                            <option value="output">Output</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="dataType">Data Type *</label>
                        <select id="dataType" required>
                            <option value="">Select data type</option>
                            <option value="text">Text</option>
                            <option value="audio">Audio</option>
                            <option value="image">Image</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="pricePerUnit">Price per 1M characters *</label>
                        <input type="number" id="pricePerUnit" step="any" required placeholder="e.g., 0.03 or 23">
                    </div>
                    
                    <div class="form-group">
                        <label>
                            <input type="checkbox" id="isActive" checked> Active
                        </label>
                    </div>
                    
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Save</button>
                    </div>
                </form>
            </div>
        </div>

        <script>
            let editingId = null;
            
            function openAddModal() {{
                editingId = null;
                document.getElementById('priceForm').reset();
                document.getElementById('isActive').checked = true;
                document.getElementById('modalTitle').innerText = 'Add LLM Price';
                document.getElementById('modal').classList.add('show');
            }}
            
            function editPrice(id) {{
                const row = document.querySelector(`tr[data-id="${{id}}"]`);
                if (row) {{
                    const cells = row.querySelectorAll('td');
                    editingId = id;
                    document.getElementById('humanName').value = cells[0].innerText;
                    document.getElementById('llmModelId').value = row.dataset.llmModelId;
                    document.getElementById('direction').value = cells[2].innerText.toLowerCase();
                    document.getElementById('dataType').value = cells[3].innerText.toLowerCase();
                    document.getElementById('pricePerUnit').value = parseFloat(row.dataset.price);
                    document.getElementById('isActive').checked = row.dataset.active === 'True';
                    document.getElementById('modalTitle').innerText = 'Edit LLM Price';
                    document.getElementById('modal').classList.add('show');
                }}
            }}
            
            function closeModal() {{
                document.getElementById('modal').classList.remove('show');
                editingId = null;
            }}
            
            async function submitForm(e) {{
                e.preventDefault();
                const priceValue = document.getElementById('pricePerUnit').value;
                const data = {{
                    human_name: document.getElementById('humanName').value,
                    llm_model_id: parseInt(document.getElementById('llmModelId').value),
                    direction: document.getElementById('direction').value,
                    data_type: document.getElementById('dataType').value,
                    price_per_unit: priceValue ? parseFloat(priceValue) : 0,
                    is_active: document.getElementById('isActive').checked
                }};
                
                try {{
                    const url = editingId 
                        ? `/admin/api/llm-prices/${{editingId}}`
                        : '/admin/api/llm-prices';
                    const method = editingId ? 'PUT' : 'POST';
                    
                    const response = await fetch(url, {{
                        method: method,
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify(data)
                    }});
                    
                    const result = await response.json();
                    if (result.ok) {{
                        location.reload();
                    }} else {{
                        alert('Error: ' + result.error);
                    }}
                }} catch (error) {{
                    alert('Error: ' + error.message);
                }}
            }}
            
            async function deletePrice(id) {{
                if (confirm('Are you sure you want to delete this price?')) {{
                    try {{
                        const response = await fetch(`/admin/api/llm-prices/${{id}}`, {{
                            method: 'DELETE',
                            headers: {{'Content-Type': 'application/json'}}
                        }});
                        
                        const result = await response.json();
                        if (result.ok) {{
                            location.reload();
                        }} else {{
                            alert('Error: ' + result.error);
                        }}
                    }} catch (error) {{
                        alert('Error: ' + error.message);
                    }}
                }}
            }}
        </script>
    </body>
    </html>
    """
    
    return html


# (Removed legacy AI Resources endpoints that referenced non-existent AIResource model)


# ============ LLM MODELS ============

@router.get("/llm-models", response_class=HTMLResponse)
async def llm_models_page(
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """LLM Models management page"""
    result = await db.execute(select(LLMModel).order_by(LLMModel.id.desc()))
    models = result.scalars().all()
    
    rows_html = ""
    for model in models:
        status = "✅ Active" if model.is_active else "⏸️ Inactive"
        rows_html += f"""
        <tr data-model-id="{model.id}" data-model-name="{model.human_name}">
            <td>{model.human_name}</td>
            <td><code>{model.model_id}</code></td>
            <td>{model.provider}</td>
            <td>{status}</td>
            <td>
                <button class="btn btn-sm btn-warning" onclick="editLLMModel({model.id})">Edit</button>
                <button class="btn btn-sm btn-danger" onclick="deleteLLMModel({model.id})">Delete</button>
            </td>
        </tr>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>LLM Models</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto; background-color: #f5f7fa; }}
            .navbar {{ display: block!important; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 30px; }}
            .navbar-container {{ display: flex; align-items: center; justify-content: flex-start; padding: 0 30px; height: 50px; gap: 40px; }}
            .navbar-brand {{ font-size: 1.5em; font-weight: 700; color: white; text-decoration: none; display: flex; align-items: center; gap: 10px; white-space: nowrap; }}
            .navbar-brand:hover {{ color: #f0f0f0; }}
            .nav-menu {{ display: flex; gap: 0; list-style: none; margin: 0; padding: 0; }}
            .nav-item {{ position: relative; }}
            .nav-link {{ color: rgba(255,255,255,0.9); text-decoration: none; padding: 15px 12px; font-size: 0.9em; font-weight: 500; transition: all 0.3s; border-bottom: 3px solid transparent; height: 50px; display: flex; align-items: center; white-space: nowrap; }}
            .nav-link:hover {{ color: white; background-color: rgba(255,255,255,0.1); border-bottom-color: rgba(255,255,255,0.3); }}
            .nav-link.active {{ color: white; background-color: rgba(255,255,255,0.15); border-bottom-color: white; }}
            .nav-right {{ display: flex; gap: 8px; align-items: center; margin-left: auto; color: white; font-size: 0.85em; white-space: nowrap; }}
            .nav-right a.nav-link {{ padding: 8px 12px; height: auto; border-bottom: none; }}
            .container-main {{ max-width: 1400px; margin: 0 auto; padding: 0 30px; }}
            h1 {{ font-size: 2em; color: #2c3e50; margin-bottom: 30px; font-weight: 700; }}
            .btn-add {{ margin-bottom: 20px; }}
            table {{ background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.05); border-radius: 8px; overflow: hidden; }}
            code {{ background: #f5f5f5; padding: 2px 6px; border-radius: 3px; }}
            .modal {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; align-items: center; justify-content: center; overflow: auto; }}
            .modal.show {{ display: flex; }}
            .modal-content {{ background: white; padding: 30px; border-radius: 8px; width: 90%; max-width: 600px; max-height: 90vh; overflow-y: auto; box-shadow: 0 4px 12px rgba(0,0,0,0.15); margin: auto 0; }}
            .modal-header {{ margin-bottom: 20px; font-size: 1.5em; font-weight: 700; }}
            .form-group {{ margin-bottom: 15px; }}
            label {{ font-weight: 600; margin-bottom: 5px; display: block; }}
            input, select {{ width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 1em; }}
            input:focus, select:focus {{ outline: none; border-color: #667eea; box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1); }}
            .modal-footer {{ display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; }}
            .btn {{ padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-weight: 600; }}
            .btn-primary {{ background: #667eea; color: white; }}
            .btn-primary:hover {{ background: #5568d3; }}
            .btn-secondary {{ background: #6c757d; color: white; }}
            .btn-secondary:hover {{ background: #5a6268; }}
            .btn-danger {{ background: #dc3545; color: white; padding: 5px 10px; font-size: 0.85em; }}
            .btn-warning {{ background: #ffc107; color: black; padding: 5px 10px; font-size: 0.85em; }}
        </style>
    </head>
    <body>
        <nav class="navbar">
            <div class="navbar-container">
                <a class="navbar-brand" href="/admin">🎓 Admin</a>
                <ul class="nav-menu">
                    <li class="nav-item"><a class="nav-link" href="/admin">Dashboard</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/sentence/list">Sentences</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/reported">Reported</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/users">Users</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/llm-prices">LLM Prices</a></li>
                    <li class="nav-item"><a class="nav-link active" href="/admin/llm-models">LLM Models</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/tts-models">TTS Models</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/tts-voices">TTS Voices</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/ai-preferences">AI Preferences</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/generate">Generate</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/caching-stats">Stats</a></li>
                </ul>
                <div class="nav-right">
                    <span title="{current_user.email}">{current_user.email.split("@")[0]}</span>
                    <a class="nav-link" href="/admin/logout">Logout</a>
                </div>
            </div>
        </nav>
        
        <div class="container-main">
            <h1>LLM Models & Resources</h1>
            <button class="btn btn-primary btn-add" onclick="openAddModal()">+ Add LLM Model</button>
            
            <table class="table table-striped table-bordered">
                <thead>
                    <tr>
                        <th>Human Name</th>
                        <th>Model ID</th>
                        <th>Provider</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html if rows_html else '<tr><td colspan="5" style="text-align: center; padding: 20px; color: #999;">No LLM models yet. Click "Add" to create one.</td></tr>'}
                </tbody>
            </table>
        </div>
        
        <!-- Modal -->
        <div id="modal" class="modal">
            <div class="modal-content">
                <div class="modal-header" id="modalTitle">Add LLM Model</div>
                <form id="form" onsubmit="submitForm(event)">
                    <div class="form-group">
                        <label>Human Name</label>
                        <input type="text" id="humanName" required placeholder="e.g., GPT-4 Turbo">
                    </div>
                    <div class="form-group">
                        <label>Model ID</label>
                        <input type="text" id="modelId" required placeholder="e.g., gpt-4-turbo">
                    </div>
                    <div class="form-group">
                        <label>Provider</label>
                        <select id="provider" required>
                            <option value="">Select provider</option>
                            <option value="openai">OpenAI</option>
                            <option value="google">Google</option>
                            <option value="azure">Azure</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>
                            <input type="checkbox" id="isActive" checked> Active
                        </label>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Save</button>
                    </div>
                </form>
            </div>
        </div>
        
        <script>
            let editingId = null;
            
            function openAddModal() {{
                editingId = null;
                document.getElementById('modalTitle').innerText = 'Add LLM Model';
                document.getElementById('form').reset();
                document.getElementById('isActive').checked = true;
                document.getElementById('modal').classList.add('show');
            }}
            
            function editLLMModel(id) {{
                // Find model in page and get its data
                const rows = document.querySelectorAll('tbody tr');
                for (let row of rows) {{
                    const cells = row.querySelectorAll('td');
                    if (cells[0]) {{
                        // Parse the row data
                        editingId = id;
                        document.getElementById('humanName').value = cells[0].innerText;
                        document.getElementById('modelId').value = cells[1].innerText.trim();
                        document.getElementById('provider').value = cells[2].innerText.toLowerCase();
                        document.getElementById('isActive').checked = cells[3].innerText.includes('Active');
                        document.getElementById('modalTitle').innerText = 'Edit LLM Model';
                        document.getElementById('modal').classList.add('show');
                        break;
                    }}
                }}
            }}
            
            function closeModal() {{
                document.getElementById('modal').classList.remove('show');
                editingId = null;
            }}
            
            async function submitForm(e) {{
                e.preventDefault();
                const data = {{
                    human_name: document.getElementById('humanName').value,
                    model_id: document.getElementById('modelId').value,
                    provider: document.getElementById('provider').value,
                    is_active: document.getElementById('isActive').checked
                }};
                
                try {{
                    const url = editingId 
                        ? `/admin/api/llm-models/${{editingId}}`
                        : '/admin/api/llm-models';
                    const method = editingId ? 'PUT' : 'POST';
                    
                    const response = await fetch(url, {{
                        method: method,
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify(data)
                    }});
                    
                    const result = await response.json();
                    if (result.ok) {{
                        location.reload();
                    }} else {{
                        alert('Error: ' + result.error);
                    }}
                }} catch (error) {{
                    alert('Error: ' + error);
                }}
            }}
            
            async function deleteLLMModel(id) {{
                const modelRow = document.querySelector(`[data-model-id="${{id}}"]`);
                const modelName = modelRow ? modelRow.getAttribute('data-model-name') : 'Unknown';
                
                const confirmName = prompt(`⚠️ ВАЖЛИВО!\\n\\nВведіть точну назву моделі щоб підтвердити видалення:\\n\\n"${{modelName}}"`);
                
                if (confirmName !== modelName) {{
                    alert('❌ Назва не збігається. Видалення скасовано.');
                    return;
                }}
                
                if (confirm(`Видалити модель "${{modelName}}"? Цю дію неможливо скасувати!`)) {{
                    try {{
                        const response = await fetch(`/admin/api/llm-models/${{id}}`, {{
                            method: 'DELETE'
                        }});
                        const result = await response.json();
                        if (result.ok) {{
                            location.reload();
                        }} else {{
                            alert('Error: ' + result.error);
                        }}
                    }} catch (error) {{
                        alert('Error: ' + error);
                    }}
                }}
            }}
        </script>
    </body>
    </html>
    """
    return html


@router.get("/tts-models", response_class=HTMLResponse)
async def tts_models_page(
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """TTS Models management page"""
    result = await db.execute(select(TTSModel).order_by(TTSModel.id.desc()))
    models = result.scalars().all()
    
    rows_html = ""
    for model in models:
        status = "✅ Active" if model.is_active else "⏸️ Inactive"
        price_display = f"{model.price_per_unit:g}"
        rows_html += f"""
        <tr data-id="{model.id}" data-tts-model-id="{model.id}" data-tts-model-name="{model.human_name}" data-price="{model.price_per_unit}" data-active="{model.is_active}">
            <td>{model.human_name}</td>
            <td>{model.family}</td>
            <td>{model.provider}</td>
            <td>${price_display}</td>
            <td>{status}</td>
            <td>
                <button class="btn btn-sm btn-warning" onclick="editTTSModel({model.id})">Edit</button>
                <button class="btn btn-sm btn-danger" onclick="deleteTTSModel({model.id})">Delete</button>
            </td>
        </tr>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>TTS Models</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto; background-color: #f5f7fa; }}
            .navbar {{ display: block!important; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 30px; }}
            .navbar-container {{ display: flex; align-items: center; justify-content: flex-start; padding: 0 30px; height: 50px; gap: 40px; }}
            .navbar-brand {{ font-size: 1.5em; font-weight: 700; color: white; text-decoration: none; display: flex; align-items: center; gap: 10px; white-space: nowrap; }}
            .navbar-brand:hover {{ color: #f0f0f0; }}
            .nav-menu {{ display: flex; gap: 0; list-style: none; margin: 0; padding: 0; }}
            .nav-item {{ position: relative; }}
            .nav-link {{ color: rgba(255,255,255,0.9); text-decoration: none; padding: 15px 12px; font-size: 0.9em; font-weight: 500; transition: all 0.3s; border-bottom: 3px solid transparent; height: 50px; display: flex; align-items: center; white-space: nowrap; }}
            .nav-link:hover {{ color: white; background-color: rgba(255,255,255,0.1); border-bottom-color: rgba(255,255,255,0.3); }}
            .nav-link.active {{ color: white; background-color: rgba(255,255,255,0.15); border-bottom-color: white; }}
            .nav-right {{ display: flex; gap: 8px; align-items: center; margin-left: auto; color: white; font-size: 0.85em; white-space: nowrap; }}
            .nav-right a.nav-link {{ padding: 8px 12px; height: auto; border-bottom: none; }}
            .container-main {{ max-width: 1400px; margin: 0 auto; padding: 0 30px; }}
            h1 {{ font-size: 2em; color: #2c3e50; margin-bottom: 30px; font-weight: 700; }}
            .btn-add {{ margin-bottom: 20px; }}
            table {{ background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.05); border-radius: 8px; overflow: hidden; }}
            .modal {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; align-items: center; justify-content: center; overflow: auto; }}
            .modal.show {{ display: flex; }}
            .modal-content {{ background: white; padding: 30px; border-radius: 8px; width: 90%; max-width: 600px; max-height: 90vh; overflow-y: auto; box-shadow: 0 4px 12px rgba(0,0,0,0.15); margin: auto 0; }}
            .modal-header {{ margin-bottom: 20px; font-size: 1.5em; font-weight: 700; }}
            .form-group {{ margin-bottom: 15px; }}
            label {{ font-weight: 600; margin-bottom: 5px; display: block; }}
            input, select {{ width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 1em; }}
            input:focus, select:focus {{ outline: none; border-color: #667eea; box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1); }}
            .modal-footer {{ display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; }}
            .btn {{ padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-weight: 600; }}
            .btn-primary {{ background: #667eea; color: white; }}
            .btn-primary:hover {{ background: #5568d3; }}
            .btn-secondary {{ background: #6c757d; color: white; }}
            .btn-secondary:hover {{ background: #5a6268; }}
            .btn-danger {{ background: #dc3545; color: white; padding: 5px 10px; font-size: 0.85em; }}
            .btn-warning {{ background: #ffc107; color: black; padding: 5px 10px; font-size: 0.85em; }}
        </style>
    </head>
    <body>
        <nav class="navbar">
            <div class="navbar-container">
                <a class="navbar-brand" href="/admin">🎓 Admin</a>
                <ul class="nav-menu">
                    <li class="nav-item"><a class="nav-link" href="/admin">Dashboard</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/sentence/list">Sentences</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/reported">Reported</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/users">Users</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/llm-prices">LLM Prices</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/llm-models">LLM Models</a></li>
                    <li class="nav-item"><a class="nav-link active" href="/admin/tts-models">TTS Models</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/tts-voices">TTS Voices</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/ai-preferences">AI Preferences</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/generate">Generate</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/caching-stats">Stats</a></li>
                </ul>
                <div class="nav-right">
                    <span title="{current_user.email}">{current_user.email.split("@")[0]}</span>
                    <a class="nav-link" href="/admin/logout">Logout</a>
                </div>
            </div>
        </nav>
        
        <div class="container-main">
            <h1>TTS Models & Resources</h1>
            <button class="btn btn-primary btn-add" onclick="openAddModal()">+ Add TTS Model</button>
            
            <table class="table table-striped table-bordered">
                <thead>
                    <tr>
                        <th>Human Name</th>
                        <th>Family</th>
                        <th>Provider</th>
                        <th>Price per 1M chars</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html if rows_html else '<tr><td colspan="6" style="text-align: center; padding: 20px; color: #999;">No TTS models yet. Click "Add" to create one.</td></tr>'}
                </tbody>
            </table>
        </div>
        
        <!-- Modal -->
        <div id="modal" class="modal">
            <div class="modal-content">
                <div class="modal-header" id="modalTitle">Add TTS Model</div>
                <form id="form" onsubmit="submitForm(event)">
                    <div class="form-group">
                        <label>Human Name</label>
                        <input type="text" id="humanName" required placeholder="e.g., Google TTS">
                    </div>
                    <div class="form-group">
                        <label>Family</label>
                        <input type="text" id="family" required placeholder="e.g., German, English, Ukrainian">
                    </div>
                    <div class="form-group">
                        <label>Provider</label>
                        <select id="provider" required>
                            <option value="">Select provider</option>
                            <option value="google">Google</option>
                            <option value="azure">Azure</option>
                            <option value="openai">OpenAI</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Price per 1M characters</label>
                        <input type="number" id="pricePerUnit" step="any" required placeholder="e.g., 0.03 or 23">
                    </div>
                    <div class="form-group">
                        <label>
                            <input type="checkbox" id="isActive" checked> Active
                        </label>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Save</button>
                    </div>
                </form>
            </div>
        </div>
        
        <script>
            let editingId = null;
            
            function openAddModal() {{
                editingId = null;
                document.getElementById('modalTitle').innerText = 'Add TTS Model';
                document.getElementById('form').reset();
                document.getElementById('isActive').checked = true;
                document.getElementById('modal').classList.add('show');
            }}
            
            function editTTSModel(id) {{
                const row = document.querySelector(`tr[data-id="${{id}}"]`);
                if (row) {{
                    const cells = row.querySelectorAll('td');
                    editingId = id;
                    document.getElementById('humanName').value = cells[0].innerText;
                    document.getElementById('family').value = cells[1].innerText;
                    document.getElementById('provider').value = cells[2].innerText.toLowerCase();
                    document.getElementById('pricePerUnit').value = parseFloat(row.dataset.price);
                    document.getElementById('isActive').checked = row.dataset.active === 'True';
                    document.getElementById('modalTitle').innerText = 'Edit TTS Model';
                    document.getElementById('modal').classList.add('show');
                }}
            }}
            
            function closeModal() {{
                document.getElementById('modal').classList.remove('show');
                editingId = null;
            }}
            
            async function submitForm(e) {{
                e.preventDefault();
                const priceValue = document.getElementById('pricePerUnit').value;
                const data = {{
                    human_name: document.getElementById('humanName').value,
                    family: document.getElementById('family').value,
                    provider: document.getElementById('provider').value,
                    price_per_unit: priceValue ? parseFloat(priceValue) : 0,
                    is_active: document.getElementById('isActive').checked
                }};
                
                try {{
                    const url = editingId 
                        ? `/admin/api/tts-models/${{editingId}}`
                        : '/admin/api/tts-models';
                    const method = editingId ? 'PUT' : 'POST';
                    
                    const response = await fetch(url, {{
                        method: method,
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify(data)
                    }});
                    
                    const result = await response.json();
                    if (result.ok) {{
                        location.reload();
                    }} else {{
                        alert('Error: ' + result.error);
                    }}
                }} catch (error) {{
                    alert('Error: ' + error);
                }}
            }}
            
            async function deleteTTSModel(id) {{
                const modelRow = document.querySelector(`[data-tts-model-id="${{id}}"]`);
                const modelName = modelRow ? modelRow.getAttribute('data-tts-model-name') : 'Unknown';
                
                const confirmName = prompt(`⚠️ ВАЖЛИВО!\\n\\nВведіть точну назву моделі щоб підтвердити видалення:\\n\\n"${{modelName}}"`);
                
                if (confirmName !== modelName) {{
                    alert('❌ Назва не збігається. Видалення скасовано.');
                    return;
                }}
                
                if (confirm(`Видалити модель "${{modelName}}"? Цю дію неможливо скасувати!`)) {{
                    try {{
                        const response = await fetch(`/admin/api/tts-models/${{id}}`, {{
                            method: 'DELETE'
                        }});
                        const result = await response.json();
                        if (result.ok) {{
                            location.reload();
                        }} else {{
                            alert('Error: ' + result.error);
                        }}
                    }} catch (error) {{
                        alert('Error: ' + error);
                    }}
                }}
            }}
        </script>
    </body>
    </html>
    """
    return html


# LLM Models API endpoints
@router.post("/api/llm-models")
async def create_llm_model(
    data: dict,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Create a new LLM model"""
    try:
        model = LLMModel(
            human_name=data.get("human_name"),
            model_id=data.get("model_id"),
            provider=data.get("provider"),
            is_active=data.get("is_active", True)
        )
        db.add(model)
        await db.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.put("/api/llm-models/{model_id}")
async def update_llm_model(
    model_id: int,
    data: dict,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Update an LLM model"""
    try:
        result = await db.execute(select(LLMModel).where(LLMModel.id == model_id))
        model = result.scalar_one_or_none()
        
        if not model:
            return {"ok": False, "error": "Model not found"}
        
        model.human_name = data.get("human_name", model.human_name)
        model.model_id = data.get("model_id", model.model_id)
        model.provider = data.get("provider", model.provider)
        model.is_active = data.get("is_active", model.is_active)
        
        await db.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.delete("/api/llm-models/{model_id}")
async def delete_llm_model(
    model_id: int,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Delete an LLM model"""
    try:
        result = await db.execute(select(LLMModel).where(LLMModel.id == model_id))
        model = result.scalar_one_or_none()
        
        if not model:
            return {"ok": False, "error": "Model not found"}
        
        await db.delete(model)
        await db.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# TTS Models API endpoints
@router.post("/api/tts-models")
async def create_tts_model(
    data: dict,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Create a new TTS model"""
    try:
        model = TTSModel(
            human_name=data.get("human_name"),
            family=data.get("family"),
            provider=data.get("provider"),
            price_per_unit=data.get("price_per_unit"),
            is_active=data.get("is_active", True)
        )
        db.add(model)
        await db.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.put("/api/tts-models/{model_id}")
async def update_tts_model(
    model_id: int,
    data: dict,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Update a TTS model"""
    try:
        result = await db.execute(select(TTSModel).where(TTSModel.id == model_id))
        model = result.scalar_one_or_none()
        
        if not model:
            return {"ok": False, "error": "Model not found"}
        
        model.human_name = data.get("human_name", model.human_name)
        model.family = data.get("family", model.family)
        model.provider = data.get("provider", model.provider)
        model.price_per_unit = data.get("price_per_unit", model.price_per_unit)
        model.is_active = data.get("is_active", model.is_active)
        
        await db.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.delete("/api/tts-models/{model_id}")
async def delete_tts_model(
    model_id: int,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Delete a TTS model"""
    try:
        result = await db.execute(select(TTSModel).where(TTSModel.id == model_id))
        model = result.scalar_one_or_none()
        
        if not model:
            return {"ok": False, "error": "Model not found"}
        
        await db.delete(model)
        await db.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ============ LLM PRICES ============

@router.post("/api/llm-prices")
async def create_llm_price(
    data: dict,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Create a new LLM price"""
    try:
        price = LLMPrice(
            human_name=data.get("human_name"),
            llm_model_id=data.get("llm_model_id"),
            direction=data.get("direction"),
            data_type=data.get("data_type"),
            price_per_unit=data.get("price_per_unit"),
            is_active=data.get("is_active", True)
        )
        db.add(price)
        await db.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.put("/api/llm-prices/{price_id}")
async def update_llm_price(
    price_id: int,
    data: dict,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Update an LLM price"""
    try:
        result = await db.execute(select(LLMPrice).where(LLMPrice.id == price_id))
        price = result.scalar_one_or_none()
        
        if not price:
            return {"ok": False, "error": "Price not found"}
        
        price.human_name = data.get("human_name", price.human_name)
        price.llm_model_id = data.get("llm_model_id", price.llm_model_id)
        price.direction = data.get("direction", price.direction)
        price.data_type = data.get("data_type", price.data_type)
        price.price_per_unit = data.get("price_per_unit", price.price_per_unit)
        price.is_active = data.get("is_active", price.is_active)
        
        await db.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.delete("/api/llm-prices/{price_id}")
async def delete_llm_price(
    price_id: int,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Delete an LLM price"""
    try:
        result = await db.execute(select(LLMPrice).where(LLMPrice.id == price_id))
        price = result.scalar_one_or_none()
        
        if not price:
            return {"ok": False, "error": "Price not found"}
        
        await db.delete(price)
        await db.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ============ TTS VOICES ============

@router.get("/tts-voices", response_class=HTMLResponse)
async def tts_voices_list(
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """TTS Voices management page"""
    result = await db.execute(
        select(TTSVoice)
        .join(TTSModel, TTSVoice.tts_model_id == TTSModel.id)
        .order_by(TTSVoice.id.desc())
    )
    voices = result.scalars().all()
    
    # Отримуємо всі TTS моделі для dropdown
    models_result = await db.execute(select(TTSModel).order_by(TTSModel.human_name))
    tts_models = models_result.scalars().all()
    
    rows_html = ""
    for v in voices:
        status = "✅ Active" if v.is_active else "⏸️ Inactive"
        # Отримуємо ім'я моделі
        model_result = await db.execute(select(TTSModel).where(TTSModel.id == v.tts_model_id))
        model = model_result.scalar_one_or_none()
        model_name = model.human_name if model else "Unknown"
        
        rows_html += f"""
        <tr data-id="{v.id}" data-active="{v.is_active}" data-tts-model-id="{v.tts_model_id}">
            <td>{v.voice_name}</td>
            <td>{model_name}</td>
            <td>{v.lang}</td>
            <td>{v.gender}</td>
            <td>{status}</td>
            <td>
                <button class="btn btn-sm btn-warning" onclick="editVoice({v.id})">Edit</button>
                <button class="btn btn-sm btn-danger" onclick="deleteVoice({v.id})">Delete</button>
            </td>
        </tr>
        """
    
    if not rows_html:
        rows_html = '<tr><td colspan="6" style="text-align: center; padding: 20px; color: #999;">No TTS voices yet. Click "Add" to create one.</td></tr>'
    
    models_options = "".join([f'<option value="{m.id}">{m.human_name}</option>' for m in tts_models])
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>TTS Voices</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto; background-color: #f5f7fa; }}
            .navbar {{display: block!important; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 30px; }}
            .navbar-container {{ display: flex; align-items: center; justify-content: flex-start; padding: 0 30px; height: 50px; gap: 40px; }}
            .navbar-brand {{ font-size: 1.5em; font-weight: 700; color: white; text-decoration: none; display: flex; align-items: center; gap: 10px; white-space: nowrap; }}
            .navbar-brand:hover {{ color: #f0f0f0; }}
            .nav-menu {{ display: flex; gap: 0; list-style: none; margin: 0; padding: 0; }}
            .nav-item {{ position: relative; }}
            .nav-link {{ color: rgba(255,255,255,0.9); text-decoration: none; padding: 15px 12px; font-size: 0.9em; font-weight: 500; transition: all 0.3s; border-bottom: 3px solid transparent; height: 50px; display: flex; align-items: center; white-space: nowrap; }}
            .nav-link:hover {{ color: white; background-color: rgba(255,255,255,0.1); border-bottom-color: rgba(255,255,255,0.3); }}
            .nav-link.active {{ color: white; background-color: rgba(255,255,255,0.15); border-bottom-color: white; }}
            .nav-right {{ display: flex; gap: 8px; align-items: center; margin-left: auto; color: white; font-size: 0.85em; white-space: nowrap; }}
            .nav-right a.nav-link {{ padding: 8px 12px; height: auto; border-bottom: none; }}
            .container-main {{ max-width: 1400px; margin: 0 auto; padding: 30px; }}
            h1 {{ font-size: 2em; color: #2c3e50; margin-bottom: 30px; font-weight: 700; }}
            .btn-add {{ margin-bottom: 20px; }}
            table {{ background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.05); border-radius: 8px; overflow: hidden; }}
            .modal {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; align-items: center; justify-content: center; overflow: auto; }}
            .modal.show {{ display: flex; }}
            .modal-content {{ background: white; padding: 30px; border-radius: 8px; width: 90%; max-width: 600px; max-height: 90vh; overflow-y: auto; box-shadow: 0 4px 12px rgba(0,0,0,0.15); margin: auto 0; }}
            .modal-header {{ margin-bottom: 20px; font-size: 1.5em; font-weight: 700; }}
            .form-group {{ margin-bottom: 15px; }}
            label {{ font-weight: 600; margin-bottom: 5px; display: block; }}
            input, select {{ width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 1em; }}
            input:focus, select:focus {{ outline: none; border-color: #667eea; box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1); }}
            .modal-footer {{ display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; }}
            .btn {{ padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-weight: 600; }}
            .btn-primary {{ background: #667eea; color: white; }}
            .btn-primary:hover {{ background: #5568d3; }}
            .btn-secondary {{ background: #6c757d; color: white; }}
            .btn-secondary:hover {{ background: #5a6268; }}
            .btn-danger {{ background: #dc3545; color: white; padding: 5px 10px; font-size: 0.85em; }}
            .btn-warning {{ background: #ffc107; color: black; padding: 5px 10px; font-size: 0.85em; }}
        </style>
    </head>
    <body>
        <nav class="navbar">
            <div class="navbar-container">
                <a class="navbar-brand" href="/admin">🎓 Admin</a>
                <ul class="nav-menu">
                    <li class="nav-item"><a class="nav-link" href="/admin">Dashboard</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/sentence/list">Sentences</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/reported">Reported</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/users">Users</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/llm-prices">LLM Prices</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/llm-models">LLM Models</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/tts-models">TTS Models</a></li>
                    <li class="nav-item"><a class="nav-link active" href="/admin/tts-voices">TTS Voices</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/ai-preferences">AI Preferences</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/generate">Generate</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/caching-stats">Stats</a></li>
                </ul>
                <div class="nav-right">
                    <span>{current_user.email.split("@")[0]}</span>
                    <a class="nav-link" href="/admin/logout">Logout</a>
                </div>
            </div>
        </nav>

        <div class="container-main">
            <h1>TTS Voices</h1>
            <button class="btn btn-primary btn-add" onclick="openAddModal()">+ Add TTS Voice</button>
            
            <table class="table table-striped table-bordered">
                <thead class="table-dark">
                    <tr>
                        <th>Voice Name</th>
                        <th>TTS Model</th>
                        <th>Language</th>
                        <th>Gender</th>
                        <th>Status</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>

        <!-- Add/Edit Modal -->
        <div id="modal" class="modal">
            <div class="modal-content">
                <div class="modal-header" id="modalTitle">Add TTS Voice</div>
                
                <form id="voiceForm" onsubmit="submitForm(event)">
                    <input type="hidden" id="voiceId" value="">
                    
                    <div class="form-group">
                        <label for="voiceName">Voice Name *</label>
                        <input type="text" id="voiceName" required placeholder="e.g., de-DE-Standard-A">
                    </div>
                    
                    <div class="form-group">
                        <label for="ttsModelId">TTS Model *</label>
                        <select id="ttsModelId" required>
                            <option value="">Select TTS Model</option>
                            {models_options}
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="lang">Language *</label>
                        <select id="lang" required>
                            <option value="">Select language</option>
                            <option value="EN">English (EN)</option>
                            <option value="DE">German (DE)</option>
                            <option value="UA">Ukrainian (UA)</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="gender">Gender *</label>
                        <select id="gender" required>
                            <option value="">Select gender</option>
                            <option value="male">Male</option>
                            <option value="female">Female</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label>
                            <input type="checkbox" id="isActive" checked> Active
                        </label>
                    </div>
                    
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Save</button>
                    </div>
                </form>
            </div>
        </div>

        <script>
            let editingId = null;
            
            function openAddModal() {{
                editingId = null;
                document.getElementById('voiceForm').reset();
                document.getElementById('isActive').checked = true;
                document.getElementById('modalTitle').innerText = 'Add TTS Voice';
                document.getElementById('modal').classList.add('show');
            }}
            
            function editVoice(id) {{
                const row = document.querySelector(`tr[data-id="${{id}}"]`);
                if (row) {{
                    const cells = row.querySelectorAll('td');
                    editingId = id;
                    document.getElementById('voiceName').value = cells[0].innerText;
                    document.getElementById('ttsModelId').value = row.dataset.ttsModelId;
                    document.getElementById('lang').value = cells[2].innerText;
                    document.getElementById('gender').value = cells[3].innerText.toLowerCase();
                    document.getElementById('isActive').checked = row.dataset.active === 'True';
                    document.getElementById('modalTitle').innerText = 'Edit TTS Voice';
                    document.getElementById('modal').classList.add('show');
                }}
            }}
            
            function closeModal() {{
                document.getElementById('modal').classList.remove('show');
                editingId = null;
            }}
            
            async function submitForm(e) {{
                e.preventDefault();
                const data = {{
                    voice_name: document.getElementById('voiceName').value,
                    tts_model_id: parseInt(document.getElementById('ttsModelId').value),
                    lang: document.getElementById('lang').value,
                    gender: document.getElementById('gender').value,
                    is_active: document.getElementById('isActive').checked
                }};
                
                try {{
                    const url = editingId 
                        ? `/admin/api/tts-voices/${{editingId}}`
                        : '/admin/api/tts-voices';
                    const method = editingId ? 'PUT' : 'POST';
                    
                    const response = await fetch(url, {{
                        method: method,
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify(data)
                    }});
                    
                    const result = await response.json();
                    if (result.ok) {{
                        location.reload();
                    }} else {{
                        alert('Error: ' + result.error);
                    }}
                }} catch (error) {{
                    alert('Error: ' + error.message);
                }}
            }}
            
            async function deleteVoice(id) {{
                if (confirm('Are you sure you want to delete this voice?')) {{
                    try {{
                        const response = await fetch(`/admin/api/tts-voices/${{id}}`, {{
                            method: 'DELETE',
                            headers: {{'Content-Type': 'application/json'}}
                        }});
                        
                        const result = await response.json();
                        if (result.ok) {{
                            location.reload();
                        }} else {{
                            alert('Error: ' + result.error);
                        }}
                    }} catch (error) {{
                        alert('Error: ' + error.message);
                    }}
                }}
            }}
        </script>
    </body>
    </html>
    """
    
    return html


@router.post("/api/tts-voices")
async def create_tts_voice(
    request: Request,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Create a new TTS voice"""
    try:
        data = await request.json()
        
        voice = TTSVoice(
            voice_name=data.get("voice_name"),
            tts_model_id=data.get("tts_model_id"),
            lang=data.get("lang"),
            gender=data.get("gender"),
            is_active=data.get("is_active", True)
        )
        db.add(voice)
        await db.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.put("/api/tts-voices/{voice_id}")
async def update_tts_voice(
    voice_id: int,
    request: Request,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Update a TTS voice"""
    try:
        data = await request.json()
        
        result = await db.execute(select(TTSVoice).where(TTSVoice.id == voice_id))
        voice = result.scalar_one_or_none()
        
        if not voice:
            return {"ok": False, "error": "Voice not found"}
        
        voice.voice_name = data.get("voice_name", voice.voice_name)
        voice.tts_model_id = data.get("tts_model_id", voice.tts_model_id)
        voice.lang = data.get("lang", voice.lang)
        voice.gender = data.get("gender", voice.gender)
        voice.is_active = data.get("is_active", voice.is_active)
        
        await db.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.delete("/api/tts-voices/{voice_id}")
async def delete_tts_voice(
    voice_id: int,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Delete a TTS voice"""
    try:
        result = await db.execute(select(TTSVoice).where(TTSVoice.id == voice_id))
        voice = result.scalar_one_or_none()
        
        if not voice:
            return {"ok": False, "error": "Voice not found"}
        
        await db.delete(voice)
        await db.commit()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ============ AI PREFERENCES - API ENDPOINTS ============

@router.get("/api/ai-preferences/llm-models")
async def get_llm_models(
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Get all LLM models for dropdown"""
    result = await db.execute(select(LLMModel).order_by(LLMModel.human_name))
    models = result.scalars().all()
    return [{"id": m.id, "human_name": m.human_name, "is_active": m.is_active} for m in models]


@router.get("/api/ai-preferences/tts-voices-by-lang")
async def get_tts_voices_by_lang(
    lang: str = Query(...),
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Get TTS voices filtered by language"""
    result = await db.execute(
        select(TTSVoice)
        .where(TTSVoice.lang == lang, TTSVoice.is_active == True)
        .order_by(TTSVoice.gender, TTSVoice.voice_name)
    )
    voices = result.scalars().all()
    return [
        {
            "id": v.id,
            "voice_name": v.voice_name,
            "lang": v.lang,
            "gender": v.gender,
            "is_active": v.is_active
        }
        for v in voices
    ]


@router.get("/api/ai-preferences/tts-voices")
async def get_tts_voices(
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Get all TTS voices for dropdown"""
    result = await db.execute(select(TTSVoice).order_by(TTSVoice.lang, TTSVoice.voice_name))
    voices = result.scalars().all()
    return [
        {
            "id": v.id,
            "voice_name": v.voice_name,
            "lang": v.lang,
            "gender": v.gender,
            "is_active": v.is_active,
            "tts_model_id": v.tts_model_id
        }
        for v in voices
    ]


@router.get("/api/ai-preferences")
async def get_ai_preferences(
    tab: str = Query(None),
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Get AI preferences, optionally filtered by page"""
    result = await db.execute(select(AIPreference).order_by(AIPreference.job))
    prefs = result.scalars().all()
    
    # Filter by page if provided
    if tab:
        prefs = [p for p in prefs if p.page == tab]
    
    return [
        {
            "id": p.id,
            "job": p.job,
            "page": p.page,
            "model_type": p.model_type,
            "lang": p.lang,
            "gender": p.gender,
            "llm_model_id": p.llm_model_id,
            "tts_voice_id": p.tts_voice_id
        }
        for p in prefs
    ]


@router.get("/api/ai-preferences/{pref_id}")
async def get_ai_preference(
    pref_id: int,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Get single AI preference"""
    pref = await db.get(AIPreference, pref_id)
    if not pref:
        return {"ok": False, "error": "Preference not found"}
    
    return {
        "id": pref.id,
        "job": pref.job,
        "page": pref.page,
        "model_type": pref.model_type,
        "lang": pref.lang,
        "gender": pref.gender,
        "llm_model_id": pref.llm_model_id,
        "tts_voice_id": pref.tts_voice_id
    }


@router.post("/api/ai-preferences")
async def create_ai_preference(
    request: Request,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Create new AI preference"""
    try:
        data = await request.json()
        
        # Validate data
        model_type = data.get("model_type")
        page = data.get("page")
        
        if not page or page not in ["texts", "words", "sentences", "speaking"]:
            return {"ok": False, "error": "Invalid page"}
        
        if model_type == "tts":
            if not data.get("tts_voice_id"):
                return {"ok": False, "error": "tts_voice_id required for TTS"}
            if not data.get("lang"):
                return {"ok": False, "error": "lang required for TTS"}
        elif model_type == "llm":
            if not data.get("llm_model_id"):
                return {"ok": False, "error": "llm_model_id required for LLM"}
        else:
            return {"ok": False, "error": "Invalid model_type"}
        
        pref = AIPreference(
            job=data.get("job"),
            page=page,
            model_type=model_type,
            lang=data.get("lang"),
            gender=data.get("gender"),
            llm_model_id=data.get("llm_model_id"),
            tts_voice_id=data.get("tts_voice_id")
        )
        
        db.add(pref)
        await db.commit()
        return {"ok": True, "id": pref.id}
    except Exception as e:
        await db.rollback()
        return {"ok": False, "error": str(e)}


@router.put("/api/ai-preferences/{pref_id}")
async def update_ai_preference(
    pref_id: int,
    request: Request,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Update AI preference"""
    try:
        data = await request.json()
        
        pref = await db.get(AIPreference, pref_id)
        if not pref:
            return {"ok": False, "error": "Preference not found"}
        
        # Validate data
        model_type = data.get("model_type")
        page = data.get("page")
        
        if not page or page not in ["texts", "words", "sentences", "speaking"]:
            return {"ok": False, "error": "Invalid page"}
        
        if model_type == "tts":
            if not data.get("tts_voice_id"):
                return {"ok": False, "error": "tts_voice_id required for TTS"}
            if not data.get("lang"):
                return {"ok": False, "error": "lang required for TTS"}
            # Gender is optional but can be set for TTS
        elif model_type == "llm":
            if not data.get("llm_model_id"):
                return {"ok": False, "error": "llm_model_id required for LLM"}
        else:
            return {"ok": False, "error": "Invalid model_type"}
        
        pref.job = data.get("job", pref.job)
        pref.page = page
        pref.model_type = model_type
        pref.lang = data.get("lang")
        pref.gender = data.get("gender")  # Add gender support
        pref.llm_model_id = data.get("llm_model_id")
        pref.tts_voice_id = data.get("tts_voice_id")
        
        await db.commit()
        return {"ok": True}
    except Exception as e:
        await db.rollback()
        return {"ok": False, "error": str(e)}


@router.delete("/api/ai-preferences/{pref_id}")
async def delete_ai_preference(
    pref_id: int,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Delete AI preference"""
    try:
        pref = await db.get(AIPreference, pref_id)
        if not pref:
            return {"ok": False, "error": "Preference not found"}
        
        await db.delete(pref)
        await db.commit()
        return {"ok": True}
    except Exception as e:
        await db.rollback()
        return {"ok": False, "error": str(e)}


# ============ AI PREFERENCES - PAGE ============

TABS = {
    "texts": {
        "name": "Texts",
        "description": "Model settings for text generation settings, grammar generation options, audio generation for sentences, model prompts"
    },
    "words": {
        "name": "Words",
        "description": "Model settings for words translation and generating audio for words, model prompts"
    },
    "sentences": {
        "name": "Sentences",
        "description": "Model settings for sentences generation, audio generation and model prompts"
    },
    "speaking": {
        "name": "Speaking",
        "description": "Model settings for evaluating speaking, model prompts"
    }
}

@router.get("/ai-preferences", response_class=HTMLResponse)
async def ai_preferences_page(
    tab: str = "texts",
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """AI Preferences admin page"""
    
    # Validate tab
    if tab not in TABS:
        tab = "texts"
    
    current_tab = TABS[tab]
    
    # Generate tab buttons
    tabs_html = ""
    for tab_key, tab_info in TABS.items():
        active_class = "active" if tab_key == tab else ""
        tabs_html += f'<a href="/admin/ai-preferences?tab={tab_key}" class="tab-btn {active_class}">{tab_info["name"]}</a>\n'
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI Preferences</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto; background-color: #f5f7fa; }}
            .navbar {{display: block!important; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 30px; }}
            .navbar-container {{ display: flex; align-items: center; justify-content: flex-start; padding: 0 30px; height: 50px; gap: 40px; }}
            .navbar-brand {{ font-size: 1.5em; font-weight: 700; color: white; text-decoration: none; display: flex; align-items: center; gap: 10px; white-space: nowrap; }}
            .navbar-brand:hover {{ color: #f0f0f0; }}
            .nav-menu {{ display: flex; gap: 0; list-style: none; margin: 0; padding: 0; }}
            .nav-item {{ position: relative; }}
            .nav-link {{ color: rgba(255,255,255,0.9); text-decoration: none; padding: 15px 12px; font-size: 0.9em; font-weight: 500; transition: all 0.3s; border-bottom: 3px solid transparent; height: 50px; display: flex; align-items: center; white-space: nowrap; }}
            .nav-link:hover {{ color: white; background-color: rgba(255,255,255,0.1); border-bottom-color: rgba(255,255,255,0.3); }}
            .nav-link.active {{ color: white; background-color: rgba(255,255,255,0.15); border-bottom-color: white; }}
            .nav-right {{ display: flex; gap: 8px; align-items: center; margin-left: auto; color: white; font-size: 0.85em; white-space: nowrap; }}
            .nav-right a.nav-link {{ padding: 8px 12px; height: auto; border-bottom: none; }}
            .container-main {{ max-width: 1200px; margin: 0 auto; padding: 20px; background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
            
            .tabs-container {{ display: flex; gap: 10px; margin-bottom: 30px; border-bottom: 2px solid #e0e0e0; }}
            .tab-btn {{ padding: 12px 24px; background: none; border: none; cursor: pointer; font-size: 1em; color: #666; border-bottom: 3px solid transparent; transition: 0.3s; }}
            .tab-btn:hover {{ color: #333; }}
            .tab-btn.active {{ color: #667eea; border-bottom-color: #667eea; font-weight: 600; }}
            
            .tab-content {{ display: none; }}
            .tab-content.active {{ display: block; }}
            
            .tab-header {{ margin-bottom: 30px; }}
            .tab-header h2 {{ color: #333; margin-bottom: 15px; font-size: 1.8em; }}
            .tab-header p {{ color: #666; font-size: 1.05em; line-height: 1.6; }}
            
            h1 {{ color: #333; margin-bottom: 30px; font-size: 2.2em; }}
            h2 {{ color: #333; font-size: 1.5em; font-weight: 600; }}
            
            table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
            th {{ background: #f8f9fa; font-weight: 600; color: #333; }}
            tr:hover {{ background: #f8f9fa; }}
            
            .modal {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; align-items: center; justify-content: center; }}
            .modal.show {{ display: flex; }}
            .modal-content {{ background: white; padding: 30px; border-radius: 8px; width: 90%; max-width: 500px; max-height: 90vh; overflow-y: auto; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }}
            .modal-header {{ margin-bottom: 20px; font-size: 1.3em; font-weight: 700; }}
            .form-group {{ margin-bottom: 15px; }}
            label {{ font-weight: 600; margin-bottom: 5px; display: block; color: #333; }}
            input, select {{ width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 1em; }}
            input:focus, select:focus {{ outline: none; border-color: #667eea; box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1); }}
            .modal-footer {{ display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; }}
            .btn-primary {{ background: #667eea; color: white; }}
            .btn-primary:hover {{ background: #5568d3; }}
            .btn-secondary {{ background: #6c757d; color: white; }}
            .btn-secondary:hover {{ background: #5a6268; }}
            .btn-danger {{ background: #dc3545; color: white; padding: 5px 10px; font-size: 0.85em; }}
            .btn-danger:hover {{ background: #c82333; }}
        </style>
    </head>
    <body>
        <nav class="navbar">
            <div class="navbar-container">
                <a class="navbar-brand" href="/admin">🎓 Admin</a>
                <ul class="nav-menu">
                    <li class="nav-item"><a class="nav-link" href="/admin">Dashboard</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/sentence/list">Sentences</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/reported">Reported</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/users">Users</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/llm-prices">LLM Prices</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/llm-models">LLM Models</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/tts-models">TTS Models</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/tts-voices">TTS Voices</a></li>
                    <li class="nav-item"><a class="nav-link active" href="/admin/ai-preferences">AI Preferences</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/generate">Generate</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/caching-stats">Stats</a></li>
                </ul>
                <div class="nav-right">
                    <span>{current_user.email.split("@")[0]}</span>
                    <a class="nav-link" href="/admin/logout">Logout</a>
                </div>
            </div>
        </nav>

        <div class="container-main">
            <h1>⚙️ AI Preferences</h1>
            
            <div class="tabs-container">
                {tabs_html}
            </div>
            
            <!-- TEXTS TAB -->
            <div class="tab-content {('active' if tab == 'texts' else '')}">
                <p>{TABS['texts']['description']}</p>
                <h2 style="margin-top: 30px; margin-bottom: 20px;">Models</h2>
                <button class="btn btn-primary btn-add" onclick="openAddModal('texts')">+ Add Model</button>
                <div id="texts-models-table" style="margin-top: 20px;"></div>
                
                <h2 style="margin-top: 50px; margin-bottom: 20px;">Prompts</h2>
                <button class="btn btn-primary btn-add" onclick="openAddPromptModal('texts')">+ Add Prompt</button>
                <div id="texts-prompts-table" style="margin-top: 20px;"></div>
            </div>
            
            <!-- WORDS TAB -->
            <div class="tab-content {('active' if tab == 'words' else '')}">
                <p>{TABS['words']['description']}</p>
                <h2 style="margin-top: 30px; margin-bottom: 20px;">Models</h2>
                <button class="btn btn-primary btn-add" onclick="openAddModal('words')">+ Add Model</button>
                <div id="words-models-table" style="margin-top: 20px;"></div>
                
                <h2 style="margin-top: 50px; margin-bottom: 20px;">Prompts</h2>
                <button class="btn btn-primary btn-add" onclick="openAddPromptModal('words')">+ Add Prompt</button>
                <div id="words-prompts-table" style="margin-top: 20px;"></div>
            </div>
            
            <!-- SENTENCES TAB -->
            <div class="tab-content {('active' if tab == 'sentences' else '')}">
                <p>{TABS['sentences']['description']}</p>
                <h2 style="margin-top: 30px; margin-bottom: 20px;">Models</h2>
                <div style="display: flex; gap: 10px; align-items: center;">
                    <button class="btn btn-primary btn-add" onclick="openAddModal('sentences')">+ Add Model</button>
                    <button class="btn btn-outline-secondary" style="width: 32px; height: 32px; padding: 0; border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: help;" onclick="showHelpModal('sentences')" title="How to add models?">?</button>
                </div>
                <div id="sentences-models-table" style="margin-top: 20px;"></div>
                
                <h2 style="margin-top: 50px; margin-bottom: 20px;">Prompts</h2>
                <button class="btn btn-primary btn-add" onclick="openAddPromptModal('sentences')">+ Add Prompt</button>
                <div id="sentences-prompts-table" style="margin-top: 20px;"></div>
            </div>
            
            <!-- SPEAKING TAB -->
            <div class="tab-content {('active' if tab == 'speaking' else '')}">
                <p>{TABS['speaking']['description']}</p>
                <h2 style="margin-top: 30px; margin-bottom: 20px;">Models</h2>
                <button class="btn btn-primary btn-add" onclick="openAddModal('speaking')">+ Add Model</button>
                <div id="speaking-models-table" style="margin-top: 20px;"></div>
                
                <h2 style="margin-top: 50px; margin-bottom: 20px;">Prompts</h2>
                <button class="btn btn-primary btn-add" onclick="openAddPromptModal('speaking')">+ Add Prompt</button>
                <div id="speaking-prompts-table" style="margin-top: 20px;"></div>
            </div>
        </div>
        
        <!-- Modal -->
        <div id="modal" class="modal">
            <div class="modal-content">
                <div class="modal-header" id="modalTitle">Add AI Preference</div>
                <form id="form" onsubmit="submitForm(event)">
                    <div class="form-group">
                        <label>Job Name</label>
                        <input type="text" id="job" required placeholder="e.g., tts_de">
                    </div>
                    <!-- Hidden field for page -->
                    <input type="hidden" id="page">
                    <div class="form-group">
                        <label>Model Type</label>
                        <select id="modelType" required onchange="updateModelTypeFields()">
                            <option value="">Select type</option>
                            <option value="tts">TTS</option>
                            <option value="llm">LLM</option>
                        </select>
                    </div>
                    <div class="form-group" id="langGroup" style="display: none;">
                        <label>Language</label>
                        <select id="lang" onchange="loadTTSVoices()">
                            <option value="">Select language</option>
                            <option value="DE">German</option>
                            <option value="EN">English</option>
                            <option value="UA">Ukrainian</option>
                        </select>
                    </div>
                    <div class="form-group" id="genderGroup" style="display: none;">
                        <label>Gender</label>
                        <select id="gender" onchange="loadTTSVoices()">
                            <option value="">Select gender</option>
                            <option value="male">Male</option>
                            <option value="female">Female</option>
                        </select>
                    </div>
                    <div class="form-group" id="ttsVoiceGroup" style="display: none;">
                        <label>TTS Voice</label>
                        <select id="ttsVoiceId"></select>
                    </div>
                    <div class="form-group" id="llmModelGroup" style="display: none;">
                        <label>LLM Model</label>
                        <select id="llmModelId"></select>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" onclick="closeModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Save</button>
                    </div>
                </form>
            </div>
        </div>
        
        <!-- Prompts Modal -->
        <div id="promptModal" class="modal">
            <div class="modal-content">
                <div class="modal-header" id="promptModalTitle">Add Model Prompt</div>
                <form id="promptForm" onsubmit="submitPromptForm(event)">
                    <div class="form-group">
                        <label>Prompt Name</label>
                        <input type="text" id="promptName" required placeholder="e.g., generate_texts_a1">
                    </div>
                    <!-- Hidden field for page -->
                    <input type="hidden" id="promptPage">
                    <div class="form-group">
                        <label>Prompt Text</label>
                        <textarea id="promptText" required placeholder="Enter the prompt..." style="width: 100%; height: 300px; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-family: monospace; font-size: 0.9em;"></textarea>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" onclick="closePromptModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Save</button>
                    </div>
                </form>
            </div>
        </div>
        
        <!-- Fullscreen Prompt Editor Modal -->
        <div id="editorModal" class="modal" style="z-index: 2000;">
            <div class="modal-content" style="width: 95%; height: 95%; max-width: 100%; max-height: 100%; display: flex; flex-direction: column; padding: 0;">
                <div style="padding: 20px; border-bottom: 1px solid #ddd; display: flex; justify-content: space-between; align-items: center; background: #f8f9fa;">
                    <div class="modal-header" id="editorModalTitle" style="margin: 0;">Edit Prompt</div>
                    <button type="button" class="btn btn-secondary" onclick="closeEditorModal()" style="margin: 0;">✕ Close</button>
                </div>
                <div style="flex: 1; overflow: hidden; display: flex; flex-direction: column;">
                    <textarea id="editorText" style="flex: 1; padding: 20px; border: none; font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace; font-size: 13px; line-height: 1.5; resize: none; background: #fafafa; color: #333;"></textarea>
                </div>
                <div style="padding: 20px; border-top: 1px solid #ddd; display: flex; justify-content: flex-end; gap: 10px; background: #f8f9fa;">
                    <button type="button" class="btn btn-secondary" onclick="closeEditorModal()">Cancel</button>
                    <button type="button" class="btn btn-primary" onclick="savePromptEditor()">Save</button>
                </div>
            </div>
        </div>
        
        <!-- Name Edit Modal -->
        <div id="nameEditModal" class="modal">
            <div class="modal-content">
                <div class="modal-header">Edit Prompt Name</div>
                <form id="nameEditForm" onsubmit="submitNameEdit(event)">
                    <div class="form-group">
                        <label>Prompt Name</label>
                        <input type="text" id="nameEditInput" required placeholder="e.g., generate_texts_a1">
                    </div>
                    <input type="hidden" id="nameEditId">
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" onclick="closeNameEditModal()">Cancel</button>
                        <button type="submit" class="btn btn-primary">Save</button>
                    </div>
                </form>
            </div>
        </div>
        
        <script>
            let currentTab = null;
            let editingId = null;
            let allLLMModels = [];
            let allTTSVoices = [];
            let currentlyEditingPromptId = null;
            
            // Load initial data
            async function initData() {{
                try {{
                    const llmRes = await fetch('/admin/api/ai-preferences/llm-models');
                    allLLMModels = await llmRes.json();
                    
                    const ttsRes = await fetch('/admin/api/ai-preferences/tts-voices');
                    allTTSVoices = await ttsRes.json();
                    
                    populateLLMDropdown();
                    loadAllPreferences();
                }} catch (err) {{
                    console.error('Error loading data:', err);
                }}
            }}
            
            function populateLLMDropdown() {{
                const select = document.getElementById('llmModelId');
                select.innerHTML = '<option value="">Select model</option>';
                allLLMModels.forEach(model => {{
                    if (model.is_active) {{
                        select.innerHTML += `<option value="${{model.id}}">${{model.human_name}}</option>`;
                    }}
                }});
            }}
            
            function loadTTSVoices() {{
                const lang = document.getElementById('lang').value;
                const gender = document.getElementById('gender').value;
                const select = document.getElementById('ttsVoiceId');
                select.innerHTML = '<option value="">Select voice</option>';
                allTTSVoices.forEach(voice => {{
                    // Filter by language and gender (gender is optional)
                    const langMatch = voice.lang === lang;
                    const genderMatch = !gender || voice.gender === gender;
                    
                    if (langMatch && genderMatch && voice.is_active) {{
                        select.innerHTML += `<option value="${{voice.id}}">${{voice.voice_name}}</option>`;
                    }}
                }});
            }}
            
            function updateModelTypeFields() {{
                const modelType = document.getElementById('modelType').value;
                const langGroup = document.getElementById('langGroup');
                const genderGroup = document.getElementById('genderGroup');
                const ttsVoiceGroup = document.getElementById('ttsVoiceGroup');
                const llmModelGroup = document.getElementById('llmModelGroup');
                
                if (modelType === 'tts') {{
                    langGroup.style.display = 'block';
                    genderGroup.style.display = 'block';
                    ttsVoiceGroup.style.display = 'block';
                    llmModelGroup.style.display = 'none';
                }} else if (modelType === 'llm') {{
                    langGroup.style.display = 'none';
                    genderGroup.style.display = 'none';
                    ttsVoiceGroup.style.display = 'none';
                    llmModelGroup.style.display = 'block';
                    populateLLMDropdown();
                }} else {{
                    langGroup.style.display = 'none';
                    genderGroup.style.display = 'none';
                    ttsVoiceGroup.style.display = 'none';
                    llmModelGroup.style.display = 'none';
                }}
            }}
            
            function openAddModal(tab) {{
                currentTab = tab;
                editingId = null;
                document.getElementById('modalTitle').innerText = 'Add AI Preference';
                document.getElementById('form').reset();
                document.getElementById('page').value = tab;
                document.getElementById('modelType').value = '';
                updateModelTypeFields();
                document.getElementById('modal').classList.add('show');
            }}
            
            function closeModal() {{
                document.getElementById('modal').classList.remove('show');
                editingId = null;
                currentTab = null;
            }}
            
            function showHelpModal(page) {{
                const helpContent = {{
                    'texts': `
                        <h4>🔧 How Models Are Used for Text Generation</h4>
                        <p><strong>Job Name:</strong> <code>generate_texts</code></p>
                        <p>When you click "Generate Text" in the app, the system:</p>
                        <ol>
                            <li>Looks up <strong>generate_texts</strong> job in AI Preferences</li>
                            <li>Gets the LLM Model you configured (e.g., Gemini Flash 2.5)</li>
                            <li>Uses that model to generate text</li>
                        </ol>
                        <p><strong>Configuration:</strong></p>
                        <ul>
                            <li><strong>Model Type:</strong> LLM (required)</li>
                            <li><strong>Language:</strong> Not used (leave empty)</li>
                            <li><strong>Gender:</strong> Not used (leave empty)</li>
                        </ul>
                        <p><strong>Naming:</strong> Job name must be exactly <code>generate_texts</code></p>
                    `,
                    'words': `
                        <h4>🔧 How Models Are Used for Vocabulary</h4>
                        <p><strong>Job Names:</strong> <code>translate_vocabulary</code>, <code>vocabulary_tts_de</code>, <code>vocabulary_tts_en</code>, <code>vocabulary_tts_ua</code></p>
                        
                        <p><strong>For Translation:</strong></p>
                        <ol>
                            <li>System looks for <code>translate_vocabulary</code> job</li>
                            <li>Gets the LLM Model configured</li>
                            <li>Uses it to translate word definitions</li>
                        </ol>
                        
                        <p><strong>For Audio Generation:</strong></p>
                        <ol>
                            <li>System looks for <code>vocabulary_tts_de</code> (or en/ua)</li>
                            <li>Gets the TTS Voice you configured for that language</li>
                            <li>Uses it to generate audio for that word</li>
                        </ol>
                        
                        <p><strong>Configuration:</strong></p>
                        <ul>
                            <li><strong>translate_vocabulary:</strong> Model Type=LLM, Language=empty, Gender=empty</li>
                            <li><strong>vocabulary_tts_*:</strong> Model Type=TTS, Language=DE/EN/UA, Gender=empty (one voice per language)</li>
                        </ul>
                        
                        <p><strong>Naming Rules:</strong></p>
                        <ul>
                            <li>Translation job: must be <code>translate_vocabulary</code></li>
                            <li>Audio jobs: must be <code>vocabulary_tts_de</code>, <code>vocabulary_tts_en</code>, <code>vocabulary_tts_ua</code></li>
                            <li>Each language gets ONE voice (not multiple like sentences)</li>
                        </ul>
                    `,
                    'sentences': `
                        <h4>🔧 How Models Are Used for Sentence Generation</h4>
                        <p><strong>Job Names:</strong> <code>generate_sentences</code>, <code>sentences_tts_de_male</code>, <code>sentences_tts_de_female</code>, etc.</p>
                        
                        <p><strong>For Text Generation:</strong></p>
                        <ol>
                            <li>System looks for <code>generate_sentences</code> job</li>
                            <li>Gets the LLM Model configured</li>
                            <li>Uses it to generate sentence text</li>
                        </ol>
                        
                        <p><strong>For Audio Generation:</strong></p>
                        <ol>
                            <li>System looks for ALL <code>sentences_tts_*</code> jobs for a language</li>
                            <li>Finds both MALE and FEMALE voices (if configured)</li>
                            <li>For each sentence, randomly picks one voice (50/50 male/female)</li>
                            <li>Generates audio with that voice</li>
                        </ol>
                        <p>↳ This gives <strong>natural variation</strong> — no two sentences sound identical</p>
                        
                        <p><strong>Configuration Rules:</strong></p>
                        <ul>
                            <li><strong>Text generation:</strong> Model Type=LLM, Language=empty, Gender=empty</li>
                            <li><strong>Audio (German):</strong> Model Type=TTS, Language=DE, Gender=male OR female (separate entries)</li>
                            <li><strong>Audio (English):</strong> Model Type=TTS, Language=EN, Gender=male OR female (separate entries)</li>
                            <li><strong>Audio (Ukrainian):</strong> Model Type=TTS, Language=UA, Gender=male OR female (separate entries)</li>
                        </ul>
                        
                        <p><strong>Naming Rules:</strong></p>
                        <ul>
                            <li>Text generation job: must be <code>generate_sentences</code></li>
                            <li>Audio jobs: format is <code>sentences_tts_{{lang}}_{{gender}}</code></li>
                            <li>Examples: <code>sentences_tts_de_male</code>, <code>sentences_tts_en_female</code>, <code>sentences_tts_ua_male</code></li>
                            <li><strong>Add BOTH male and female for each language</strong> to enable voice variation</li>
                        </ul>
                        
                        <p><strong>Pro Tip:</strong> You can add more than 2 voices per language (e.g., male, female, another_male) and the system will randomly rotate through all of them.</p>
                    `,
                    'speaking': `
                        <h4>🔧 How Models Are Used for Speaking Practice</h4>
                        <p><strong>Job Names:</strong> <code>speaking_tts_de_male</code>, <code>speaking_tts_de_female</code>, etc.</p>
                        
                        <p><strong>For Audio Generation:</strong></p>
                        <ol>
                            <li>System looks for ALL <code>speaking_tts_*</code> jobs for a language</li>
                            <li>Finds both MALE and FEMALE voices (if configured)</li>
                            <li>For each speaking prompt, randomly picks one voice</li>
                            <li>Generates audio with that voice</li>
                        </ol>
                        
                        <p><strong>Configuration Rules:</strong></p>
                        <ul>
                            <li><strong>Audio (German):</strong> Model Type=TTS, Language=DE, Gender=male OR female (separate entries)</li>
                            <li><strong>Audio (English):</strong> Model Type=TTS, Language=EN, Gender=male OR female (separate entries)</li>
                            <li><strong>Audio (Ukrainian):</strong> Model Type=TTS, Language=UA, Gender=male OR female (separate entries)</li>
                        </ul>
                        
                        <p><strong>Naming Rules:</strong></p>
                        <ul>
                            <li>Format: <code>speaking_tts_{{lang}}_{{gender}}</code></li>
                            <li>Examples: <code>speaking_tts_de_male</code>, <code>speaking_tts_en_female</code>, <code>speaking_tts_ua_male</code></li>
                            <li><strong>Add BOTH male and female for each language</strong> for voice variation</li>
                        </ul>
                        
                        <p><strong>Note:</strong> Job names matter! System searches by exact job name to find models.</p>
                    `
                }};
                
                const content = helpContent[page] || '<p>Help not available</p>';
                const modal = document.createElement('div');
                modal.className = 'modal show';
                modal.style.display = 'block';
                modal.style.backgroundColor = 'rgba(0,0,0,0.5)';
                modal.innerHTML = `
                    <div class="modal-dialog modal-lg" style="margin: 50px auto;">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title">⚙️ Model Logic & Naming</h5>
                                <button type="button" class="close" onclick="this.closest('.modal').remove()" style="border: none; background: none; font-size: 1.5rem; cursor: pointer;">×</button>
                            </div>
                            <div class="modal-body" style="max-height: 600px; overflow-y: auto;">
                                ${{content}}
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" onclick="this.closest('.modal').remove()">Close</button>
                            </div>
                        </div>
                    </div>
                `;
                document.body.appendChild(modal);
            }}
            
            async function loadAllPreferences() {{
                const tabs = ['texts', 'words', 'sentences', 'speaking'];
                for (const tab of tabs) {{
                    await loadPreferencesForTab(tab);
                }}
            }}
            
            async function loadPreferencesForTab(tab) {{
                const response = await fetch(`/admin/api/ai-preferences?tab=${{tab}}`);
                const prefs = await response.json();
                renderTable(tab, prefs);
            }}
            
            function renderTable(tab, prefs) {{
                const container = document.getElementById(`${{tab}}-models-table`);
                if (!prefs || prefs.length === 0) {{
                    container.innerHTML = '<p style="color: #999; padding: 20px; text-align: center;">No models configured yet</p>';
                    return;
                }}
                
                let html = '<table><thead><tr><th>Job</th><th>Type</th><th>Language</th><th>Gender</th><th>Model</th><th>Actions</th></tr></thead><tbody>';
                prefs.forEach(pref => {{
                    const modelName = pref.model_type === 'tts' 
                        ? (allTTSVoices.find(v => v.id === pref.tts_voice_id)?.voice_name || 'N/A')
                        : (allLLMModels.find(m => m.id === pref.llm_model_id)?.human_name || 'N/A');
                    
                    html += `
                        <tr data-preference-id="${{pref.id}}" data-preference-name="${{pref.job.replace(/"/g, '&quot;').replace(/&/g, '&amp;')}}">
                            <td>${{pref.job}}</td>
                            <td><strong>${{pref.model_type.toUpperCase()}}</strong></td>
                            <td>${{pref.lang || '-'}}</td>
                            <td>${{pref.gender || '-'}}</td>
                            <td>${{modelName}}</td>
                            <td>
                                <button class="btn btn-sm btn-warning" onclick="editPreference(${{pref.id}}, '${{tab}}')">Edit</button>
                                <button class="btn btn-sm btn-danger" onclick="deletePreference(${{pref.id}}, '${{tab}}')">Delete</button>
                            </td>
                        </tr>
                    `;
                }});
                html += '</tbody></table>';
                container.innerHTML = html;
            }}
            
            async function editPreference(id, tab) {{
                const response = await fetch(`/admin/api/ai-preferences/${{id}}`);
                const pref = await response.json();
                
                currentTab = tab;
                editingId = id;
                
                document.getElementById('job').value = pref.job;
                document.getElementById('page').value = pref.page;
                document.getElementById('modelType').value = pref.model_type;
                document.getElementById('lang').value = pref.lang || '';
                document.getElementById('gender').value = pref.gender || '';
                
                updateModelTypeFields();
                
                if (pref.model_type === 'tts') {{
                    await new Promise(resolve => setTimeout(resolve, 100));
                    loadTTSVoices();
                    document.getElementById('ttsVoiceId').value = pref.tts_voice_id || '';
                }} else if (pref.model_type === 'llm') {{
                    document.getElementById('llmModelId').value = pref.llm_model_id || '';
                }}
                
                document.getElementById('modalTitle').innerText = 'Edit AI Preference';
                document.getElementById('modal').classList.add('show');
            }}
            
            async function submitForm(e) {{
                e.preventDefault();
                const data = {{
                    job: document.getElementById('job').value,
                    page: document.getElementById('page').value,
                    model_type: document.getElementById('modelType').value,
                    lang: document.getElementById('lang').value || null,
                    gender: document.getElementById('gender').value || null,
                    llm_model_id: document.getElementById('llmModelId').value ? parseInt(document.getElementById('llmModelId').value) : null,
                    tts_voice_id: document.getElementById('ttsVoiceId').value ? parseInt(document.getElementById('ttsVoiceId').value) : null
                }};
                
                try {{
                    const url = editingId 
                        ? `/admin/api/ai-preferences/${{editingId}}`
                        : '/admin/api/ai-preferences';
                    const method = editingId ? 'PUT' : 'POST';
                    
                    const response = await fetch(url, {{
                        method: method,
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify(data)
                    }});
                    
                    const result = await response.json();
                    if (result.ok) {{
                        const tabToRefresh = currentTab;
                        closeModal();
                        await loadPreferencesForTab(tabToRefresh);
                    }} else {{
                        alert('Error: ' + (result.error || 'Unknown error'));
                    }}
                }} catch (err) {{
                    alert('Error: ' + err.message);
                }}
            }}
            
            async function deletePreference(id, tab) {{
                const prefRow = document.querySelector(`[data-preference-id="${{id}}"]`);
                const prefNameEscaped = prefRow ? prefRow.getAttribute('data-preference-name') : 'Unknown';
                // Декодуємо HTML entities
                const prefName = prefNameEscaped
                    .replace(/&quot;/g, '"')
                    .replace(/&amp;/g, '&');
                
                const confirmName = prompt(`⚠️ ВАЖЛИВО!\\n\\nВведіть точну назву налаштування щоб підтвердити видалення:\\n\\n"${{prefName}}"`);
                
                if (confirmName !== prefName) {{
                    alert('❌ Назва не збігається. Видалення скасовано.');
                    return;
                }}
                
                if (!confirm(`Видалити налаштування "${{prefName}}"? Цю дію неможливо скасувати!`)) return;
                
                try {{
                    const response = await fetch(`/admin/api/ai-preferences/${{id}}`, {{ method: 'DELETE' }});
                    const result = await response.json();
                    if (result.ok) {{
                        await loadPreferencesForTab(tab);
                    }} else {{
                        alert('Error: ' + (result.error || 'Unknown error'));
                    }}
                }} catch (err) {{
                    alert('Error: ' + err.message);
                }}
            }}
            
            // Prompt Management Functions
            async function openAddPromptModal(page) {{
                currentTab = page;
                document.getElementById('promptPage').value = page;
                document.getElementById('promptName').value = '';
                document.getElementById('promptText').value = '';
                document.getElementById('promptModalTitle').textContent = 'Add Prompt for ' + page.toUpperCase();
                document.getElementById('promptModal').classList.add('show');
            }}
            
            function closePromptModal() {{
                document.getElementById('promptModal').classList.remove('show');
            }}
            
            // Prompt Editor Functions
            async function openPromptEditor(promptId, promptName) {{
                try {{
                    const response = await fetch(`/admin/api/model-prompts/${{promptId}}`);
                    const data = await response.json();
                    
                    currentlyEditingPromptId = promptId;
                    document.getElementById('editorText').value = data.prompt;
                    document.getElementById('editorModalTitle').textContent = `Edit Prompt: ${{promptName}}`;
                    document.getElementById('editorModal').classList.add('show');
                }} catch (err) {{
                    alert('Error loading prompt: ' + err.message);
                }}
            }}
            
            function closeEditorModal() {{
                document.getElementById('editorModal').classList.remove('show');
                currentlyEditingPromptId = null;
            }}
            
            async function savePromptEditor() {{
                if (!currentlyEditingPromptId) return;
                
                const newPrompt = document.getElementById('editorText').value;
                
                try {{
                    const response = await fetch(`/admin/api/model-prompts/${{currentlyEditingPromptId}}`, {{
                        method: 'PUT',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{ prompt: newPrompt }})
                    }});
                    
                    const result = await response.json();
                    if (result.ok) {{
                        closeEditorModal();
                        await loadPromptsForTab(currentTab);
                        alert('Prompt saved successfully!');
                    }} else {{
                        alert('Error: ' + (result.error || 'Unknown error'));
                    }}
                }} catch (err) {{
                    alert('Error: ' + err.message);
                }}
            }}
            
            // Name Edit Functions
            async function editPromptName(promptId, promptName) {{
                document.getElementById('nameEditId').value = promptId;
                document.getElementById('nameEditInput').value = promptName;
                document.getElementById('nameEditModal').classList.add('show');
            }}
            
            function closeNameEditModal() {{
                document.getElementById('nameEditModal').classList.remove('show');
            }}
            
            async function submitNameEdit(event) {{
                event.preventDefault();
                const promptId = document.getElementById('nameEditId').value;
                const newName = document.getElementById('nameEditInput').value;
                
                try {{
                    const response = await fetch(`/admin/api/model-prompts/${{promptId}}`, {{
                        method: 'PUT',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{ name: newName }})
                    }});
                    
                    const result = await response.json();
                    if (result.ok) {{
                        closeNameEditModal();
                        await loadPromptsForTab(currentTab);
                        alert('Name updated successfully!');
                    }} else {{
                        alert('Error: ' + (result.error || 'Unknown error'));
                    }}
                }} catch (err) {{
                    alert('Error: ' + err.message);
                }}
            }}
            
            async function submitPromptForm(event) {{
                event.preventDefault();
                const name = document.getElementById('promptName').value;
                const page = document.getElementById('promptPage').value;
                const prompt = document.getElementById('promptText').value;
                
                try {{
                    const response = await fetch('/admin/api/model-prompts', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{ name, page, prompt }})
                    }});
                    
                    const result = await response.json();
                    if (result.ok) {{
                        closePromptModal();
                        await loadPromptsForTab(currentTab);
                    }} else {{
                        alert('Error: ' + (result.error || 'Unknown error'));
                    }}
                }} catch (err) {{
                    alert('Error: ' + err.message);
                }}
            }}
            
            async function loadPromptsForTab(tab) {{
                try {{
                    const tableDiv = document.getElementById(`${{tab}}-prompts-table`);
                    
                    // Skip if element doesn't exist (tab not yet loaded in DOM)
                    if (!tableDiv) {{
                        console.warn(`Element ${{tab}}-prompts-table not found, skipping load`);
                        return;
                    }}
                    
                    const response = await fetch(`/admin/api/model-prompts?page=${{tab}}`);
                    const prompts = await response.json();
                    
                    if (!prompts || prompts.length === 0) {{
                        tableDiv.innerHTML = '<p style="color: #999;">No prompts yet.</p>';
                        return;
                    }}
                    
                    let html = '<table><tr><th>Name</th><th>Preview</th><th>Actions</th></tr>';
                    for (const p of prompts) {{
                        const preview = p.prompt.substring(0, 100) + (p.prompt.length > 100 ? '...' : '');
                        const escapedName = p.name.replace(/"/g, '&quot;').replace(/&/g, '&amp;');
                        html += `
                            <tr data-prompt-id="${{p.id}}" data-prompt-name="${{escapedName}}">
                                <td>${{p.name}}</td>
                                <td><small style="color: #666;">${{preview}}</small></td>
                                <td style="display: flex; gap: 5px;">
                                    <button class="btn btn-warning" style="padding: 5px 10px; font-size: 0.85em;" onclick="editPromptName(${{p.id}}, '${{p.name.replace(/'/g, "\\'")}}')">✏️ Name</button>
                                    <button class="btn btn-info" style="padding: 5px 10px; font-size: 0.85em;" onclick="openPromptEditor(${{p.id}}, '${{p.name.replace(/'/g, "\\'")}}')">📝 Prompt</button>
                                    <button class="btn btn-danger" style="padding: 5px 10px; font-size: 0.85em;" onclick="deletePrompt(${{p.id}}, '${{tab}}')">🗑️</button>
                                </td>
                            </tr>
                        `;
                    }}
                    html += '</table>';
                    tableDiv.innerHTML = html;
                }} catch (err) {{
                    console.error('Error loading prompts:', err);
                    alert('Error loading prompts: ' + err.message);
                }}
            }}
            
            async function deletePrompt(id, tab) {{
                const promptRow = document.querySelector(`[data-prompt-id="${{id}}"]`);
                const promptNameEscaped = promptRow ? promptRow.getAttribute('data-prompt-name') : 'Unknown';
                // Декодуємо HTML entities
                const promptName = promptNameEscaped
                    .replace(/&quot;/g, '"')
                    .replace(/&amp;/g, '&');
                
                const confirmName = prompt(`⚠️ ВАЖЛИВО!\\n\\nВведіть точну назву промпту щоб підтвердити видалення:\\n\\n"${{promptName}}"`);
                
                if (confirmName !== promptName) {{
                    alert('❌ Назва не збігається. Видалення скасовано.');
                    return;
                }}
                
                if (!confirm(`Видалити промпт "${{promptName}}"? Цю дію неможливо скасувати!`)) return;
                
                try {{
                    const response = await fetch(`/admin/api/model-prompts/${{id}}`, {{
                        method: 'DELETE'
                    }});
                    
                    const result = await response.json();
                    if (result.ok) {{
                        await loadPromptsForTab(tab);
                    }} else {{
                        alert('Error: ' + (result.error || 'Unknown error'));
                    }}
                }} catch (err) {{
                    alert('Error: ' + err.message);
                }}
            }}
            
            // Load prompts for all tabs on init
            async function loadAllPrompts() {{
                const pages = ['texts', 'words', 'sentences', 'speaking'];
                for (const page of pages) {{
                    const tableDiv = document.getElementById(`${{page}}-prompts-table`);
                    if (tableDiv) {{
                        // Only load prompts for visible tabs
                        await loadPromptsForTab(page);
                    }}
                }}
            }}
            
            // Initialize on page load
            document.addEventListener('DOMContentLoaded', () => {{
                initData();
                
                // Load prompts for the currently active tab
                const urlParams = new URLSearchParams(window.location.search);
                const activeTab = urlParams.get('tab') || 'texts';
                loadPromptsForTab(activeTab);
            }});
        </script>
    </body>
    </html>
    """
    
    return html


# ============================================================================
# MODEL PROMPTS API ENDPOINTS
# ============================================================================

@router.post("/api/model-prompts")
async def create_model_prompt(
    data: ModelPromptCreate,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Create a new model prompt"""
    try:
        new_prompt = ModelPrompt(
            name=data.name,
            page=data.page,
            prompt=data.prompt
        )
        db.add(new_prompt)
        await db.commit()
        return {"ok": True}
    except Exception as e:
        await db.rollback()
        return {"ok": False, "error": str(e)}


@router.get("/api/model-prompts")
async def get_model_prompts(
    page: str = None,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Get model prompts, optionally filtered by page"""
    try:
        query = select(ModelPrompt)
        if page:
            query = query.where(ModelPrompt.page == page)
        
        result = await db.execute(query)
        prompts = result.scalars().all()
        
        return [
            {
                "id": p.id,
                "name": p.name,
                "page": p.page,
                "prompt": p.prompt,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None
            }
            for p in prompts
        ]
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/model-prompts/{prompt_id}")
async def get_model_prompt(
    prompt_id: int,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific model prompt"""
    try:
        result = await db.execute(select(ModelPrompt).where(ModelPrompt.id == prompt_id))
        prompt = result.scalar_one_or_none()
        
        if not prompt:
            return {"error": "Prompt not found"}
        
        return {
            "id": prompt.id,
            "name": prompt.name,
            "page": prompt.page,
            "prompt": prompt.prompt
        }
    except Exception as e:
        return {"error": str(e)}


@router.put("/api/model-prompts/{prompt_id}")
async def update_model_prompt(
    prompt_id: int,
    data: ModelPromptUpdate,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Update a model prompt"""
    try:
        result = await db.execute(select(ModelPrompt).where(ModelPrompt.id == prompt_id))
        prompt = result.scalar_one_or_none()
        
        if not prompt:
            return {"ok": False, "error": "Prompt not found"}
        
        if data.name:
            prompt.name = data.name
        if data.prompt:
            prompt.prompt = data.prompt
        if data.page:
            prompt.page = data.page
        
        await db.commit()
        return {"ok": True}
    except Exception as e:
        await db.rollback()
        return {"ok": False, "error": str(e)}


@router.delete("/api/model-prompts/{prompt_id}")
async def delete_model_prompt(
    prompt_id: int,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Delete a model prompt"""
    try:
        result = await db.execute(select(ModelPrompt).where(ModelPrompt.id == prompt_id))
        prompt = result.scalar_one_or_none()
        
        if not prompt:
            return {"ok": False, "error": "Prompt not found"}
        
        await db.delete(prompt)
        await db.commit()
        return {"ok": True}
    except Exception as e:
        await db.rollback()
        return {"ok": False, "error": str(e)}

