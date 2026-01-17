import sys
import os
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                           QPushButton, QLabel, QScrollArea, QFrame, QFileDialog,
                           QDialog, QSpinBox, QCheckBox, QMessageBox, QLineEdit,
                           QProgressDialog, QMenu, QApplication, QComboBox, QProgressBar)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, pyqtProperty
from PyQt6.QtGui import QPixmap, QCursor, QShortcut, QKeySequence
import requests
from PIL import Image
from io import BytesIO
from datetime import datetime
import webbrowser
import logging
from bs4 import BeautifulSoup
from models.database import Bookmark, Settings, Video
from services.update_checker import UpdateChecker
from services.web_scraper import WebScraper
from urllib.parse import urljoin
from utils.image_cache import image_cache
from config.settings import IMAGE_LOAD_CONCURRENCY
# 旧版UI不使用骨架屏
import time

class UpdateCheckThread(QThread):
    finished = pyqtSignal(list)  # 全部完成
    progress_updated = pyqtSignal(int, int, str, float)  # 进度更新 (当前, 总数, 书签名称, 速度)
    item_finished = pyqtSignal(dict)  # 单个项目完成
    error = pyqtSignal(str)

    def __init__(self, session, update_checker):
        super().__init__()
        self.session = session
        self.update_checker = update_checker
        self.start_time = None

    def run(self):
        try:
            self.start_time = time.time()
            def progress_callback(current, total, name):
                elapsed = time.time() - self.start_time
                speed = current / elapsed if elapsed > 0 else 0
                self.progress_updated.emit(current, total, name, speed)
            self.update_checker.set_progress_callback(progress_callback)
            self.update_checker.set_item_callback(lambda u: self.item_finished.emit(u))
            updates = self.update_checker.check_all_bookmarks()
            total = len(self.session.query(Bookmark).all())
            self.progress_updated.emit(total, total, "完成", 0)
            self.finished.emit(updates)

        except Exception as e:
            self.error.emit(str(e))

class ImageLoader(QThread):
    finished = pyqtSignal(QLabel, QPixmap)
    
    def __init__(self, label, url, size):
        super().__init__()
        self.label = label
        self.url = url
        self.size = size
        self.is_running = True
        if not hasattr(ImageLoader, '_sem'):
            ImageLoader._sem = None
        if ImageLoader._sem is None:
            from threading import Semaphore
            ImageLoader._sem = Semaphore(IMAGE_LOAD_CONCURRENCY)
        
    def run(self):
        try:
            ImageLoader._sem.acquire()
            if not self.is_running or not self.url:
                return
            
            # 使用缓存加载图片
            pixmap = image_cache.get_image(self.url)
            
            if not self.is_running:
                return
            
            if pixmap and not pixmap.isNull():
                # 调整大小
                pixmap = pixmap.scaled(
                    self.size[0], self.size[1], 
                    Qt.AspectRatioMode.KeepAspectRatio, 
                    Qt.TransformationMode.SmoothTransformation
                )
                self.finished.emit(self.label, pixmap)
            else:
                # 缓存加载失败，尝试直接下载
                response = requests.get(self.url, timeout=10)
                if not self.is_running:
                    return
                    
                image = Image.open(BytesIO(response.content))
                image = image.resize(self.size, Image.Resampling.LANCZOS)
                bytes_io = BytesIO()
                image.save(bytes_io, format='PNG')
                
                if not self.is_running:
                    return
                    
                pixmap = QPixmap()
                pixmap.loadFromData(bytes_io.getvalue())
                self.finished.emit(self.label, pixmap)
                
        except Exception as e:
            logging.error(f"加载图片失败 {self.url}: {str(e)}")
        finally:
            try:
                ImageLoader._sem.release()
            except Exception:
                pass
        
    def stop(self):
        self.is_running = False
    def __del__(self):
        pass

