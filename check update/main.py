import sys
from PyQt6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.database import Base, init_db
from ui.qt_main_window import MainWindow
import logging
import os
from datetime import datetime

# 创建logs目录
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)

# 配置日志
log_file = os.path.join(log_dir, 'app.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def main():
    try:
        # 初始化数据库
        engine = create_engine('sqlite:///database.sqlite')
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        init_db()
        
        # 创建Qt应用
        app = QApplication(sys.argv)
        app.setStyle('Fusion')  # 使用Fusion风格，看起来更现代
        
        # 设置样式表
        with open(os.path.join(os.path.dirname(__file__), 'ui/style.qss'), 'r', encoding='utf-8') as f:
            app.setStyleSheet(f.read())
        
        # 创建主窗口
        window = MainWindow(session)
        window.show()
        
        # 运行应用
        result = app.exec()
        
        # 确保窗口正确关闭
        window.close()
        
        # 退出程序
        sys.exit(result)
        
    except Exception as e:
        logger.error(f"程序启动失败: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
