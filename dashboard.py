from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QFrame, QSizePolicy, QGridLayout
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class Dashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AMR Remote Dashboard")
        self.setMinimumSize(1200, 720)
        self.setStyleSheet("background-color: #161822; color: #EAEAEA;")
        self.init_ui()

    def create_telemetry_box(self, title, value="--"):
        box = QFrame()
        box.setStyleSheet("""
            QFrame {
                background-color: #222430;
                border-radius: 10px;
                padding: 10px;
            }
        """)
        layout = QVBoxLayout(box)
        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        value_label = QLabel(value)
        value_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        value_label.setStyleSheet("color: #7FDBFF;")
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        return box

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # === Top Bar ===
        top_bar = QHBoxLayout()
        status_label = QLabel("🟢 Connected | Topic: /amr/state")
        status_label.setFont(QFont("Segoe UI", 11))
        top_bar.addWidget(status_label)
        top_bar.addStretch()
        top_bar.addWidget(QLabel("📶 WiFi: Strong"))
        main_layout.addLayout(top_bar)
        main_layout.addSpacing(10)

        # === Center Layout ===
        center_layout = QHBoxLayout()

        # --- Left: Map Frame ---
        map_frame = QFrame()
        map_frame.setMinimumWidth(int(self.width() * 0.5))
        map_frame.setStyleSheet("background-color: #1F2233; border-radius: 10px;")
        map_layout = QVBoxLayout(map_frame)
        map_label = QLabel("🗺️ Occupancy Grid Map")
        map_label.setFont(QFont("Segoe UI", 13, QFont.Bold))
        map_label.setAlignment(Qt.AlignCenter)
        map_layout.addWidget(map_label)
        map_layout.addStretch()
        center_layout.addWidget(map_frame, 1)

        # --- Right: Telemetry + Errors ---
        right_panel = QVBoxLayout()

        # Grid of telemetry cards
        telemetry_grid = QGridLayout()
        telemetry_grid.setSpacing(12)

        telemetry_items = [
            "Battery (%)", "Velocity (m/s)", "Omega (rad/s)",
            "IMU Angle (°)", "Encoder L", "Encoder R",
            "RPM L", "RPM R"
        ]

        for i, label in enumerate(telemetry_items):
            box = self.create_telemetry_box(label)
            telemetry_grid.addWidget(box, i // 2, i % 2)

        right_panel.addLayout(telemetry_grid)
        right_panel.addSpacing(15)

        # Error Panel
        error_label = QLabel("⚠️ Error Logs")
        error_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        error_text = QTextEdit()
        error_text.setReadOnly(True)
        error_text.setStyleSheet("background-color: #2C1E1E; color: #FF6B6B; border: none;")
        error_text.setPlaceholderText("No errors yet.")

        right_panel.addWidget(error_label)
        right_panel.addWidget(error_text)

        center_layout.addLayout(right_panel, 1)
        main_layout.addLayout(center_layout)

        # === Bottom Control Buttons ===
        bottom_bar = QHBoxLayout()
        bottom_bar.addStretch()
        for label in ["⬅️ Left", "⬆️ Forward", "➡️ Right", "⬇️ Backward", "⏹️ Stop"]:
            btn = QPushButton(label)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3B4B5A;
                    color: white;
                    font-weight: bold;
                    padding: 10px 20px;
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background-color: #4C6276;
                }
            """)
            bottom_bar.addWidget(btn)
        bottom_bar.addStretch()

        main_layout.addSpacing(10)
        main_layout.addLayout(bottom_bar)
        main_layout.addSpacing(10)

        self.setLayout(main_layout)
