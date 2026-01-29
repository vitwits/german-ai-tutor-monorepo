"""
AI Preferences admin page for managing model settings and prompts
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import User
from .admin_router import check_admin_access

router = APIRouter(prefix="/admin", tags=["admin"])

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
                    <li class="nav-item"><a class="nav-link" href="/admin/llm-models">LLM Models</a></li>
                    <li class="nav-item"><a class="nav-link" href="/admin/tts-models">TTS Models</a></li>
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
                <div class="tab-header">
                    <h2>{TABS['texts']['name']}</h2>
                    <p>{TABS['texts']['description']}</p>
                </div>
                <p style="color: #999; padding: 40px; text-align: center;">Content coming soon...</p>
            </div>
            
            <!-- WORDS TAB -->
            <div class="tab-content {('active' if tab == 'words' else '')}">
                <div class="tab-header">
                    <h2>{TABS['words']['name']}</h2>
                    <p>{TABS['words']['description']}</p>
                </div>
                <p style="color: #999; padding: 40px; text-align: center;">Content coming soon...</p>
            </div>
            
            <!-- SENTENCES TAB -->
            <div class="tab-content {('active' if tab == 'sentences' else '')}">
                <div class="tab-header">
                    <h2>{TABS['sentences']['name']}</h2>
                    <p>{TABS['sentences']['description']}</p>
                </div>
                <p style="color: #999; padding: 40px; text-align: center;">Content coming soon...</p>
            </div>
            
            <!-- SPEAKING TAB -->
            <div class="tab-content {('active' if tab == 'speaking' else '')}">
                <div class="tab-header">
                    <h2>{TABS['speaking']['name']}</h2>
                    <p>{TABS['speaking']['description']}</p>
                </div>
                <p style="color: #999; padding: 40px; text-align: center;">Content coming soon...</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html
