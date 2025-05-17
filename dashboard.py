# dashboard.py  –  two-pane UI
# • top  : static warehouse map (never changes)
# • bottom : live Li-DAR map  + heading arrow + A* path  + goal “X”
# • grey grid every 2 m, numeric ticks every 4 m
# • manual arrow-key override / auto toggle
# • full int() casts → no Qt TypeError

import sys, json, math, base64, numpy as np
from PyQt5.QtCore      import Qt, QUrl, QPointF
from PyQt5.QtGui       import (QPixmap, QImage, QPainter, QBrush,
                               QPolygonF, QColor)
from PyQt5.QtWidgets   import (QApplication, QWidget, QLabel, QPushButton,
                               QVBoxLayout, QHBoxLayout, QGridLayout, QFrame,
                               QTextEdit, QCheckBox, QLineEdit)
from PyQt5.QtWebSockets import QWebSocket
from PyQt5.QtNetwork    import QAbstractSocket                     # ConnectedState


# ────────────────────────────────────────────────────────────────
class Card(QFrame):
    def __init__(self, title: str):
        super().__init__()
        self.setStyleSheet(
            "QFrame{background:#2b2d3a;border-radius:10px}"
            "QLabel{color:white}")
        v = QVBoxLayout(self)
        t = QLabel(title); t.setStyleSheet("font-size:12px")
        self.val = QLabel("--"); self.val.setStyleSheet("font-size:19px")
        v.addWidget(t); v.addWidget(self.val); v.addStretch()


