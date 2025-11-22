import sys
import os
from PyQt6.QtWidgets import QApplication, QMainWindow
from ui_main import Ui_MainWindow


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Load UI
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        # Apply theme
        self.apply_theme()
        
        # Bind buttons
        self.ui.btnStart.clicked.connect(self.start_crawling)
        self.ui.btnStop.clicked.connect(self.stop_crawling)
        self.ui.btnLoadConfig.clicked.connect(self.load_config)
        self.ui.btnSaveConfig.clicked.connect(self.save_config)
    
    def apply_theme(self):
        theme_file = "ui/style.qss"
        if os.path.exists(theme_file):
            with open(theme_file, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
    
    def log(self, text):
        self.ui.textLog.append(text)
    
    def start_crawling(self):
        url = self.ui.inputURL.text().strip()
        if url:
            self.log(f"[INFO] URL entered: {url}")
            self.log("[INFO] No crawler logic - UI only mode")
        else:
            self.log("[WARNING] Please enter a URL")
    
    def stop_crawling(self):
        self.log("[INFO] Stop button clicked")
    
    def load_config(self):
        self.log("[INFO] Load config button clicked")
    
    def save_config(self):
        self.log("[INFO] Save config button clicked")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
