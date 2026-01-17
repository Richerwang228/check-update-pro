import os
import sys
import json
import logging
from datetime import datetime

# Setup paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEGACY_DIR = os.path.join(BASE_DIR, 'check update')
OUTPUT_FILE = os.path.join(BASE_DIR, 'web-platform', 'frontend', 'data.json')
DB_PATH = os.path.join(BASE_DIR, 'database.sqlite')

# Add legacy code to path
sys.path.append(LEGACY_DIR)

from models.database import init_db, Bookmark, Video, Settings
from services.update_checker import UpdateChecker
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("🚀 Starting automated update check...")
    
    # Ensure database exists
    if not os.path.exists(DB_PATH):
        logger.info("Initializing database...")
        # We need to temporarily set cwd to legacy dir because init_db might rely on relative paths or just to be safe
        # actually init_db in models uses a hardcoded path usually, let's just connect manually
        pass

    engine = create_engine(f'sqlite:///{DB_PATH}')
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Check settings
        settings = session.query(Settings).first()
        if not settings:
            settings = Settings(check_interval=3600, update_range_days=7)
            session.add(settings)
            session.commit()
            
        update_range_days = settings.update_range_days
        logger.info(f"Update range: {update_range_days} days")
        
        # Run Check
        checker = UpdateChecker(session)
        updates = checker.check_all_bookmarks()
        
        logger.info(f"✅ Check complete. Found {len(updates)} distinct updates.")
        
        # Prepare data for export
        # We need to fetch ALL relevant updates from database to show in the frontend, 
        # not just the ones found in this run (because the frontend is static and needs full history within range)
        # Actually, the frontend usually only shows "New" updates.
        # But for a static site, it acts as a "Latest Feed".
        # So let's query the Video table for videos within the range.
        
        from datetime import timedelta
        cutoff_date = datetime.now() - timedelta(days=update_range_days)
        
        recent_videos = session.query(Video).join(Bookmark).filter(
            Video.upload_time >= cutoff_date
        ).order_by(Video.upload_time.desc()).limit(100).all()
        
        export_data = {
            "metadata": {
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_items": len(recent_videos),
                "range_days": update_range_days
            },
            "items": []
        }
        
        for v in recent_videos:
            b = v.bookmark
            export_data["items"].append({
                "bookmark": {
                    "id": b.id,
                    "name": b.name,
                    "url": b.url,
                    "avatar_url": b.avatar_url
                },
                "video": {
                    "video_id": v.video_id,
                    "title": v.title,
                    "thumbnail_url": v.thumbnail_url,
                    "relative_time": v.relative_time,
                    "upload_time": v.upload_time.isoformat() if v.upload_time else ""
                }
            })
            
        # Check if encryption is required
        site_password = os.environ.get('SITE_PASSWORD')
        if site_password and site_password.strip():
            logger.info("🔒 Encrypting data with SITE_PASSWORD...")
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import pad
            from Crypto.Random import get_random_bytes
            from Crypto.Protocol.KDF import PBKDF2
            import base64
            
            # Prepare data
            json_str = json.dumps(export_data, ensure_ascii=False)
            data_bytes = json_str.encode('utf-8')
            
            # Key Derivation
            salt = get_random_bytes(16)
            key = PBKDF2(site_password, salt, dkLen=32, count=1000)
            
            # Encrypt
            iv = get_random_bytes(16)
            cipher = AES.new(key, AES.MODE_CBC, iv)
            ct_bytes = cipher.encrypt(pad(data_bytes, AES.block_size))
            
            # Result
            final_output = {
                "encrypted": True,
                "salt": base64.b64encode(salt).decode('utf-8'),
                "iv": base64.b64encode(iv).decode('utf-8'),
                "content": base64.b64encode(ct_bytes).decode('utf-8')
            }
            logger.info("🔒 Data encrypted successfully.")
        else:
            final_output = export_data

        # Write to JSON
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(final_output, f, ensure_ascii=False, indent=2)
            
        logger.info(f"💾 Exported items to {OUTPUT_FILE}")
        
    except Exception as e:
        logger.error(f"❌ Error during check: {e}", exc_info=True)
        sys.exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    main()
