"""
Custom admin router for FastAPI - replaces Flask-Admin with enhanced functionality
"""
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select, and_
import os
import datetime
from typing import Optional
from datetime import timedelta

from ..database import get_db
from ..models import User, Sentence, SentenceBatch, TempSentence
from ..dependencies import get_current_user
from ..security import verify_password, create_access_token

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
        {ADMIN_CSS}
    </head>
    <body>
        {get_navbar_html('dashboard', current_user.email)}
        
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
            .navbar-container {{ display: flex; align-items: center; justify-content: space-between; padding: 0 30px; height: 70px; }}
            .navbar-brand {{ font-size: 1.5em; font-weight: 700; color: white; text-decoration: none; display: flex; align-items: center; gap: 10px; }}
            .navbar-brand:hover {{ color: #f0f0f0; }}
            .nav-menu {{ display: flex; gap: 0; list-style: none; flex: 1; margin-left: 40px; }}
            .nav-item {{ position: relative; }}
            .nav-link {{ color: rgba(255,255,255,0.9); text-decoration: none; padding: 25px 18px; font-size: 0.95em; font-weight: 500; transition: all 0.3s; border-bottom: 3px solid transparent; height: 70px; display: flex; align-items: center; }}
            .nav-link:hover {{ color: white; background-color: rgba(255,255,255,0.1); border-bottom-color: rgba(255,255,255,0.3); }}
            .nav-link.active {{ color: white; background-color: rgba(255,255,255,0.15); border-bottom-color: white; }}
            .nav-right {{ display: flex; gap: 15px; align-items: center; margin-left: auto; color: white; }}
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
                <a class="navbar-brand" href="/admin">🎓 German Tutor Admin</a>
                <ul class="nav-menu">
                    <li class="nav-item"><a class="nav-link" href="/admin">Dashboard</a></li>
                    <li class="nav-item"><a class="nav-link active" href="/admin/sentence/list">Sentences</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/reported">Reported</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/users">Users</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/generate">Generate</a></li>
                </ul>
                <div class="nav-right">
                    <span>{current_user.email}</span>
                    <a class="nav-link" href="/admin/logout" style="padding: 10px 15px; border-bottom: none;">Logout</a>
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
        
        rows_html += f"""
        <tr>
            <td class="col-play"><button class="play-btn" onclick="playSequence(this, [{', '.join(audio_urls)}])">▶</button></td>
            <td>{s.text_de or ''}</td>
            <td>{s.text_en or ''}</td>
            <td>{s.text_uk or ''}</td>
            <td>{s.topic or ''}</td>
            <td>
                <div style="display: flex; gap: 8px;">
                    <a href="/admin/sentence/{s.id}/edit" class="btn btn-primary action-btn">Edit</a>
                    <form action="/admin/sentence/{s.id}/unreport" method="POST" style="display:inline;">
                        <button type="submit" class="btn btn-warning action-btn">Un-report</button>
                    </form>
                    <form action="/admin/sentence/{s.id}/delete" method="POST" style="display:inline;">
                        <button type="submit" class="btn btn-danger action-btn">Delete</button>
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
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined" rel="stylesheet">
        <style>
            body {{ padding: 20px; }}
            .navbar {{ background-color: #2c3e50; margin-bottom: 20px; }}
            .action-btn {{ width: 36px; height: 36px; padding: 0; }}
            .play-btn {{ background: #4CAF50; color: white; border: none; border-radius: 50%; width: 32px; height: 32px; cursor: pointer; }}
        </style>
    </head>
    <body>
        <nav class="navbar navbar-dark bg-dark">
            <a class="navbar-brand" href="/admin">🎓 DE Tutor Admin</a>
        </nav>
        <div class="container-fluid">
            <h1>Reported Sentences ({len(sentences)})</h1>
            <table class="table table-striped">
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
                <tbody>{rows_html}</tbody>
            </table>
        </div>
        <script>
            let currentAudio = null;
            let currentRow = null;
            let stopPlayback = false;
            
            async function playSequence(btn, urls) {{
                const isPauseAction = (currentRow === btn.closest('tr'));
                if (currentAudio) currentAudio.pause();
                if (currentRow) {{
                    currentRow.classList.remove('playing-row');
                    const oldBtn = currentRow.querySelector('.play-btn');
                    if (oldBtn) oldBtn.innerHTML = '▶';
                }}
                stopPlayback = true;
                await new Promise(r => setTimeout(r, 50));
                if (isPauseAction) {{ currentRow = null; currentAudio = null; return; }}
                stopPlayback = false;
                let activeRow = btn.closest('tr');
                while (activeRow && !stopPlayback) {{
                    const currentBtn = activeRow.querySelector('.play-btn');
                    currentRow = activeRow;
                    activeRow.classList.add('playing-row');
                    currentBtn.innerHTML = '⏸';
                    for (const url of urls) {{
                        if (stopPlayback) break;
                        if (!url) continue;
                        await new Promise((resolve) => {{
                            currentAudio = new Audio(url);
                            currentAudio.onended = resolve;
                            currentAudio.onerror = resolve;
                            currentAudio.play();
                        }});
                        await new Promise(r => setTimeout(r, 500));
                    }}
                    activeRow.classList.remove('playing-row');
                    currentBtn.innerHTML = '▶';
                    currentRow = null;
                    currentAudio = null;
                    
                    // Move to next TR element, skip non-TR nodes
                    do {{
                        activeRow = activeRow.nextElementSibling;
                    }} while (activeRow && activeRow.tagName !== 'TR');
                }}
                
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
            <td>{u.credits}</td>
            <td>{"Yes" if u.is_admin else "No"}</td>
            <td><button class="btn btn-sm btn-primary">Edit</button></td>
        </tr>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Users</title>
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
        <div class="container-fluid">
            <h1>Users ({len(users)})</h1>
            <table class="table table-striped">
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
    </body>
    </html>
    """
    return html


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
    
    await db.delete(sentence)
    await db.commit()
    
    return {"ok": True}


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
                audio_btn = f'<button class="btn btn-sm btn-success" onclick="generateAudio({batch.id})">🔊 Generate Audio</button>'
        
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