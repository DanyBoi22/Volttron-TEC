import sys
import json
import requests
from PyQt6.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout, QTextEdit, QLabel
)
from PyQt6.QtCore import QThread, pyqtSignal

"""
Basic test gui, to test compatibility with existing platform
"""

# --- Worker thread to make HTTP request ---
class FetchThread(QThread):
    result_ready = pyqtSignal(dict)
    error = pyqtSignal(str)

    def run(self):
        try:
            response = requests.get("http://172.23.68.187:8000/experiments/all/data")
            response.raise_for_status()
            data = response.json()
            self.result_ready.emit(data)
        except Exception as e:
            self.error.emit(str(e))


# --- Main Window ---
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Volttron Control UI")

        self.label = QLabel("Fetch experiment list:")
        self.text = QTextEdit()
        self.text.setReadOnly(True)

        self.button = QPushButton("Fetch Experiments")
        self.button.clicked.connect(self.fetch_data)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.text)
        layout.addWidget(self.button)
        self.setLayout(layout)

    def fetch_data(self):
        self.text.setText("Fetching...")
        self.thread = FetchThread()
        self.thread.result_ready.connect(self.show_data)
        self.thread.error.connect(self.show_error)
        self.thread.start()

    def show_data(self, data):
        self.text.setText(json.dumps(data, indent=2))

    def show_error(self, msg):
        self.text.setText(f"Error: {msg}")


# --- Entry point ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(600, 400)
    window.show()
    sys.exit(app.exec())
