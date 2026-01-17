from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QFrame, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from models.database import Video, Bookmark
from utils.image_cache import image_cache
import logging
from datetime import datetime

class UpdateWidget(QWidget):
    watched = pyqtSignal(str)  # 视频标记为已看信号

    def __init__(self, bookmark: Bookmark, video: Video, session):
        super().__init__()
        self.bookmark = bookmark
        self.video = video
        self.session = session
        self.logger = logging.getLogger(__name__)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 上部分：UP主信息
        top_layout = QHBoxLayout()
        
        # UP主头像
        avatar_label = QLabel()
        avatar_pixmap = image_cache.get_image(self.bookmark.avatar_url, make_round=True)
        if avatar_pixmap:
            avatar_label.setPixmap(avatar_pixmap.scaled(30, 30, Qt.AspectRatioMode.KeepAspectRatio))
        top_layout.addWidget(avatar_label)
        
        # UP主名称
        name_label = QLabel(self.bookmark.name)
        name_label.setStyleSheet('font-weight: bold;')
        top_layout.addWidget(name_label)
        
        # 发布时间
        time_label = QLabel(self.video.relative_time)
        time_label.setStyleSheet('color: #666;')
        top_layout.addWidget(time_label)
        
        # 弹性空间
        top_layout.addStretch()
        
        # 标记为已看按钮
        watch_btn = QPushButton('标记为已看')
        watch_btn.clicked.connect(self.mark_as_watched)
        top_layout.addWidget(watch_btn)
        
        layout.addLayout(top_layout)
        
        # 中部分：视频信息
        content_layout = QHBoxLayout()
        
        # 缩略图
        thumbnail_label = QLabel()
        thumbnail_pixmap = image_cache.get_image(self.video.thumbnail_url)
        if thumbnail_pixmap:
            thumbnail_label.setPixmap(thumbnail_pixmap.scaled(160, 90, Qt.AspectRatioMode.KeepAspectRatio))
        content_layout.addWidget(thumbnail_label)
        
        # 视频标题
        title_label = QLabel(self.video.title)
        title_label.setWordWrap(True)
        title_label.setStyleSheet('''
            font-size: 14px;
            color: #333;
            margin-left: 10px;
        ''')
        content_layout.addWidget(title_label)
        
        layout.addLayout(content_layout)
        
        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet('background-color: #ddd;')
        layout.addWidget(line)
        
        # 设置整体样式
        self.setStyleSheet('''
            QWidget {
                background: white;
            }
            QPushButton {
                padding: 5px 10px;
                border: 1px solid #ddd;
                border-radius: 3px;
                background: #f8f8f8;
            }
            QPushButton:hover {
                background: #f0f0f0;
            }
        ''')

    def mark_as_watched(self):
        """标记视频为已看"""
        try:
            self.video.is_watched = True
            self.video.watched_at = datetime.now()
            self.session.commit()
            self.watched.emit(self.video.video_id)
            self.hide()  # 隐藏此更新项
        except Exception as e:
            self.logger.error(f"Error marking video as watched: {str(e)}")
            QMessageBox.critical(self, '错误', '标记视频时发生错误。') 