import sys
from PyQt5.QtWidgets import QApplication
from splash_screen import SplashScreen
from dashboard import Dashboard

# Keep references to windows to avoid garbage collection
dashboard = None

def main():
    app = QApplication(sys.argv)

    def show_dashboard():
        global dashboard  # So Python doesn't delete it
        dashboard = Dashboard()
        dashboard.show()

    splash = SplashScreen(on_finish=show_dashboard)
    splash.show()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
