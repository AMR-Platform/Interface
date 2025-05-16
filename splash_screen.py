from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtCore import Qt, QTimer


class SplashScreen(QWidget):
    def __init__(self, on_finish):
        super().__init__()
        self.setWindowTitle("AMR Dashboard - Welcome")
        self.setFixedSize(800, 500)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.on_finish = on_finish
        self.init_ui()

        QTimer.singleShot(3000, self.close_splash)

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Background Image
        bg = QLabel(self)
        pixmap = QPixmap("resources/splash.jpeg").scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        bg.setPixmap(pixmap)
        bg.setAlignment(Qt.AlignCenter)

        # Welcome Message
        msg = QLabel("Welcome to AMR Remote Monitoring Dashboard")
        msg.setStyleSheet("color: white;")
        msg.setFont(QFont("Arial", 20, QFont.Bold))
        msg.setAlignment(Qt.AlignCenter)

        # Stack the message on the background
        bg_layout = QVBoxLayout(bg)
        bg_layout.addStretch()
        bg_layout.addWidget(msg)
        bg_layout.addStretch()

        layout.addWidget(bg)
        self.setLayout(layout)

    def close_splash(self):
        self.close()
        self.on_finish()
