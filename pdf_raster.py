"""Keep transparent PDF paper white for grayscale optical recognition."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter


def opaque_score_page(image):
    if image.isNull():
        return image
    paper=QImage(image.size(),QImage.Format.Format_RGB32)
    paper.fill(Qt.GlobalColor.white)
    painter=QPainter(paper)
    try:
        painter.drawImage(0,0,image)
    finally:
        painter.end()
    return paper
