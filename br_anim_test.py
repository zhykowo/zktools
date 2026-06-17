import sys
from PySide6.QtCore import QPropertyAnimation, QEasingCurve, Property
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget

class AnimatedButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self._radius = 0
        self.setMinimumSize(200, 60)
        self.update_style()

        # Initialize the Qt property animation
        self.animation = QPropertyAnimation(self, b"radius")
        self.animation.setDuration(300) # Duration in milliseconds
        self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

    # Define a Qt-aware getter
    @Property(int)
    def radius(self):
        return self._radius

    # Define a Qt-aware setter that modifies the stylesheet
    @radius.setter
    def radius(self, value):
        self._radius = value
        self.update_style()

    def update_style(self):
        # Dynamically updates the QSS rule string
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: #3498db;
                color: white;
                border-style: solid;
                border-radius: {self._radius}px;
                font-size: 16px;
                border: 2px solid #2980b9;
            }}
            QPushButton:hover {{
                background-color: #2980b9;
            }}
        """)

    # Trigger animation on hover events
    def enterEvent(self, event):
        self.animation.stop()
        self.animation.setStartValue(self._radius)
        self.animation.setEndValue(30) # Fully rounded corners
        self.animation.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.animation.stop()
        self.animation.setStartValue(self._radius)
        self.animation.setEndValue(0) # Square corners
        self.animation.start()
        super().leaveEvent(event)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PySide6 Border Radius Animation")
        self.resize(400, 300)

        layout = QVBoxLayout()
        self.btn = AnimatedButton("Hover Over Me!")
        layout.addWidget(self.btn)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.argv[0] = "Radius Anim"
    sys.exit(app.exec())