class SettingsDialog(QDialog):
    def __init__(self, parent, session):
        super().__init__(parent)
        self.session = session
        self.result = None
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle('设置')
        self.setFixedSize(400, 300)
        
        layout = QVBoxLayout()
        
        # 检查间隔
        interval_layout = QHBoxLayout()
        interval_label = QLabel("检查间隔（小时）:")
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 24)
        interval_layout.addWidget(interval_label)
        interval_layout.addWidget(self.interval_spin)
        layout.addLayout(interval_layout)
        
        # 更新范围
        range_layout = QHBoxLayout()
        range_label = QLabel("更新范围:")
        self.range_spin = QSpinBox()
        self.range_spin.setRange(1, 999)  # 允许三位数
        self.range_unit = QComboBox()
        self.range_unit.addItems(['天', '月', '年'])
        self.range_unit.currentTextChanged.connect(self.on_unit_changed)
        range_layout.addWidget(range_label)
        range_layout.addWidget(self.range_spin)
        range_layout.addWidget(self.range_unit)
        layout.addLayout(range_layout)
        
        # 浏览器路径
        browser_layout = QHBoxLayout()
        browser_label = QLabel("浏览器路径:")
        self.browser_path = QLineEdit()
        browser_btn = QPushButton("选择")
        browser_btn.clicked.connect(self.choose_browser)
        browser_layout.addWidget(browser_label)
        browser_layout.addWidget(self.browser_path)
        browser_layout.addWidget(browser_btn)
        layout.addLayout(browser_layout)
        
        # 自动检查
        self.auto_check = QCheckBox("自动检查")
        layout.addWidget(self.auto_check)
        
        # 按钮
        button_layout = QHBoxLayout()
        ok_btn = QPushButton("确定")
        cancel_btn = QPushButton("取消")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # 加载当前设置
        settings = self.session.query(Settings).first()
        if settings:
            self.interval_spin.setValue(settings.check_interval // 3600)
            days = settings.update_range_days
            # 优先判断年
            if days >= 365 and days % 365 == 0:
                self.range_spin.setValue(days // 365)
                self.range_unit.setCurrentText('年')
            # 其次判断月
            elif days >= 30 and days % 30 == 0:
                self.range_spin.setValue(days // 30)
                self.range_unit.setCurrentText('月')
            # 最后是天
            else:
                self.range_spin.setValue(days)
                self.range_unit.setCurrentText('天')
            self.auto_check.setChecked(settings.auto_check)
            if settings.browser_path:
                self.browser_path.setText(settings.browser_path)
    
    def on_unit_changed(self, text):
        """当单位改变时调整范围"""
        current_value = self.range_spin.value()
        if text == '天':
            self.range_spin.setRange(1, 999)  # 天数范围1-999
            if current_value > 999:
                self.range_spin.setValue(999)
        elif text == '月':
            self.range_spin.setRange(1, 120)  # 月数范围1-120
            if current_value > 120:
                self.range_spin.setValue(120)
        else:  # 年
            self.range_spin.setRange(1, 10)  # 年数范围1-10
            if current_value > 10:
                self.range_spin.setValue(10)
    
    def choose_browser(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择浏览器程序",
            "",
            "程序 (*.exe);;所有文件 (*.*)"
        )
        if file_path:
            self.browser_path.setText(file_path)
    
    def accept(self):
        # 计算天数
        days = self.range_spin.value()
        unit = self.range_unit.currentText()
        if unit == '月':
            days = days * 30
        elif unit == '年':
            days = days * 365
        
        self.result = {
            'check_interval': self.interval_spin.value() * 3600,
            'update_range_days': days,
            'auto_check': self.auto_check.isChecked(),
            'browser_path': self.browser_path.text()
        }
        super().accept()

class MainWindow(QMainWindow):
    def __init__(self, session):
        super().__init__()
        self.session = session
        self.update_checker = UpdateChecker(session)
        self.web_scraper = WebScraper()
        self.logger = logging.getLogger(__name__)
        self.image_loaders = []  # 保存所有的图片加载线程
        self._cached_settings = None  # 缓存设置对象
        self._bookmarks_cache = []  # 缓存书签列表
        self.init_ui()
        self.load_stylesheet()
        
    def init_ui(self):
        self.setWindowTitle('视频更新检查器 - 现代版')
        self.setMinimumSize(1000, 700)
        
        # 添加快捷键
        self.setup_shortcuts()
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QHBoxLayout(central_widget)
        
        # 左侧书签面板
        bookmark_frame = QFrame()
        bookmark_frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)
        bookmark_layout = QVBoxLayout(bookmark_frame)
        bookmark_toolbar = QHBoxLayout()
        add_btn = QPushButton('➕ 添加UP主')
        import_btn = QPushButton('📂 导入书签')
        add_btn.clicked.connect(self.add_bookmark)
        import_btn.clicked.connect(self.import_bookmarks)
        bookmark_toolbar.addWidget(add_btn)
        bookmark_toolbar.addWidget(import_btn)
        bookmark_layout.addLayout(bookmark_toolbar)
        self.bookmark_scroll = QScrollArea()
        self.bookmark_scroll.setWidgetResizable(True)
        self.bookmark_list = QWidget()
        self.bookmark_list_layout = QVBoxLayout(self.bookmark_list)
        self.bookmark_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.bookmark_scroll.setWidget(self.bookmark_list)
        bookmark_layout.addWidget(self.bookmark_scroll)

        # 右侧更新面板
        update_frame = QFrame()
        update_frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)
        update_layout = QVBoxLayout(update_frame)
        
        # 更新工具栏
        update_toolbar = QHBoxLayout()
        refresh_btn = QPushButton('🔄 立即检查')
        settings_btn = QPushButton('⚙ 设置')
        stats_btn = QPushButton('📊 统计')
        logs_btn = QPushButton('🧾 日志')
        clear_btn = QPushButton('🗑️ 清空结果')
        refresh_btn.clicked.connect(self.check_for_updates)
        settings_btn.clicked.connect(self.show_settings)
        stats_btn.clicked.connect(self.show_statistics)
        logs_btn.clicked.connect(self.show_logs)
        clear_btn.clicked.connect(self.clear_results)
        
        # 设置按钮提示
        refresh_btn.setToolTip('检查所有书签的更新 (F5)')
        settings_btn.setToolTip('打开设置 (Ctrl+,)')
        stats_btn.setToolTip('查看统计信息')
        clear_btn.setToolTip('清空当前结果 (Ctrl+K)')
        
        update_toolbar.addWidget(refresh_btn)
        update_toolbar.addWidget(settings_btn)
        update_toolbar.addWidget(stats_btn)
        update_toolbar.addWidget(logs_btn)
        update_toolbar.addWidget(clear_btn)
        update_layout.addLayout(update_toolbar)
        
        # 更新列表
        self.update_scroll = QScrollArea()
        self.update_scroll.setWidgetResizable(True)
        self.update_list = QWidget()
        self.update_list_layout = QVBoxLayout(self.update_list)
        self.update_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.update_scroll.setWidget(self.update_list)
        update_layout.addWidget(self.update_scroll)
        
        layout.addWidget(bookmark_frame, 1)
        layout.addWidget(update_frame, 2)
        
        self.load_settings()
        self.load_bookmarks()
        
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self.check_updates_timer)
        self.check_timer.start(3600000)
        
    def setup_shortcuts(self):
        """设置快捷键"""
        # F5 或 Ctrl+R: 刷新/检查更新
        refresh_shortcut = QShortcut(QKeySequence("F5"), self)
        refresh_shortcut.activated.connect(self.check_for_updates)
        
        refresh_shortcut2 = QShortcut(QKeySequence("Ctrl+R"), self)
        refresh_shortcut2.activated.connect(self.check_for_updates)
        
        # Ctrl+N: 添加新书签
        add_shortcut = QShortcut(QKeySequence("Ctrl+N"), self)
        add_shortcut.activated.connect(self.add_bookmark)
        
        # Ctrl+I: 导入书签
        import_shortcut = QShortcut(QKeySequence("Ctrl+I"), self)
        import_shortcut.activated.connect(self.import_bookmarks)
        
        # Ctrl+,: 打开设置
        settings_shortcut = QShortcut(QKeySequence("Ctrl+,"), self)
        settings_shortcut.activated.connect(self.show_settings)
        
        # Ctrl+K: 清空结果
        clear_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        clear_shortcut.activated.connect(self.clear_results)
        
        # Ctrl+Q: 退出程序
        quit_shortcut = QShortcut(QKeySequence("Ctrl+Q"), self)
        quit_shortcut.activated.connect(self.close)
        
        # Ctrl+Shift+C: 清理缓存
        cache_shortcut = QShortcut(QKeySequence("Ctrl+Shift+C"), self)
        cache_shortcut.activated.connect(self.clear_cache)
    
    def closeEvent(self, event):
        # 停止所有图片加载线程
        for loader in self.image_loaders:
            loader.stop()
            loader.wait()
        event.accept()
    
    def add_bookmark_widget(self, bookmark):
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        layout = QHBoxLayout(frame)
        
        # 头像
        avatar_label = QLabel()
        avatar_label.setFixedSize(40, 40)
        if bookmark.avatar_url:
            self.load_image(avatar_label, bookmark.avatar_url, (40, 40))
        else:
            avatar_label.setText("👤")
        layout.addWidget(avatar_label)
        
        # 名称
        name_label = QLabel(bookmark.name)
        layout.addWidget(name_label)
        
        # 按钮
        check_btn = QPushButton("🔄")
        menu_btn = QPushButton("⋮")
        check_btn.clicked.connect(lambda: self.check_single_bookmark(bookmark.id))
        menu_btn.clicked.connect(lambda: self.show_bookmark_menu(frame, bookmark))
        layout.addWidget(check_btn)
        layout.addWidget(menu_btn)
        
        self.bookmark_list_layout.addWidget(frame)
    
    def load_image(self, label, url, size):
        loader = ImageLoader(label, url, size)
        loader.finished.connect(self.on_image_loaded)
        self.image_loaders.append(loader)
        loader.start()
    
    def on_image_loaded(self, label, pixmap):
        if not label.isVisible():
            return
        label.setPixmap(pixmap)
        # 从列表中移除已完成的加载器
        for loader in self.image_loaders[:]:
            if not loader.isRunning():
                self.image_loaders.remove(loader)
                loader.deleteLater()
    
    def add_update_widget(self, bookmark, video):
        frame = QFrame()
        frame.setObjectName("update_item_frame")
        frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        layout = QVBoxLayout(frame)
        
        # UP主信息
        info_layout = QHBoxLayout()
        
        # 头像
        avatar_label = QLabel()
        avatar_label.setFixedSize(30, 30)
        if bookmark.avatar_url:
            self.load_image(avatar_label, bookmark.avatar_url, (30, 30))
        else:
            avatar_label.setText("👤")
        info_layout.addWidget(avatar_label)
        
        # UP主名称
        name_label = QLabel(f"<b>{bookmark.name}</b>")
        info_layout.addWidget(name_label)
        
        # 时间
        time_label = QLabel(video.relative_time)
        info_layout.addWidget(time_label)
        info_layout.addStretch()
        
        layout.addLayout(info_layout)
        
        # 视频信息
        content_layout = QHBoxLayout()
        
        # 缩略图
        thumb_label = QLabel()
        thumb_label.setFixedSize(160, 90)
        if video.thumbnail_url:
            self.load_image(thumb_label, video.thumbnail_url, (160, 90))
        else:
            thumb_label.setText("🎬")
        content_layout.addWidget(thumb_label)
        
        # 标题
        title_label = QLabel(f'<u>{video.title}</u><br><span style="color:gray;">点击打开视频</span>')
        title_label.setWordWrap(True)
        title_label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        title_label.mousePressEvent = lambda e: self.open_video(video.video_id)
        content_layout.addWidget(title_label)
        
        layout.addLayout(content_layout)
        
        self.update_list_layout.addWidget(frame)
    
    def open_video(self, video_id):
        settings = self.get_settings()
        url = f"https://hsex.men/video-{video_id}.htm"
        
        if settings and settings.browser_path:
            try:
                import subprocess
                subprocess.Popen([settings.browser_path, url])
            except Exception as e:
                self.logger.error(f"使用自定义浏览器打开失败: {str(e)}")
                webbrowser.open(url)
        else:
            webbrowser.open(url)
    
    def check_for_updates(self):
        """检查更新"""
        # 清空现有的更新
        for i in reversed(range(self.update_list_layout.count())):
            widget = self.update_list_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

        self.progress_dialog = QProgressDialog("正在检查更新...", "取消", 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.WindowModality.NonModal)
        self.progress_dialog.show()

        self.update_thread = UpdateCheckThread(self.session, self.update_checker)
        self.update_thread.progress_updated.connect(self.update_progress)
        self.update_thread.item_finished.connect(self.add_single_update)
        self.update_thread.finished.connect(self.on_update_check_finished)
        self.update_thread.error.connect(self.on_update_check_error)
        self.update_thread.start()

    def on_update_check_finished(self, updates):
        """更新检查完成后的处理"""
        self.progress_dialog.close()
        if not updates:
            if self.update_list_layout.count() == 0:
                self.update_list_layout.addWidget(QLabel("没有发现更新。"))
            QMessageBox.information(self, "检查完成", "所有书签都是最新的。")
        else:
            QMessageBox.information(self, "检查完成", f"共发现 {len(updates)} 个更新。")
        self.logger.info(f"检查完成，发现 {len(updates)} 个更新。")

    def on_update_check_error(self, error_message):
        """更新检查出错时的处理"""
        self.progress_dialog.close()
        self.logger.error(f"检查更新失败: {error_message}")
        QMessageBox.critical(self, "错误", f"检查更新失败: {error_message}")

    def update_progress(self, current, total, name, speed=0):
        """更新进度条，显示进度百分比和速度"""
        if total > 0:
            self.progress_dialog.setMaximum(total)
            self.progress_dialog.setValue(current)
            percentage = int((current / total) * 100)
            
            # 计算剩余时间
            if speed > 0 and current < total:
                remaining = (total - current) / speed
                remaining_str = f" - 剩余约 {int(remaining)}秒"
            else:
                remaining_str = ""
            
            speed_str = f"{speed:.1f} 个/秒" if speed > 0 else ""
            self.progress_dialog.setLabelText(
                f"正在检查: {name}\n"
                f"进度: {current}/{total} ({percentage}%)\n"
                f"速度: {speed_str}{remaining_str}"
            )

    def add_single_update(self, update):
        """添加单个更新到UI"""
        # 如果当前只有提示标签，先移除它
        if self.update_list_layout.count() == 1 and isinstance(self.update_list_layout.itemAt(0).widget(), QLabel):
            widget = self.update_list_layout.itemAt(0).widget()
            if widget is not None:
                widget.deleteLater()
        
        self.add_update_widget(update['bookmark'], update['video'])

    def clear_results(self):
        """清空所有更新结果"""
        # 检查是否有可清空的内容
        has_updates = False
        for i in range(self.update_list_layout.count()):
            widget = self.update_list_layout.itemAt(i).widget()
            if isinstance(widget, UpdateWidget):
                has_updates = True
                break
        
        if not has_updates:
            QMessageBox.information(self, "提示", "当前没有可清空的结果。")
            return

        for i in reversed(range(self.update_list_layout.count())):
            widget = self.update_list_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()
        
        # 添加提示信息
        self.update_list_layout.addWidget(QLabel("结果已清空，请点击“立即检查”以获取最新状态。"))

    def show_logs(self):
        try:
            from config.settings import LOG_DIR, LOG_FILE
            path = os.path.join(LOG_DIR, LOG_FILE)
            content = ''
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()[-8000:]
            dlg = QDialog(self)
            dlg.setWindowTitle('日志')
            v = QVBoxLayout(dlg)
            label = QLabel(content or '无日志内容')
            label.setWordWrap(True)
            v.addWidget(label)
            dlg.setMinimumSize(700, 500)
            dlg.exec()
        except Exception as e:
            QMessageBox.information(self, '日志', f'无法读取日志：{str(e)}')

    def load_stylesheet(self):
        """加载QSS样式表"""
        style_path = os.path.join(os.path.dirname(__file__), 'style.qss')
        try:
            with open(style_path, 'r', encoding='utf-8') as f:
                self.setStyleSheet(f.read())
        except Exception as e:
            self.logger.warning(f"加载样式表失败: {e}")
    
    def show_settings(self):
        dialog = SettingsDialog(self, self.session)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result:
            self.save_settings(dialog.result)
    
    def save_settings(self, settings_data):
        try:
            settings = self.session.query(Settings).first()
            if not settings:
                settings = Settings()
                self.session.add(settings)
            
            settings.check_interval = settings_data['check_interval']
            settings.update_range_days = settings_data['update_range_days']
            settings.auto_check = settings_data['auto_check']
            settings.browser_path = settings_data['browser_path']
            
            self.session.commit()
            
            # 使缓存失效
            self.invalidate_settings_cache()
            
            QMessageBox.information(self, "成功", "设置已保存。")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存设置失败：{str(e)}")
    
    def check_updates_timer(self):
        settings = self.get_settings()
        if settings and settings.auto_check:
            self.check_for_updates() 
    
    def add_bookmark(self):
        """添加新书签"""
        dialog = QDialog(self)
        dialog.setWindowTitle('添加UP主')
        dialog.setFixedSize(500, 150)
        
        layout = QVBoxLayout(dialog)
        
        # URL输入框
        url_layout = QHBoxLayout()
        url_label = QLabel("UP主主页URL:")
        url_input = QLineEdit()
        url_input.setText('https://hsex.men/user.htm?author=')
        url_layout.addWidget(url_label)
        url_layout.addWidget(url_input)
        layout.addLayout(url_layout)
        
        # 按钮
        button_layout = QHBoxLayout()
        ok_btn = QPushButton("确定")
        cancel_btn = QPushButton("取消")
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.process_add_bookmark(url_input.text())
    
    def process_add_bookmark(self, url):
        """处理添加书签的逻辑"""
        try:
            # 获取UP主信息
            html = self.web_scraper.get_page_content(url)
            if not html:
                QMessageBox.warning(self, '错误', '无法访问该URL，请检查网络连接或URL是否正确')
                return
            
            # 解析UP主信息
            soup = BeautifulSoup(html, 'lxml')
            
            # 尝试获取UP主名称
            name = None
            name_selectors = [
                '.user-info .name',
                '.user-name',
                '.author-name',
                'h1.name',
                '.profile-name'
            ]
            
            for selector in name_selectors:
                name_elem = soup.select_one(selector)
                if name_elem:
                    name = name_elem.text.strip()
                    break
            
            if not name:
                name = f"UP主_{url.split('author=')[-1]}"
            
            # 尝试获取头像URL
            avatar_url = None
            avatar_selectors = [
                '.user-avatar img',
                '.avatar img',
                '.profile-avatar img',
                '.user-info img'
            ]
            
            for selector in avatar_selectors:
                avatar_elem = soup.select_one(selector)
                if avatar_elem and 'src' in avatar_elem.attrs:
                    avatar_url = avatar_elem['src']
                    if avatar_url.startswith('//'):
                        avatar_url = f'https:{avatar_url}'
                    elif avatar_url.startswith('/'):
                        avatar_url = urljoin(url, avatar_url)
                    break
            
            # 检查是否已存在
            existing = self.session.query(Bookmark).filter_by(url=url).first()
            if existing:
                QMessageBox.warning(self, '提示', '该UP主已经添加过了')
                return
            
            # 创建书签
            bookmark = Bookmark(
                url=url,
                name=name,
                avatar_url=avatar_url
            )
            self.session.add(bookmark)
            self.session.commit()
            
            # 添加到界面
            self.add_bookmark_widget(bookmark)
            
            # 立即检查更新
            self.check_single_bookmark(bookmark.id)
            
        except Exception as e:
            QMessageBox.critical(self, '错误', f'添加书签失败：\n{str(e)}\n\n请确保URL格式正确且网页可访问')
    
    def import_bookmarks(self):
        """导入书签"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "选择书签HTML文件",
                "",
                "HTML文件 (*.html);;所有文件 (*.*)"
            )
            
            if not file_path:
                return
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 解析HTML
                soup = BeautifulSoup(content, 'lxml')
                
                # 查找所有链接
                links = soup.find_all('a')
                imported_count = 0
                skipped_count = 0
                
                # 创建进度对话框
                progress = QProgressDialog("正在导入书签...", "取消", 0, len(links), self)
                progress.setWindowTitle("导入书签")
                progress.setWindowModality(Qt.WindowModality.WindowModal)
                
                for i, link in enumerate(links):
                    if progress.wasCanceled():
                        break
                        
                    url = link.get('href', '')
                    # 检查是否是目标网站的用户页面
                    if 'user.htm?author=' in url:
                        # 检查是否已存在
                        existing = self.session.query(Bookmark).filter_by(url=url).first()
                        if not existing:
                            # 创建新书签
                            bookmark = Bookmark(
                                url=url,
                                name=link.text.strip() or f"UP主_{url.split('author=')[-1]}"
                            )
                            self.session.add(bookmark)
                            imported_count += 1
                        else:
                            skipped_count += 1
                    
                    progress.setValue(i + 1)
                    progress.setLabelText(f"正在导入: {imported_count} 个书签...")
                    QApplication.instance().processEvents()
                
                self.session.commit()
                
                # 刷新书签列表
                self.refresh_bookmarks()
                
                # 自动检查新导入的书签
                if imported_count > 0:
                    self.check_for_updates()
                
                message = f'成功导入 {imported_count} 个书签'
                if skipped_count > 0:
                    message += f'\n跳过 {skipped_count} 个已存在的书签'
                QMessageBox.information(self, '导入成功', message)
                
            except Exception as e:
                QMessageBox.critical(self, '导入失败', f'导入书签时出错：\n{str(e)}\n\n请确保文件格式正确且包含有效的书签')
                
        except Exception as e:
            QMessageBox.critical(self, '错误', f'打开文件时出错：\n{str(e)}')
    
    def show_bookmark_menu(self, widget, bookmark):
        """显示书签的上下文菜单（增强版）"""
        menu = QMenu(self)
        
        # 检查更新
        check_action = menu.addAction('🔄 检查更新')
        check_action.triggered.connect(lambda: self.check_single_bookmark(bookmark.id))
        
        # 在浏览器中打开
        open_action = menu.addAction('🌐 在浏览器中打开')
        open_action.triggered.connect(lambda: webbrowser.open(bookmark.url))
        
        menu.addSeparator()
        
        # 编辑名称
        edit_action = menu.addAction('✏️ 编辑名称')
        edit_action.triggered.connect(lambda: self.edit_bookmark_name(bookmark))
        
        # 复制链接
        copy_action = menu.addAction('📋 复制链接')
        copy_action.triggered.connect(lambda: QApplication.clipboard().setText(bookmark.url))
        
        menu.addSeparator()
        
        # 删除
        delete_action = menu.addAction('🗑️ 删除')
        delete_action.triggered.connect(lambda: self.delete_bookmark(widget, bookmark))
        
        menu.popup(QCursor.pos())
    
    def edit_bookmark_name(self, bookmark):
        """编辑书签名称"""
        from PyQt6.QtWidgets import QInputDialog
        
        new_name, ok = QInputDialog.getText(
            self,
            '编辑名称',
            '请输入新的UP主名称:',
            text=bookmark.name
        )
        
        if ok and new_name:
            try:
                bookmark.name = new_name
                self.session.commit()
                self.refresh_bookmarks()
                QMessageBox.information(self, '成功', '名称已更新。')
            except Exception as e:
                QMessageBox.critical(self, '错误', f'更新名称失败：{str(e)}')
    
    def delete_bookmark(self, widget, bookmark):
        """删除书签"""
        reply = QMessageBox.question(
            self,
            '确认删除',
            f'确定要删除 {bookmark.name} 的书签吗？\n相关的更新记录也会被删除。',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.session.delete(bookmark)
                self.session.commit()
                widget.setParent(None)
            except Exception as e:
                QMessageBox.critical(self, '错误', f'删除书签失败：{str(e)}')
    
    def check_single_bookmark(self, bookmark_id):
        """检查单个书签的更新"""
        try:
            bookmark = self.session.query(Bookmark).get(bookmark_id)
            if bookmark:
                settings = self.get_settings()
                update_range_days = settings.update_range_days if settings else 7
                
                updates = self.update_checker.check_single_bookmark(bookmark, update_range_days)
                for update in updates:
                    self.add_update_widget(update['bookmark'], update['video'])
                
                if updates:
                    QMessageBox.information(self, '检查完成', f'发现 {len(updates)} 个更新。')
                else:
                    QMessageBox.information(self, '检查完成', '该UP主没有新更新。')
                
        except Exception as e:
            QMessageBox.critical(self, '错误', f'检查更新失败：{str(e)}')
    
    def refresh_bookmarks(self):
        """刷新书签列表"""
        # 清空现有书签列表
        for i in reversed(range(self.bookmark_list_layout.count())):
            self.bookmark_list_layout.itemAt(i).widget().setParent(None)
        
        # 重新加载书签
        bookmarks = self.session.query(Bookmark).all()
        for bookmark in bookmarks:
            self.add_bookmark_widget(bookmark)
    
    def get_settings(self):
        """获取设置（带缓存）"""
        if self._cached_settings is None:
            self._cached_settings = self.session.query(Settings).first()
            if not self._cached_settings:
                self._cached_settings = Settings()
                self.session.add(self._cached_settings)
                self.session.commit()
        return self._cached_settings
    
    def invalidate_settings_cache(self):
        """使设置缓存失效"""
        self._cached_settings = None
    
    def load_settings(self):
        """加载设置"""
        self.get_settings()  # 初始化缓存
    
    def load_bookmarks(self):
        """加载书签"""
        try:
            bookmarks = self.session.query(Bookmark).all()
            for bookmark in bookmarks:
                self.add_bookmark_widget(bookmark)
        except Exception as e:
            QMessageBox.critical(self, '错误', f'加载书签失败：{str(e)}')
    
    def clear_cache(self):
        """清理缓存（包括图片和页面）"""
        from utils.page_cache import page_cache
        
        reply = QMessageBox.question(
            self,
            '确认清理',
            '确定要清理所有缓存吗？\n\n将清理：\n• 图片缓存\n• 页面缓存\n\n下次访问时会重新下载。',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # 清理图片缓存
                image_cache.clear_all()
                
                # 清理页面缓存
                page_cache.clear_all()
                
                QMessageBox.information(
                    self, 
                    '成功', 
                    '所有缓存已清理完成。\n\n包括：\n✓ 图片缓存\n✓ 页面缓存'
                )
            except Exception as e:
                QMessageBox.critical(self, '错误', f'清理缓存失败：{str(e)}')
    
    def show_statistics(self):
        """显示统计信息（增强版）"""
        try:
            from services.request_manager import request_manager
            from utils.page_cache import page_cache
            
            bookmark_count = self.session.query(Bookmark).count()
            video_count = self.session.query(Video).count()
            settings = self.get_settings()
            
            last_check = "从未检查"
            if settings and settings.last_check_time:
                last_check = settings.last_check_time.strftime("%Y-%m-%d %H:%M:%S")
            
            # 图片缓存大小
            import os
            img_cache_size = 0
            img_cache_dir = 'cache/images'
            if os.path.exists(img_cache_dir):
                for filename in os.listdir(img_cache_dir):
                    file_path = os.path.join(img_cache_dir, filename)
                    if os.path.isfile(file_path):
                        img_cache_size += os.path.getsize(file_path)
            
            img_cache_mb = img_cache_size / (1024 * 1024)
            
            # 页面缓存统计
            page_stats = page_cache.get_stats()
            
            # 请求管理器统计
            req_stats = request_manager.get_statistics()
            
            # 计算书签活跃度
            active_bookmarks = self.session.query(Bookmark).filter(
                Bookmark.update_frequency <= 7
            ).count()
            
            stats_text = f"""
