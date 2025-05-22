#!/usr/bin/env python3
# dashboard.py  –  continuous-drive version
#
# Hold ↑ ↓ ← →  (or long-press the GUI arrow buttons) to stream
# F/B/L/R packets at 20 Hz; release to send S.

import sys
import math
import socket
from PyQt5.QtCore    import Qt, QPointF, QTimer
from PyQt5.QtGui     import QPixmap, QPainter
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QPushButton,
                             QVBoxLayout, QHBoxLayout, QCheckBox)

# ─────────────── configuration ───────────────
JETSON_IP  = "192.168.8.144"   # adjust to your Jetson IP
UDP_PORT   = 5005
TICK_MS    = 50                # 20 Hz command stream
STEP_PX    = 4                 # movement per tick
WIN_W, WIN_H = 800, 600
# ──────────────────────────────────────────────


class Dashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AMR TELE-OP")
        self.resize(WIN_W, WIN_H)
        self.setFocusPolicy(Qt.StrongFocus)

        # local pose
        self.x   = WIN_W / 2
        self.y   = WIN_H / 2
        self.yaw = 0.0

        # comms
        self._udp_sock   = None
        self._udp_target = (JETSON_IP, UDP_PORT)

        # current drive command: 'f', 'b', 'l', 'r' or None
        self.drive_cmd = None

        # UI ──────────────────────────────────────
        root = QVBoxLayout(self)

        self.view = QLabel()
        self.view.setMinimumSize(600, 500)
        self.view.setStyleSheet("background:#000")
        root.addWidget(self.view)

        self.manual_cb = QCheckBox("Manual arrow-key drive (hold for motion)")
        self.manual_cb.setChecked(True)
        root.addWidget(self.manual_cb)

        row = QHBoxLayout(); root.addLayout(row)
        for key, txt in [("l", "←"), ("f", "↑"), ("r", "→"),
                         ("b", "↓"), ("s", "■")]:
            btn = QPushButton(txt); btn.setFixedSize(48, 48)
            if key == "s":
                btn.setStyleSheet("background:red;color:white")
                btn.clicked.connect(lambda _=False, k=key: self._stop())
            else:
                btn.pressed.connect(lambda k=key: self._start(k))
                btn.released.connect(lambda: self._stop())
            row.addWidget(btn)

        # periodic timer
        self.timer = QTimer(self); self.timer.timeout.connect(self._tick)
        self.timer.start(TICK_MS)

        self.setFocus()
        self._draw_dot()

    # ─────────────── networking ────────────────
    def _send(self, letter: str):
        if self._udp_sock is None:
            self._udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._udp_sock.sendto(letter.encode(), self._udp_target)

    # ─────────────── driving logic ─────────────
    def _start(self, k: str):
        self.drive_cmd = k
        self._send(k.upper())      # immediate first packet

    def _stop(self):
        if self.drive_cmd is not None:
            self._send('S')
            self.drive_cmd = None

    def _tick(self):
        """Called every TICK_MS ms."""
        if self.drive_cmd:
            self._send(self.drive_cmd.upper())
            self._simulate(self.drive_cmd)

    # ─────────────── key events ────────────────
    def keyPressEvent(self, e):
        if not (self.manual_cb.isChecked() and not e.isAutoRepeat()):
            return
        key_map = {Qt.Key_Up:'f', Qt.Key_Down:'b',
                   Qt.Key_Left:'l', Qt.Key_Right:'r'}
        if e.key() in key_map:
            self._start(key_map[e.key()])
        elif e.key() in (Qt.Key_Space, Qt.Key_S):
            self._stop()

    def keyReleaseEvent(self, e):
        if not (self.manual_cb.isChecked() and not e.isAutoRepeat()):
            return
        if e.key() in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right):
            self._stop()

    # ─────────────── simulation ────────────────
    def _simulate(self, k: str):
        if   k == 'f':
            self.x += STEP_PX * math.cos(self.yaw)
            self.y += STEP_PX * math.sin(self.yaw)
        elif k == 'b':
            self.x -= STEP_PX * math.cos(self.yaw)
            self.y -= STEP_PX * math.sin(self.yaw)
        elif k == 'l':
            self.yaw += 0.05            # smoother rotation
        elif k == 'r':
            self.yaw -= 0.05

        self.x = max(10, min(self.view.width()  - 10, self.x))
        self.y = max(10, min(self.view.height() - 10, self.y))
        self._draw_dot()

    def _draw_dot(self):
        pix = QPixmap(self.view.size()); pix.fill(Qt.black)
        p = QPainter(pix); p.setPen(Qt.white); p.setBrush(Qt.white)

        centre = QPointF(self.x, self.y)
        p.drawEllipse(centre, 6, 6)
        tip = QPointF(self.x + 14*math.cos(self.yaw),
                      self.y + 14*math.sin(self.yaw))
        p.drawLine(centre, tip)

        p.end()
        self.view.setPixmap(pix)


# ─────────────────────────── runner ────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    Dashboard().show()
    sys.exit(app.exec_())
