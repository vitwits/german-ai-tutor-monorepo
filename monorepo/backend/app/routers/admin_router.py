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

from ..database import get_db
from ..models import User, Sentence, SentenceBatch, TempSentence, TTSLog, AIResource
from ..dependencies import get_current_user
from ..security import verify_password, create_access_token
from sqlalchemy import delete

router = APIRouter(prefix="/admin", tags=["admin"])

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
            .navbar {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 30px; }}
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
                    <li class="nav-item"><a class="nav-link" href="/admin/ai-models">AI Models</a></li>
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
            .navbar {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 30px; }}
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
                    <li class="nav-item"><a class="nav-link" href="/admin/ai-models">AI Models</a></li>
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
            .navbar {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 30px; }}
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
                    <li class="nav-item"><a class="nav-link" href="/admin/ai-models">AI Models</a></li>
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
                    <form action="/admin/sentence/{s.id}/unreport" method="POST" style="display:inline;">
                        <button type="submit" class="btn btn-warning action-btn" title="Un-report">✓</button>
                    </form>
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
            .navbar {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 30px; }}
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
                    <li class="nav-item"><a class="nav-link" href="/admin/ai-models">AI Models</a></li>
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
            .navbar {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 30px; }}
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
                    <li class="nav-item"><a class="nav-link" href="/admin/ai-models">AI Models</a></li>
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
            .navbar {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 30px; }}
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
                    <li class="nav-item"><a class="nav-link" href="/admin/ai-models">AI Models</a></li>
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
            .navbar {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 30px; }}
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