📊 统计信息 (优化版)

═══ 基础统计 ═══
📚 书签数量: {bookmark_count} ({active_bookmarks} 个活跃)
🎬 视频记录: {video_count}
🕐 最后检查: {last_check}

═══ 缓存系统 ═══
🖼️ 图片缓存: {img_cache_mb:.2f} MB
📄 页面缓存: {page_stats['disk_size_mb']:.2f} MB
💾 内存缓存: {page_stats['memory_cached']} 个页面
📦 磁盘缓存: {page_stats['disk_cached']} 个页面

═══ 请求统计 ═══
🌐 总请求数: {req_stats['total_requests']}
❌ 失败请求: {req_stats['total_failures']}
🚫 封禁次数: {req_stats['total_blocks']}
⚡ 最近1分钟: {req_stats['recent_requests_per_minute']} 个请求
🔒 当前封禁: {req_stats['active_blocks']} 个域名

⌨️ 快捷键:
• F5 / Ctrl+R: 刷新检查
• Ctrl+N: 添加书签
• Ctrl+I: 导入书签
• Ctrl+,: 打开设置
• Ctrl+K: 清空结果
• Ctrl+Shift+C: 清理缓存
• Ctrl+Q: 退出程序
            """
            
            QMessageBox.information(self, '统计信息 (优化版)', stats_text)
            
        except Exception as e:
            QMessageBox.critical(self, '错误', f'获取统计信息失败：{str(e)}')