# ────────────────────────────────────────────────────────────────
class Dashboard(QWidget):
    # ── init ────────────────────────────────────────────────────
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AMR UI  •  auto-plan  ⇆  manual drive")
        self.resize(1280, 720)
        self.setFocusPolicy(Qt.StrongFocus)

        # robot / map state
        self.res = 0.10                 # metres per cell
        self.base         = None        # static occupancy grid (numpy)
        self._static_done = False       # drawn once flag
        self.prev_pose = self.prev_ts = None
        self.manual  = False
        self.goal    = None             # (gx,gy)
        self.path    = []               # list of way-points

        # ―― layout ---------------------------------------------------------
        root = QHBoxLayout(self)

        # ◤ left column – two stacked map panes
        maps_col = QVBoxLayout()
        self.static_lbl = QLabel(); self.static_lbl.setMinimumSize(600, 300)
        self.static_lbl.setStyleSheet("background:#111")
        self.live_lbl   = QLabel(); self.live_lbl.setMinimumSize(600, 300)
        self.live_lbl.setStyleSheet("background:#111")
        maps_col.addWidget(self.static_lbl); maps_col.addWidget(self.live_lbl)
        root.addLayout(maps_col, 3)

        # ◤ right column
        right = QVBoxLayout(); root.addLayout(right, 2)

        # telemetry cards
        grid = QGridLayout(); right.addLayout(grid)
        self.cards = {}
        for n, (k, t) in enumerate([
            ("velocity", "Velocity (m/s)"), ("omega",   "Omega (rad/s)"),
            ("battery",  "Battery (%)"),    ("rpm_l",   "RPM-L"),
            ("rpm_r",    "RPM-R")]):
            c = Card(t); self.cards[k] = c.val
            grid.addWidget(c, n // 2, n % 2)

        # goal entry row
        goal_row = QHBoxLayout(); right.addLayout(goal_row)
        goal_row.addWidget(QLabel("Goal X:"))
        self.goal_x = QLineEdit("18"); self.goal_x.setFixedWidth(60)
        goal_row.addWidget(self.goal_x)
        goal_row.addWidget(QLabel("Y:"))
        self.goal_y = QLineEdit("8");  self.goal_y.setFixedWidth(60)
        goal_row.addWidget(self.goal_y)
        set_btn = QPushButton("Set goal"); goal_row.addWidget(set_btn)
        set_btn.clicked.connect(self._set_goal)

        # manual toggle
        self.cb = QCheckBox("Manual arrow-key drive")
        self.cb.stateChanged.connect(self._toggle_mode)
        right.addWidget(self.cb)

        # log pane
        right.addWidget(QLabel("Logs:"))
        self.log = QTextEdit(readOnly=True)
        self.log.setStyleSheet("background:#101;color:#ccc")
        right.addWidget(self.log, 1)

        # arrow / stop buttons (only active in manual)
        row = QHBoxLayout(); right.addLayout(row)
        for k, txt in [("l","←"), ("f","↑"), ("r","→"),
                       ("b","↓"), ("s","■")]:
            b = QPushButton(txt); b.setFixedSize(48,48)
            if k == "s": b.setStyleSheet("background:red;color:white")
            row.addWidget(b); b.clicked.connect(
                lambda _, kk=k: self._btn(kk))

        # websocket
        self.ws = QWebSocket()
        self.ws.textMessageReceived.connect(self._rx)
        self.ws.open(QUrl("ws://localhost:8765"))

    # ── WebSocket helpers ───────────────────────────────────────
    def _send(self, obj: dict):
        if self.ws.state() == QAbstractSocket.ConnectedState:
            self.ws.sendTextMessage(json.dumps(obj))

    def _toggle_mode(self, state: int):
        self.manual = bool(state)
        self._send({"type": "mode",
                    "mode": "manual" if self.manual else "auto"})

    def _set_goal(self):
        try:
            gx = float(self.goal_x.text())
            gy = float(self.goal_y.text())
        except ValueError:
            self.log.append("<b>Invalid goal coordinates</b>")
            return
        self.goal = (gx, gy)
        self._send({"type": "goal", "x": gx, "y": gy})
        if self.manual:                      # flip back to auto
            self.cb.setChecked(False)        # triggers _toggle_mode

    # arrow / stop buttons
    def _btn(self, k: str):
        if not self.manual:
            return
        v, w = {"f": (0.5, 0),   "b": (-0.5, 0),
                "l": (0, 1.2),   "r": (0, -1.2),
                "s": (0, 0)}[k]
        self._send({"type": "cmd_vel", "v": v, "w": w})

    # arrow-key hold-to-drive
    def keyPressEvent(self, e):
        if not self.manual or e.isAutoRepeat(): return
        m = {Qt.Key_Up:    (0.5, 0),
             Qt.Key_Down: (-0.5, 0),
             Qt.Key_Left:  (0, 1.2),
             Qt.Key_Right: (0, -1.2)}
        if e.key() in m:
            v, w = m[e.key()]
            self._send({"type": "cmd_vel", "v": v, "w": w})

    def keyReleaseEvent(self, e):
        if not self.manual or e.isAutoRepeat(): return
        if e.key() in (Qt.Key_Up, Qt.Key_Down,
                       Qt.Key_Left, Qt.Key_Right):
            self._send({"type": "cmd_vel", "v": 0, "w": 0})

    # ── WebSocket RX ────────────────────────────────────────────
    def _rx(self, txt: str):
        d = json.loads(txt)
        if d.get("type") != "telemetry" or "pose" not in d:
            return

        # path from server (remaining way-points)
        if "path" in d: self.path = d["path"]

        pose, ts = d["pose"], d["ts"]

        # cards
        if self.prev_pose:
            dt = (ts - self.prev_ts) / 1000
            dx = pose["x"] - self.prev_pose["x"]
            dy = pose["y"] - self.prev_pose["y"]
            v  = math.hypot(dx, dy) / dt
            dyaw = (pose["yaw"] - self.prev_pose["yaw"] + 180) % 360 - 180
            w  = math.radians(dyaw) / dt
            self.cards["velocity"].setText(f"{v:.2f}")
            self.cards["omega"]   .setText(f"{w:.2f}")
        self.prev_pose, self.prev_ts = pose, ts
        self.cards["battery"].setText(f"{d['battery']:.0f}")
        self.cards["rpm_l"]  .setText(f"{d['enc_rpm'][0]:.0f}")
        self.cards["rpm_r"]  .setText(f"{d['enc_rpm'][1]:.0f}")

        # proximity alert
        closest = min(d["scan"]["ranges"])
        if closest < 0.25:
            self.log.append(
                f'<span style="color:#ff6b6b">ALERT {closest:.2f} m – '
                'obstacle very close!</span>')

        # static grid comes once
        if self.base is None:
            g = d["grid"]
            self.base = np.frombuffer(base64.b64decode(g["data"]), np.uint8
                       ).reshape((g["h"], g["w"]))

        self._draw(pose, d["scan"])

    # ── drawing helper ──────────────────────────────────────────
    def _draw(self, pose: dict, scan: dict):
        img = self.base.copy()
        a0  = math.radians(scan["angle_min"])
        inc = math.radians(scan["angle_inc"])
        for i, r in enumerate(scan["ranges"]):
            if r >= 10.0: continue
            ang = a0 + i * inc + math.radians(pose["yaw"])
            gx  = pose["x"] + r * math.cos(ang)
            gy  = pose["y"] + r * math.sin(ang)
            cx, cy = int(gx / self.res), int(gy / self.res)
            if 0 <= cy < img.shape[0] and 0 <= cx < img.shape[1]:
                img[cy, cx] = 200                   # grey free-space

        h, w = img.shape
        qimg = QImage(img.data, w, h, QImage.Format_Grayscale8)
        pix  = QPixmap.fromImage(qimg).scaled(
                   self.live_lbl.size(),
                   Qt.KeepAspectRatio,
                   Qt.FastTransformation)

        painter = QPainter(pix)
        sx, sy = pix.width() / w, pix.height() / h

        # grid every 2 m; tick labels every 4 m
        painter.setPen(QColor(55, 55, 55))
        step = int(2 / self.res)
        for cx in range(0, w, step):
            x_pix = int(cx * sx)
            painter.drawLine(x_pix, 0, x_pix, pix.height())
        for cy in range(0, h, step):
            y_pix = int(cy * sy)
            painter.drawLine(0, y_pix, pix.width(), y_pix)
        painter.setPen(Qt.gray)
        tick = int(4 / self.res)
        for cx in range(0, w, tick):
            painter.drawText(int(cx * sx) + 2, 12, str(int(cx * self.res)))
        for cy in range(0, h, tick):
            painter.drawText(2, int(cy * sy) - 2, str(int(cy * self.res)))

        # A* path (white poly-line)
        if self.path and len(self.path) > 1:
            painter.setPen(Qt.white)
            for i in range(len(self.path) - 1):
                x1, y1 = self.path[i]
                x2, y2 = self.path[i + 1]
                painter.drawLine(int(x1 / self.res * sx),
                                 int(y1 / self.res * sy),
                                 int(x2 / self.res * sx),
                                 int(y2 / self.res * sy))

        # robot square + heading arrow
        cx_pix = pose["x"] / self.res * sx
        cy_pix = pose["y"] / self.res * sy
        painter.setBrush(QBrush(Qt.white))
        painter.drawRect(int(cx_pix) - 4, int(cy_pix) - 4, 8, 8)

        yaw_rad = math.radians(pose["yaw"])
        tip  = QPointF(cx_pix + 12 * math.cos(yaw_rad),
                       cy_pix + 12 * math.sin(yaw_rad))
        left = QPointF(cx_pix + 6 * math.cos(yaw_rad + 2.6),
                       cy_pix + 6 * math.sin(yaw_rad + 2.6))
        right= QPointF(cx_pix + 6 * math.cos(yaw_rad - 2.6),
                       cy_pix + 6 * math.sin(yaw_rad - 2.6))
        painter.drawPolygon(QPolygonF([tip, left, right]))

        # goal mark
        if self.goal:
            gx_pix = self.goal[0] / self.res * sx
            gy_pix = self.goal[1] / self.res * sy
            painter.drawLine(int(gx_pix - 6), int(gy_pix - 6),
                             int(gx_pix + 6), int(gy_pix + 6))
            painter.drawLine(int(gx_pix - 6), int(gy_pix + 6),
                             int(gx_pix + 6), int(gy_pix - 6))

        painter.end()
        self.live_lbl.setPixmap(pix)

        # draw static map once (scaled)
        if not self._static_done:
            s_img = QImage(self.base.data, w, h, QImage.Format_Grayscale8)
            s_pix = QPixmap.fromImage(s_img).scaled(
                        self.static_lbl.size(),
                        Qt.KeepAspectRatio,
                        Qt.FastTransformation)
            self.static_lbl.setPixmap(s_pix)
            self._static_done = True


# ── run app ────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    Dashboard().show()
    sys.exit(app.exec_())
