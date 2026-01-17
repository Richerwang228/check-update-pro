import os
import sys
import time
import json
import webbrowser
import subprocess
import asyncio
import threading
from typing import List, Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Define paths
ROOT_DIR = os.path.normpath(os.path.join(BASE_DIR, '..', '..'))
LEGACY_DIR = os.path.join(ROOT_DIR, 'check update')

# Add legacy dir to sys.path
if LEGACY_DIR not in sys.path:
    sys.path.append(LEGACY_DIR)

# Add legacy code to path
sys.path.append(LEGACY_DIR)

from models.database import init_db, Bookmark, Video, Settings
from services.update_checker import UpdateChecker
from services.request_manager import request_manager
from utils.page_cache import page_cache

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_dir = os.path.join(BASE_DIR, '..', 'frontend')
app.mount("/static", StaticFiles(directory=os.path.normpath(frontend_dir)), name="static")

@app.get("/")
def index():
    return FileResponse(os.path.normpath(os.path.join(frontend_dir, 'index.html')))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pydantic import BaseModel

# Use the database in the root directory which contains the actual data
db_path = os.path.join(ROOT_DIR, 'database.sqlite')
if not os.path.exists(db_path):
    # Fallback to legacy directory if root db doesn't exist
    db_path = os.path.join(LEGACY_DIR, 'database.sqlite')

engine = create_engine(f'sqlite:///{db_path}')
Session = sessionmaker(bind=engine)

class SettingsModel(BaseModel):
    check_interval: int
    update_range_days: int
    auto_check: bool
    browser_path: str | None = None

class OpenUrlRequest(BaseModel):
    url: str

