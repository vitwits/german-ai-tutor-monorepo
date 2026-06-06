"""
TTS Voices admin page - insert at end of admin_router.py

This file contains the endpoint and UI for managing TTS voices.
Append this to the admin_router.py file after the delete_llm_price function.
"""

from fastapi import Depends, Request, APIRouter
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import User, TTSVoice, TTSModel
from app.dependencies import check_admin_access

router = APIRouter()

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
                    {{rows_html if rows_html else '<tr><td colspan="6" style="text-align: center; padding: 20px; color: #999;">No TTS voices yet. Click "Add" to create one.</td></tr>'}}
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
