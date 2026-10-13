STYLE = """
QWidget { color:#eceef3; font-family:Segoe UI; font-size:13px; }
QMainWindow,QWidget#studioRoot { background:#1d2026; }
QFrame#inspector,QWidget#panelContent { background:#232730; }
QFrame#inspector { border:1px solid #353b47; border-radius:8px; }
QLabel { background:transparent; }
QLabel#brand { font-size:22px; font-weight:600; padding-right:4px; }
QLabel#title { font-size:19px; font-weight:600; }
QLabel#subtitle,QLabel#muted { color:#adb5c4; font-size:12px; }
QLabel#section { color:#d2d8e3; padding-left:6px; }
QLabel#value { color:#c1d3ff; font-size:12px; min-width:40px; }
QLabel#sessionStatus { color:#c5cbd6; padding:4px 0; }
QPushButton { background:#2b3039; border:1px solid #48505e; border-radius:5px; padding:8px 10px; min-height:17px; }
QPushButton:hover { background:#353d4a; border-color:#7c8ba5; }
QPushButton:pressed { background:#404c60; }
QPushButton:checked { background:#344769; color:#eef4ff; border-color:#85a4e0; }
QPushButton:focus,QLineEdit:focus,QComboBox:focus,QSpinBox:focus { border:1px solid #a9c3ff; }
QPushButton:disabled { color:#858d9a; background:#262a32; border-color:#373e49; }
QPushButton#primary { background:#4d69a3; color:white; border-color:#7d9dd5; }
QPushButton#primary:hover { background:#5c7bbb; }
QPushButton#nav { border:1px solid transparent; background:transparent; color:#b7bfcd; padding:8px; }
QPushButton#nav:checked { background:#303c51; color:#f5f8ff; border-color:#536f9e; }
QPushButton#nav:hover { background:#2c3442; }
QPushButton#nav:focus { border-color:#a9c3ff; }
QPushButton#disclosure { text-align:left; background:transparent; border-color:#414b5b; }
QLineEdit,QComboBox,QSpinBox { background:#191d24; border:1px solid #4c5667; border-radius:5px; padding:7px; min-height:17px; selection-background-color:#5675b5; }
QComboBox::drop-down { border:0; width:24px; }
QComboBox QAbstractItemView { background:#252c38; border:1px solid #61718b; selection-background-color:#405a88; }
QGroupBox { border:1px solid #404a59; border-radius:6px; margin-top:12px; padding:14px 10px 10px; background:#232730; }
QGroupBox::title { subcontrol-origin:margin; left:10px; padding:0 5px; color:#e0e6f0; }
QProgressBar { border:0; background:#3b4351; height:6px; max-height:6px; border-radius:3px; }
QProgressBar::chunk { background:#93b3ef; border-radius:3px; }
QSlider::groove:horizontal { height:5px; background:#46536a; border-radius:2px; }
QSlider::sub-page:horizontal { background:#7b9cda; border-radius:2px; }
QSlider::handle:horizontal { background:#d2e1ff; width:16px; margin:-6px 0; border-radius:7px; border:1px solid #adc8fb; }
QSlider:focus::handle:horizontal { border:2px solid white; }
QCheckBox { spacing:8px; color:#d5dce8; padding:3px 0; }
QCheckBox::indicator { width:18px; height:18px; }
QScrollArea { border:0; background:transparent; }
QScrollBar:vertical { background:#232730; width:10px; margin:2px; }
QScrollBar::handle:vertical { background:#67748a; border-radius:4px; min-height:28px; }
QScrollBar::handle:vertical:hover { background:#8a9ab4; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical { background:transparent; }
QSplitter::handle { background:#363e4b; }
QSplitter::handle:hover { background:#7188ae; }
QListWidget { background:#191d24; border:1px solid #465166; border-radius:5px; padding:3px; }
QListWidget::item { padding:3px; border-radius:4px; }
QListWidget::item:selected { background:#354b70; color:white; }
QListWidget::item:hover { background:#2c384d; }
QStatusBar { background:#191c22; color:#adb5c4; border-top:1px solid #373f4c; }
QMenuBar { background:#1d2026; color:#cbd3df; }
QMenuBar::item:selected { background:#374865; }
QMenu { background:#252c38; border:1px solid #586781; padding:4px; }
QMenu::item { padding:8px 22px; }
QMenu::item:selected { background:#405a88; }
QToolTip { color:#f5f7fb; background:#303a4b; border:1px solid #8297b9; padding:7px; }
"""
