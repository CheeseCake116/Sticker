import os, sys
from PyQt5.QtWidgets import QMainWindow, QFileDialog, QLabel, QPushButton, QGroupBox, QSlider, QHBoxLayout, QVBoxLayout, QWidget, QApplication
from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QIcon, QFont
from PIL import Image, ImageQt

currentDir = os.getcwd()

try:
    meipassDir = sys._MEIPASS
except:
    meipassDir = currentDir

os.chdir(meipassDir)
# manageWindowUi = uic.loadUiType("./manage.ui")[0]
iconPath = os.path.abspath("./lise.ico")
liseImage = os.path.abspath("./lise.png")
os.chdir(currentDir)

class ManageWindow(QWidget):
    addEvent = pyqtSignal()
    loadEvent = pyqtSignal()
    quitEvent = pyqtSignal()
    endEvent = pyqtSignal()
    bgmChangeEvent = pyqtSignal(list)
    bgmVolumeEvent = pyqtSignal(int)

    def __init__(self, bgmVolume=70):
        super().__init__()
        # self.setupUi(self)  # UI 로딩
        self.setWindowIcon(QIcon(iconPath))
        self.setWindowTitle("라오 위젯 설정")
        # self.setFixedSize(457, 344)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        self.initUI()

        self.newButton.released.connect(self.addHandler)
        self.loadButton.released.connect(self.loadHandler)
        self.quitButton.released.connect(self.endHandler)
        self.bgmButton.released.connect(self.setBGM)
        self.bgmRemoveButton.released.connect(self.removeBGM)
        self.volumeSlider.setValue(bgmVolume)
        self.volumeSlider.valueChanged.connect(self.setBGMVolume)

    def initUI(self):
        # 상단 버튼들
        self.newButton = QPushButton("새 부관 추가")
        self.loadButton = QPushButton("부관 다시 불러오기")
        self.quitButton = QPushButton("라오 위젯 종료")

        # 배경음 그룹박스
        self.BGMGroupBox = QGroupBox("배경음")
        self.bgmButton = QPushButton("배경음 설정")
        self.bgmRemoveButton = QPushButton("배경음 제거")
        self.volumeLabel = QLabel("볼륨")
        self.volumeSlider = QSlider()
        self.bgmLabel = QLabel("(여러 개 선택 시 순차 재생)")

        # 디얍 이미지
        self.diyap_label = QLabel("그림: 디얍")
        self.diyap_image = QLabel()
        img = Image.open(liseImage)
        croppedImg = img.crop((0, 0, 256, 315))
        self.diyap_image.setPixmap(ImageQt.toqpixmap(croppedImg))

        # 배경음 그룹박스 구성
        bgmVBL = QVBoxLayout()

        bgmVBL_H = QHBoxLayout()
        bgmVBL_H.addWidget(self.volumeLabel, alignment=Qt.AlignLeft)
        bgmVBL_H.addWidget(self.volumeSlider)
        bgmVBL_H.setContentsMargins(0, 0, 0, 0)
        bgmVBL_H_Widget = QWidget()
        bgmVBL_H_Widget.setLayout(bgmVBL_H)

        bgmVBL.addWidget(self.bgmButton)
        bgmVBL.addWidget(self.bgmRemoveButton)
        bgmVBL.addWidget(bgmVBL_H_Widget)
        self.BGMGroupBox.setLayout(bgmVBL)

        # 전체 레이아웃
        mainLayout = QHBoxLayout()
        mainLayout.setContentsMargins(0, 0, 0, 0)

        leftBox = QVBoxLayout()
        leftBox.setContentsMargins(20, 20, 20, 20)
        leftBox.addWidget(self.newButton)
        leftBox.addWidget(self.loadButton)
        leftBox.addWidget(self.quitButton)
        leftBox.addStretch(1)
        leftBox.addWidget(self.BGMGroupBox)
        leftBox.addWidget(self.bgmLabel, alignment=Qt.AlignLeft)
        leftBoxWidget = QWidget()
        leftBoxWidget.setLayout(leftBox)
        mainLayout.addWidget(leftBoxWidget)

        rightBox = QVBoxLayout()
        rightBox.setContentsMargins(0, 0, 0, 0)
        rightBox.addStretch(1)
        rightBox.addWidget(self.diyap_label, alignment=Qt.AlignRight)
        rightBox.addWidget(self.diyap_image)
        rightBoxWidget = QWidget()
        rightBoxWidget.setLayout(rightBox)
        mainLayout.addWidget(rightBoxWidget)
        mainLayout.addStretch(1)

        self.setLayout(mainLayout)

        # 레이아웃 기타 설정
        self.newButton.setMinimumHeight(31)
        self.loadButton.setMinimumHeight(31)
        self.quitButton.setMinimumHeight(31)

        self.volumeLabel.setStyleSheet("padding: 0px 5px 0px 0px")
        self.volumeSlider.setMinimum(0)
        self.volumeSlider.setMaximum(99)
        self.volumeSlider.setSingleStep(1)
        self.volumeSlider.setPageStep(10)
        self.volumeSlider.setValue(99)
        self.volumeSlider.setOrientation(Qt.Horizontal)

        self.diyap_label.setStyleSheet("padding: 20px 20px 0px 0px")


    def addHandler(self):
        self.addEvent.emit()

    def loadHandler(self):
        self.loadEvent.emit()

    def endHandler(self):
        self.endEvent.emit()

    def setBGM(self):
        fname = QFileDialog.getOpenFileNames(self, "배경음 선택", "./bgm", "Audio File(*.mp3 *.wav)")
        if fname[0]:
            self.bgmFile = fname[0]
            self.bgmChangeEvent.emit(self.bgmFile)

    def removeBGM(self):
        self.bgmFile = []
        self.bgmChangeEvent.emit(self.bgmFile)

    def setBGMVolume(self):
        self.bgmVolumeEvent.emit(self.volumeSlider.value())

    def manageQuit(self):
        self.close()

    def closeEvent(self, event):
        event.ignore()
        self.hide()