@router.get("/ai-models", response_class=HTMLResponse)
async def ai_models_list(
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """AI Models management page"""
    result = await db.execute(select(AIResource).order_by(AIResource.created_at.desc()))
    resources = result.scalars().all()
    
    rows_html = ""
    for r in resources:
        status = "✅ Active" if r.is_active else "⛔ Inactive"
        lang_display = r.lang if r.lang else "NULL"
        rows_html += f"""
        <tr>
            <td>{r.id}</td>
            <td>{r.name}</td>
            <td><code>{r.model_id}</code></td>
            <td>{r.type}</td>
            <td>{r.direction}</td>
            <td>{r.data_type}</td>
            <td>${r.price_per_unit}</td>
            <td>{r.provider}</td>
            <td>{lang_display}</td>
            <td>{status}</td>
            <td>
                <button class="btn btn-sm btn-warning" onclick="editResource({r.id})">Edit</button>
                <button class="btn btn-sm btn-danger" onclick="deleteResource({r.id})">Delete</button>
            </td>
        </tr>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI Models</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto; background-color: #f5f7fa; }}
            .navbar {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 0; box-shadow: 0 2px 8px rgba(0,0,0,0.1); margin-bottom: 30px; }}
            .navbar-container {{ display: flex; align-items: center; justify-content: flex-start; padding: 0 30px; height: 50px; gap: 40px; }}
            .navbar-brand {{ font-size: 1.5em; font-weight: 700; color: white; text-decoration: none; display: flex; align-items: center; gap: 10px; }}
            .nav-menu {{ display: flex; gap: 0; list-style: none; margin: 0; padding: 0; }}
            .nav-link {{ color: rgba(255,255,255,0.9); text-decoration: none; padding: 15px 12px; font-size: 0.9em; font-weight: 500; border-bottom: 3px solid transparent; height: 50px; display: flex; align-items: center; }}
            .nav-link.active {{ color: white; background-color: rgba(255,255,255,0.15); border-bottom-color: white; }}
            .nav-right {{ display: flex; gap: 8px; align-items: center; margin-left: auto; color: white; font-size: 0.85em; }}
            .container-main {{ max-width: 1400px; margin: 0 auto; padding: 30px; }}
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
                    <li class="nav-item"><a class="nav-link" href="/admin/users">Users</a></li>
                    <li class="nav-item"><a class="nav-link active" href="/admin/ai-models">AI Models</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/ai-preferences">AI Preferences</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/caching-stats">Stats</a></li>
                </ul>
                <div class="nav-right">
                    <span>{current_user.email.split("@")[0]}</span>
                    <a class="nav-link" href="/admin/logout">Logout</a>
                </div>
            </div>
        </nav>

        <div class="container-main">
            <h1>AI Models & Resources</h1>
            <button class="btn btn-primary btn-add" onclick="openAddModal()">+ Add New Model</button>
            
            <table class="table table-striped">
                <thead class="table-dark">
                    <tr>
                        <th>ID</th>
                        <th>Name</th>
                        <th>Model ID</th>
                        <th>Type</th>
                        <th>Direction</th>
                        <th>Data Type</th>
                        <th>Price (per 1M chars)</th>
                        <th>Provider</th>
                        <th>Language</th>
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
                <div class="modal-header" id="modalTitle">Add New AI Model</div>
                
                <form id="modelForm">
                    <input type="hidden" id="modelId" value="">
                    
                    <div class="form-group">
                        <label for="name">Name (Friendly Name) *</label>
                        <input type="text" id="name" required placeholder="e.g., Gemini 2.5 Flash Lite (Input)">
                    </div>
                    
                    <div class="form-group">
                        <label for="modelIdentifier">Model ID (Code Identifier) *</label>
                        <input type="text" id="modelIdentifier" required placeholder="e.g., gemini-2.5-flash-lite">
                    </div>
                    
                    <div class="form-group">
                        <label for="type">Type *</label>
                        <select id="type" required onchange="updateLanguageFieldVisibility()">
                            <option value="">-- Select --</option>
                            <option value="LLM">LLM</option>
                            <option value="TTS">TTS</option>
                        </select>
                    </div>
                    
                    <div class="form-group" id="langGroup" style="display: none;">
                        <label for="lang">Language (TTS only) *</label>
                        <select id="lang">
                            <option value="">-- Select Language --</option>
                            <option value="DE">DE (Deutsch)</option>
                            <option value="EN">EN (English)</option>
                            <option value="UA">UA (Українська)</option>
                        </select>
                    </div>
                    
                    <div class="form-group" id="langNull" style="color: #999;">
                        Language: <span style="font-style: italic;">NULL (not applicable for LLM)</span>
                    </div>
                    
                    <div class="form-group">
                        <label for="direction">Direction *</label>
                        <select id="direction" required>
                            <option value="">-- Select --</option>
                            <option value="input">input</option>
                            <option value="output">output</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="dataType">Data Type *</label>
                        <select id="dataType" required>
                            <option value="">-- Select --</option>
                            <option value="text">text</option>
                            <option value="audio">audio</option>
                            <option value="image">image</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label for="pricePerUnit">Price per 1M Characters ($) *</label>
                        <input type="number" id="pricePerUnit" required step="0.000001" placeholder="0.1">
                    </div>
                    
                    <div class="form-group">
                        <label for="provider">Provider *</label>
                        <select id="provider" required>
                            <option value="">-- Select --</option>
                            <option value="google">Google</option>
                            <option value="azure">Azure</option>
                            <option value="openai">OpenAI</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label>
                            <input type="checkbox" id="isActive" checked>
                            Is Active
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
            function updateLanguageFieldVisibility() {{
                const type = document.getElementById('type').value;
                const langGroup = document.getElementById('langGroup');
                const langNull = document.getElementById('langNull');
                const langInput = document.getElementById('lang');
                
                if (type === 'TTS') {{
                    langGroup.style.display = 'block';
                    langNull.style.display = 'none';
                    langInput.required = true;
                }} else {{
                    langGroup.style.display = 'none';
                    langNull.style.display = 'block';
                    langInput.required = false;
                    langInput.value = '';
                }}
            }}

            function openAddModal() {{
                document.getElementById('modelId').value = '';
                document.getElementById('modelForm').reset();
                document.getElementById('modalTitle').textContent = 'Add New AI Model';
                document.getElementById('modal').classList.add('show');
            }}

            function closeModal() {{
                document.getElementById('modal').classList.remove('show');
            }}

            async function editResource(id) {{
                try {{
                    const response = await fetch(`/admin/api/ai-models/${{id}}`);
                    const data = await response.json();
                    
                    if (data.ok) {{
                        const model = data.data;
                        document.getElementById('modelId').value = model.id;
                        document.getElementById('name').value = model.name;
                        document.getElementById('modelIdentifier').value = model.model_id;
                        document.getElementById('type').value = model.type;
                        document.getElementById('lang').value = model.lang || '';
                        document.getElementById('direction').value = model.direction;
                        document.getElementById('dataType').value = model.data_type;
                        document.getElementById('pricePerUnit').value = model.price_per_unit;
                        document.getElementById('provider').value = model.provider;
                        document.getElementById('isActive').checked = model.is_active;
                        
                        updateLanguageFieldVisibility();
                        
                        document.getElementById('modalTitle').textContent = 'Edit AI Model';
                        document.getElementById('modal').classList.add('show');
                    }} else {{
                        alert('Error: ' + (data.error || 'Unknown error'));
                    }}
                }} catch (error) {{
                    alert('Error loading model: ' + error.message);
                }}
            }}

            async function deleteResource(id) {{
                if (!confirm('Are you sure you want to delete this model?')) return;
                
                try {{
                    const response = await fetch(`/admin/api/ai-models/${{id}}`, {{ method: 'DELETE' }});
                    const data = await response.json();
                    
                    if (data.ok) {{
                        location.reload();
                    }} else {{
                        alert('Error: ' + (data.error || 'Unknown error'));
                    }}
                }} catch (error) {{
                    alert('Error deleting resource: ' + error.message);
                }}
            }}

            document.getElementById('modelForm').addEventListener('submit', async (e) => {{
                e.preventDefault();
                
                const modelId = document.getElementById('modelId').value;
                const data = {{
                    name: document.getElementById('name').value,
                    model_id: document.getElementById('modelIdentifier').value,
                    type: document.getElementById('type').value,
                    direction: document.getElementById('direction').value,
                    data_type: document.getElementById('dataType').value,
                    price_per_unit: parseFloat(document.getElementById('pricePerUnit').value),
                    provider: document.getElementById('provider').value,
                    lang: document.getElementById('type').value === 'TTS' ? document.getElementById('lang').value : null,
                    is_active: document.getElementById('isActive').checked
                }};
                
                try {{
                    const method = modelId ? 'PUT' : 'POST';
                    const url = modelId ? `/admin/api/ai-models/${{modelId}}` : '/admin/api/ai-models';
                    
                    const response = await fetch(url, {{
                        method: method,
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify(data)
                    }});
                    
                    const result = await response.json();
                    
                    if (result.ok) {{
                        location.reload();
                    }} else {{
                        alert('Error: ' + (result.error || 'Unknown error'));
                    }}
                }} catch (error) {{
                    alert('Error saving model: ' + error.message);
                }}
            }});

            window.onclick = function(event) {{
                const modal = document.getElementById('modal');
                if (event.target == modal) {{
                    closeModal();
                }}
            }}
        </script>
    </body>
    </html>
    """
    return html


# API endpoints for CRUD operations
@router.get("/api/ai-models/{resource_id}")
async def get_ai_model(
    resource_id: int,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Get a single AI model by ID"""
    try:
        result = await db.execute(select(AIResource).where(AIResource.id == resource_id))
        resource = result.scalar_one_or_none()
        
        if not resource:
            return {"ok": False, "error": "Model not found"}
        
        return {
            "ok": True,
            "data": {
                "id": resource.id,
                "name": resource.name,
                "model_id": resource.model_id,
                "type": resource.type,
                "direction": resource.direction,
                "data_type": resource.data_type,
                "price_per_unit": resource.price_per_unit,
                "provider": resource.provider,
                "lang": resource.lang,
                "is_active": resource.is_active
            }
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/api/ai-models")
async def create_ai_model(
    request: Request,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Create a new AI model"""
    try:
        data = await request.json()
        
        new_resource = AIResource(
            name=data.get('name'),
            model_id=data.get('model_id'),
            type=data.get('type', 'LLM'),
            direction=data.get('direction'),
            data_type=data.get('data_type'),
            price_per_unit=float(data.get('price_per_unit')),
            provider=data.get('provider'),
            lang=data.get('lang') if data.get('type') == 'TTS' else None,
            is_active=data.get('is_active', True)
        )
        
        db.add(new_resource)
        await db.commit()
        
        return {"ok": True, "id": new_resource.id}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.put("/api/ai-models/{resource_id}")
async def update_ai_model(
    resource_id: int,
    request: Request,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Update an AI model"""
    try:
        data = await request.json()
        
        result = await db.execute(select(AIResource).where(AIResource.id == resource_id))
        resource = result.scalar_one_or_none()
        
        if not resource:
            return {"ok": False, "error": "Model not found"}
        
        resource.name = data.get('name', resource.name)
        resource.model_id = data.get('model_id', resource.model_id)
        resource.type = data.get('type', resource.type)
        resource.direction = data.get('direction', resource.direction)
        resource.data_type = data.get('data_type', resource.data_type)
        resource.price_per_unit = float(data.get('price_per_unit', resource.price_per_unit))
        resource.provider = data.get('provider', resource.provider)
        resource.lang = data.get('lang') if data.get('type', resource.type) == 'TTS' else None
        resource.is_active = data.get('is_active', resource.is_active)
        
        await db.commit()
        
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.delete("/api/ai-models/{resource_id}")
async def delete_ai_model(
    resource_id: int,
    current_user: User = Depends(check_admin_access),
    db: AsyncSession = Depends(get_db)
):
    """Delete an AI model"""
    try:
        result = await db.execute(select(AIResource).where(AIResource.id == resource_id))
        resource = result.scalar_one_or_none()
        
        if not resource:
            return {"ok": False, "error": "Model not found"}
        
        await db.delete(resource)
        await db.commit()
        
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}