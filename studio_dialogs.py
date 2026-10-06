"""Theme only dialogs belonging to the studio; preserve their Qt semantics."""
from PySide6.QtCore import QObject, QEvent, Qt
from PySide6.QtWidgets import QApplication, QMessageBox, QInputDialog,QProxyStyle,QStyle


class NoFocusFrameStyle(QProxyStyle):
    """Keep keyboard focus/Enter/Escape, but never paint native focus boxes."""
    def drawPrimitive(self,element,option,painter,widget=None):
        if element!=QStyle.PE_FrameFocusRect:super().drawPrimitive(element,option,painter,widget)


def suppress_focus_frames(widget):
    # Clone by style name: do not reparent or modify QApplication's shared style.
    style=NoFocusFrameStyle(QApplication.instance().style().objectName())
    style.setParent(widget);widget.setStyle(style)
    return style

STYLE = """
QMessageBox, QInputDialog {background:#24262b; color:#eadfc9;
 border:1px solid #b39766; border-radius:10px; padding:18px;font-family:"Segoe UI";}
QMessageBox QLabel, QInputDialog QLabel {color:#eadfc9; border:0; background:transparent;font-family:"Segoe UI";}
QMessageBox QPushButton, QInputDialog QPushButton {color:#e8e3da;
 background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #41434a,stop:1 #282a30);
 border:1px solid #55565b; border-radius:6px; padding:8px 16px; min-height:18px;font-family:"Segoe UI";}
QMessageBox QPushButton:hover, QInputDialog QPushButton:hover {border-color:#dfb87c;}
QMessageBox QPushButton[studioPrimary="true"] {color:#241b0d;border-color:#d8b780;
 background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #f0d5aa,stop:1 #c59a5f);}
QMessageBox QPushButton:focus, QInputDialog QPushButton:focus {background:#44403a;}
QInputDialog QComboBox, QInputDialog QLineEdit {background:#14171b;color:#eadfc9;
 border:1px solid #55565b;padding:6px;}
QMenu {background:#24262b;color:#eadfc9;border:1px solid #b39766;padding:5px;}
QMenu::item {padding:7px 18px;}
QMenu::item:selected {background:#59482e;color:#ffe0a8;}
"""

class StudioDialogTheme(QObject):
    def __init__(self, root):
        super().__init__(root)
        self.root = root
        self.focus_style=suppress_focus_frames(root)
        root.setStyleSheet(root.styleSheet() + STYLE)
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Polish and isinstance(watched, (QMessageBox, QInputDialog)):
            parent = watched.parent()
            while parent is not None and parent is not self.root:
                parent = parent.parent()
            if parent is self.root:
                # Remove the unthemed Windows caption before the dialog is shown.
                watched.setWindowFlag(Qt.FramelessWindowHint, True)
                if isinstance(watched, QMessageBox):
                    for button in watched.buttons():
                        button.setProperty("studioPrimary", watched.buttonRole(button)==QMessageBox.AcceptRole)
                        button.style().unpolish(button)
                        button.style().polish(button)
        return False
