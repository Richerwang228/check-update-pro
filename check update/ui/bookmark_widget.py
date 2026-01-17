from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QMenu, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QIcon
from models.database import Bookmark
from utils.image_cache import image_cache
import logging

class BookmarkWidget(QWidget):
    deleted = pyqtSignal(int)  # 删除信号
    check_requested = pyqtSignal(int)  # 检查更新信号

    def __init__(self, bookmark: Bookmark, session):
        super().__init__()
        self.bookmark = bookmark
        self.session = session
        self.logger = logging.getLogger(__name__)
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 头像
        avatar_label = QLabel()
        avatar_pixmap = image_cache.get_image(self.bookmark.avatar_url, make_round=True)
        if avatar_pixmap:
            avatar_label.setPixmap(avatar_pixmap.scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio))
        layout.addWidget(avatar_label)
        
        # UP主名称
        name_label = QLabel(self.bookmark.name)
        name_label.setStyleSheet('font-weight: bold;')
        layout.addWidget(name_label)
        
        # 弹性空间
        layout.addStretch()
        
        # 检查按钮
        check_btn = QPushButton('检查更新')
        check_btn.clicked.connect(lambda: self.check_requested.emit(self.bookmark.id))
        layout.addWidget(check_btn)
        
        # 更多操作按钮
        more_btn = QPushButton('⋮')
        more_btn.setFixedWidth(30)
        more_btn.clicked.connect(self.show_context_menu)
        layout.addWidget(more_btn)
        
        # 设置样式
        self.setStyleSheet('''
            QWidget {
                background: white;
                border-radius: 5px;
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

    def show_context_menu(self):
        """显示上下文菜单"""
        menu = QMenu(self)
        
        edit_action = menu.addAction('编辑')
        edit_action.triggered.connect(self.edit_bookmark)
        
        delete_action = menu.addAction('删除')
        delete_action.triggered.connect(self.delete_bookmark)
        
        menu.exec(self.sender().mapToGlobal(self.sender().rect().bottomLeft()))

    def edit_bookmark(self):
        """编辑书签"""
        # TODO: 实现编辑功能
        pass

    def delete_bookmark(self):
        """删除书签"""
        reply = QMessageBox.question(
            self,
            '确认删除',
            f'确定要删除 {self.bookmark.name} 的书签吗？\n相关的更新记录也会被删除。',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.session.delete(self.bookmark)
                self.session.commit()
                self.deleted.emit(self.bookmark.id)
            except Exception as e:
                self.logger.error(f"Error deleting bookmark: {str(e)}")
                QMessageBox.critical(self, '错误', '删除书签时发生错误。') 