@app.post("/api/open")
def open_url(req: OpenUrlRequest):
    session = Session()
    try:
        settings = session.query(Settings).first()
        browser_path = settings.browser_path if settings else None
        
        if browser_path and os.path.exists(browser_path):
            try:
                subprocess.Popen([browser_path, req.url])
                return {"status": "success", "method": "custom"}
            except Exception as e:
                print(f"Failed to launch custom browser: {e}")
                # Fallback to default
        
        webbrowser.open(req.url)
        return {"status": "success", "method": "default"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        session.close()

@app.get("/api/settings")
def get_settings():
    session = Session()
    try:
        settings = session.query(Settings).first()
        if not settings:
            # Create default settings if not exist
            settings = Settings(
                check_interval=3600,
                update_range_days=7,
                auto_check=True
            )
            session.add(settings)
            session.commit()
        
        return {
            "check_interval": settings.check_interval,
            "update_range_days": settings.update_range_days,
            "auto_check": settings.auto_check,
            "browser_path": settings.browser_path
        }
    finally:
        session.close()

@app.post("/api/settings")
def update_settings(settings_data: SettingsModel):
    session = Session()
    try:
        settings = session.query(Settings).first()
        if not settings:
            settings = Settings()
            session.add(settings)
        
        settings.check_interval = settings_data.check_interval
        settings.update_range_days = settings_data.update_range_days
        settings.auto_check = settings_data.auto_check
        settings.browser_path = settings_data.browser_path
        
        session.commit()
        return {"status": "success"}
    except Exception as e:
        session.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        session.close()


print(f"Using database at: {db_path}")

# Create our own session factory to avoid 'Session object is not callable' error
# and to ensure thread safety with new sessions for each request/thread
engine = create_engine(f'sqlite:///{db_path}')
SessionFactory = sessionmaker(bind=engine)

clients: List[WebSocket] = []
updates_cache: List[Dict] = []
main_loop = None
clients_lock = threading.Lock()

def broadcast(data: Dict):
    text = json.dumps(data, ensure_ascii=False)
    with clients_lock:
        current = list(clients)
    if not current:
        return
    for ws in current:
        try:
            asyncio.run_coroutine_threadsafe(ws.send_text(text), main_loop)
        except Exception:
            pass

@app.on_event("startup")
async def on_startup():
    global main_loop
    main_loop = asyncio.get_event_loop()

@app.websocket("/ws/progress")
async def ws_progress(ws: WebSocket):
    await ws.accept()
    with clients_lock:
        clients.append(ws)
    try:
        while True:
            await asyncio.sleep(30)
    except WebSocketDisconnect:
        pass
    finally:
        with clients_lock:
            if ws in clients:
                clients.remove(ws)

@app.get("/api/bookmarks")
def list_bookmarks():
    sess = SessionFactory()
    rows = sess.query(Bookmark).all()
    data = []
    for b in rows:
        data.append({
            "id": b.id,
            "name": b.name or "",
            "url": b.url,
            "avatar_url": b.avatar_url or ""
        })
    sess.close()
    return {"data": data}

@app.get("/api/updates")
def get_updates():
    return {"data": updates_cache}

@app.get("/api/stats")
def get_stats():
    req = request_manager.get_statistics()
    cache = page_cache.get_stats()
    return {"request": req, "cache": cache}

@app.get("/api/logs")
def get_logs():
    path = os.path.join(LEGACY_DIR, 'logs', 'app.log')
    if not os.path.exists(path):
        return {"data": ""}
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()[-10000:]
        return {"data": content}
    except Exception:
        return {"data": ""}


current_checker = None
checker_lock = threading.Lock()

def run_check(update_range_days: int):
    global current_checker
    sess = SessionFactory()
    checker = UpdateChecker(sess)
    
    with checker_lock:
        current_checker = checker
        
    def on_progress(current, total, name, speed=0.0):
        broadcast({"type": "progress", "current": current, "total": total, "name": name, "speed": speed})
    def on_item(update):
        try:
            b = update.get("bookmark")
            v = update.get("video")
            item = {
                "bookmark": {
                    "id": getattr(b, "id", None),
                    "name": getattr(b, "name", ""),
                    "url": getattr(b, "url", ""),
                    "avatar_url": getattr(b, "avatar_url", "")
                },
                "video": {
                    "video_id": getattr(v, "video_id", ""),
                    "title": getattr(v, "title", ""),
                    "thumbnail_url": getattr(v, "thumbnail_url", ""),
                    "relative_time": getattr(v, "relative_time", "")
                }
            }
            updates_cache.append(item)
            broadcast({"type": "item", "data": item})
        except Exception:
            pass
    checker.set_progress_callback(on_progress)
    checker.set_item_callback(on_item)
    updates_cache.clear()
    
    try:
        res = checker.check_all_bookmarks()
        broadcast({"type": "done", "count": len(res)})
    finally:
        with checker_lock:
            current_checker = None
        sess.close()

@app.post("/api/check")
def start_check(update_range_days: int = 7, background_tasks: BackgroundTasks = None):
    global current_checker
    with checker_lock:
        if current_checker is not None:
            return {"status": "running"}
            
    if background_tasks is None:
        t = threading.Thread(target=run_check, args=(update_range_days,), daemon=True)
        t.start()
    else:
        background_tasks.add_task(run_check, update_range_days)
    return {"status": "started"}

@app.post("/api/stop")
def stop_check():
    global current_checker
    with checker_lock:
        if current_checker:
            current_checker.stop()
            return {"status": "stopping"}
    return {"status": "not_running"}

async def auto_check_loop():
    print("Auto-check scheduler started")
    # Initial delay to let things settle
    await asyncio.sleep(10)
    
    last_check = time.time()
    
    while True:
        try:
            # Check settings every minute
            await asyncio.sleep(60)
            
            # Create a new session for this check
            session = SessionFactory()
            try:
                settings = session.query(Settings).first()
                if not settings or not settings.auto_check:
                    continue
                
                interval = settings.check_interval
                
                # Check if it's time
                if time.time() - last_check > interval:
                    print(f"Auto-check triggered (Interval: {interval}s)")
                    
                    # Check if already running
                    is_running = False
                    with checker_lock:
                        if current_checker is not None:
                            is_running = True
                    
                    if not is_running:
                        # Run check in a separate thread
                        t = threading.Thread(target=run_check, args=(settings.update_range_days,), daemon=True)
                        t.start()
                        last_check = time.time()
                    else:
                        print("Skipping auto-check: Check already in progress")
            except Exception as e:
                print(f"Error reading settings: {e}")
            finally:
                session.close()
                
        except Exception as e:
            print(f"Auto-check loop error: {e}")
            await asyncio.sleep(60)

@app.on_event("startup")
async def start_background_tasks():
    asyncio.create_task(auto_check_loop())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
