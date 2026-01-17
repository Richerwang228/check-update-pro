from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime

Base = declarative_base()

class Bookmark(Base):
    __tablename__ = 'bookmarks'
    
    id = Column(Integer, primary_key=True)
    url = Column(String, unique=True, nullable=False)
    name = Column(String)
    avatar_url = Column(String)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    last_check_time = Column(DateTime)  # 最后检查时间
    check_count = Column(Integer, default=0)  # 检查次数
    last_video_id = Column(String)  # 最后一个视频ID（用于增量检查）
    update_frequency = Column(Integer, default=7)  # 更新频率（天），动态调整
    consecutive_no_update = Column(Integer, default=0)  # 连续无更新次数
    videos = relationship("Video", back_populates="bookmark", cascade="all, delete-orphan")

class Video(Base):
    __tablename__ = 'videos'
    
    id = Column(Integer, primary_key=True)
    video_id = Column(String, nullable=False)
    title = Column(String)
    thumbnail_url = Column(String)
    upload_time = Column(DateTime)
    relative_time = Column(String)
    is_watched = Column(Boolean, default=False)
    watched_at = Column(DateTime)
    bookmark_id = Column(Integer, ForeignKey('bookmarks.id'))
    created_at = Column(DateTime, default=datetime.now)
    bookmark = relationship("Bookmark", back_populates="videos")

class Settings(Base):
    __tablename__ = 'settings'
    
    id = Column(Integer, primary_key=True)
    check_interval = Column(Integer, default=3600)  # 默认1小时
    update_range_days = Column(Integer, default=7)  # 默认7天
    auto_check = Column(Boolean, default=True)
    last_check_time = Column(DateTime)
    browser_path = Column(String)  # 添加浏览器路径设置

def init_db(db_path='database.sqlite'):
    engine = create_engine(f'sqlite:///{db_path}')
    
    # 检查是否需要迁移
    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    if 'settings' in table_names:
        # 检查是否需要添加browser_path列
        columns = [col['name'] for col in inspector.get_columns('settings')]
        if 'browser_path' not in columns:
            with engine.begin() as connection:
                connection.execute(text('ALTER TABLE settings ADD COLUMN browser_path VARCHAR'))

    if 'bookmarks' in table_names:
        # 检查并添加新列
        columns = [col['name'] for col in inspector.get_columns('bookmarks')]
        new_columns = {
            'avatar_url': 'VARCHAR',
            'last_check_time': 'DATETIME',
            'check_count': 'INTEGER DEFAULT 0',
            'last_video_id': 'VARCHAR',
            'update_frequency': 'INTEGER DEFAULT 7',
            'consecutive_no_update': 'INTEGER DEFAULT 0'
        }
        
        with engine.begin() as connection:
            for col_name, col_type in new_columns.items():
                if col_name not in columns:
                    connection.execute(text(f'ALTER TABLE bookmarks ADD COLUMN {col_name} {col_type}'))
    
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()