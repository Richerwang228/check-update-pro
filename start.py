import uvicorn
import os
import sys
import threading
import time

# Add the backend directory to sys.path
sys.path.append(os.path.join(os.getcwd(), "web-platform", "backend"))
sys.path.append(os.path.join(os.getcwd(), "check update"))

# Import the app
from app import app, auto_check_loop

def run_scheduler():
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(auto_check_loop())

if __name__ == "__main__":
    # Start the scheduler in a background thread
    t = threading.Thread(target=run_scheduler, daemon=True)
    t.start()
    
    # Run the server
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
