import os, sys, random, time, subprocess
from PyQt5.QtWidgets import *
from PyQt5.QtCore import QThread, pyqtSignal, QSize, Qt, pyqtSlot
from PyQt5.QtGui import QIcon, QCursor, QIntValidator, QMovie, QPixmap
from PIL import Image, ImageQt
from pygame import mixer



currentDir = os.getcwd()

try:
    meipassDir = sys._MEIPASS
except:
    meipassDir = currentDir

os.chdir(meipassDir)
iconPath = os.path.abspath("./lise.ico")
loadImg = os.path.abspath("./loading.png")
# secondWindowUi = uic.loadUiType("./setting.ui")[0]
os.chdir(currentDir)
ffmpegEXE = os.path.abspath("./ffmpeg/ffmpeg.exe").replace("\\", "/")

class Loading(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("webm 변환중")
        self.setWindowIcon(QIcon(iconPath))
        self.loadLabel = QLabel('', self)

        self.loadPix = QPixmap(loadImg)
        self.loadLabel.setPixmap(self.loadPix)


class Sticker(QMainWindow):
    key = -1
    managerObj = None
    AlwaysOnTop = True

    chaFile = ""
    isSizeRestricted = False
    chaSize = 400

    loginVoiceFile = []
    idleVoiceFile = []
    voiceVolume = 50
    voiceSound = None

    bgmFile = ""
    bgmVolume = 50
    bgmSound = None
    bgmTh = None

    m_flag = False
    m_Position = None
    secondWindow = None
    clickTime = 0 # check whether active voice or not

    saveEvent = pyqtSignal(dict)
    assignEvent = pyqtSignal(str, object)
    manageEvent = pyqtSignal() # 부관 설정창 열기
    groupEvent = pyqtSignal() # 그룹 설정창 열기
    presetEvent = pyqtSignal() # 프리셋 설정창 열기
    removeEvent = pyqtSignal(str) # 부관 업무에서 해제
    quitEvent = pyqtSignal() # 프로그램 종료

    def __init__(self, manager, data, key):
        super().__init__()
        self.managerObj = manager
        self.key = key
        self.setWindowTitle("라오 부관")
        self.setWindowIcon(QIcon(iconPath))

        self.saveEvent.connect(self.managerObj.stickerSave)
        self.assignEvent.connect(self.managerObj.stickerAssign)
        self.manageEvent.connect(self.managerObj.openManageUi)
        # self.groupEvent.connect(self.managerObj.openGroupUi) # 그룹 기능 확정될때까지
        self.presetEvent.connect(self.managerObj.openPresetUi)
        self.removeEvent.connect(self.managerObj.stickerRemove)
        self.quitEvent.connect(self.managerObj.programQuit)

        self.cmenu = QMenu(self)
        self.menu_setting = self.cmenu.addAction("부관 설정")
        self.menu_group = self.cmenu.addAction("그룹 설정")
        self.menu_preset = self.cmenu.addAction("프리셋 설정")
        self.menu_hide = self.cmenu.addAction("숨기기")
        self.menu_retire = self.cmenu.addAction("부관 업무에서 해제")
        self.cmenu.addSeparator()
        self.menu_manage = self.cmenu.addAction("위젯 설정")
        self.menu_quit = self.cmenu.addAction("종료")

        self.chaLabel = QLabel('', self)
        self.readDataFile(data)

        if os.path.exists(self.chaFile) is False:
            self.openSetting(new=True)

        self.setCharacter()
        self.setupWindow()

    def readDataFile(self, jsonData):
        try:
            if jsonData:
                if "Position" in jsonData:
                    pos = jsonData["Position"]
                    self.move(pos[0], pos[1])
                if "AlwaysOnTop" in jsonData:
                    self.AlwaysOnTop = jsonData["AlwaysOnTop"]
                if 'CharacterImage' in jsonData:
                    self.chaFile = jsonData['CharacterImage']
                if 'LoginVoiceFiles' in jsonData:
                    self.loginVoiceFile = jsonData['LoginVoiceFiles']
                if 'IdleVoiceFiles' in jsonData:
                    self.idleVoiceFile = jsonData['IdleVoiceFiles']
                if 'SizeRestrict' in jsonData:
                    self.isSizeRestricted = jsonData['SizeRestrict']
                if 'CharacterSize' in jsonData:
                    self.chaSize = jsonData['CharacterSize']
                if 'VoiceVolume' in jsonData:
                    self.voiceVolume = jsonData['VoiceVolume']
        except Exception as e:
            print("read Exception: " + str(e))

    def writeDataFile(self):
        pos = self.pos()
        data = {
            self.key: {
                "Position": (pos.x(), pos.y()),
                "AlwaysOnTop": self.AlwaysOnTop,
                "CharacterImage": self.chaFile,
                "LoginVoiceFiles": self.loginVoiceFile,
                "IdleVoiceFiles": self.idleVoiceFile,
                "CharacterSize": self.chaSize,
                "SizeRestrict": self.isSizeRestricted,
                "VoiceVolume": self.voiceVolume
            }
        }
        self.saveEvent.emit(data)

    def setCharacter(self):
        try:
            if os.path.exists(self.chaFile) is False:
                return

            if self.chaFile.split(".")[-1] in ["webm"]:
                self.openSetting()
                return

            img = Image.open(self.chaFile)
            width, height = img.size

            # if self.chaSize > 0
            if self.isSizeRestricted and self.chaSize:
                maxsize = self.chaSize

                if width >= height:
                    height = int(height / width * maxsize)
                    width = maxsize
                else:
                    width = int(width / height * maxsize)
                    height = maxsize
            self.chaLabel.resize(width, height)
            self.setFixedSize(width, height)

            if self.chaFile.split(".")[-1] in ["gif"]:
                movie = QMovie(self.chaFile)
                movie.setScaledSize(QSize(width, height))
                self.chaLabel.setMovie(movie)
                movie.start()

            elif self.chaFile.split(".")[-1] in ["webm"]:
                self.convertWebmtoGif()
                movie = QMovie(self.chaFile)
                movie.setScaledSize(QSize(width, height))
                self.chaLabel.setMovie(movie)
                movie.start()

            else:
                pilImage = Image.open(self.chaFile)
                pilImage_resize = pilImage.resize((width, height), Image.Resampling.LANCZOS)
                self.chaLabel.setPixmap(ImageQt.toqpixmap(pilImage_resize))

        except Exception as e:
            print("Character Exception: " + str(e))

    def loginVoicePlay(self, voiceIndex=0):
        # loginVoice 목록이 존재하는가
        if not self.loginVoiceFile:
            return

        # voiceIndex가 -1이면 랜덤재생
        if voiceIndex == -1:
            voiceIndex = random.randrange(0, len(self.loginVoiceFile))

        # 인덱스가 크기를 벗어나진 않는가, 보이스 파일이 존재하는가
        if voiceIndex >= len(self.loginVoiceFile) or os.path.exists(self.loginVoiceFile[voiceIndex]) is False:
            return

        try:
            if self.voiceSound is not None:
                self.voiceSound.stop()

            freq = 44100  # sampling rate, 44100(CD), 16000(Naver TTS), 24000(google TTS)
            bitsize = -16  # signed 16 bit. support 8,-8,16,-16
            channels = 2  # 1 is mono, 2 is stereo
            buffer = 2048  # number of samples (experiment to get right sound)

            # default : pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=4096)
            mixer.init(freq, bitsize, channels, buffer)
            self.voiceSound = mixer.Sound(self.loginVoiceFile[voiceIndex])
            self.voiceSound.set_volume(self.voiceVolume / 100)
            self.voiceSound.play()

        except Exception as e:
            print("LoginVoice Exception: " + str(e))

    def idleVoicePlay(self, voiceIndex=0):
        if self.idleVoiceFile == [] or voiceIndex >= len(self.idleVoiceFile) or os.path.exists(self.idleVoiceFile[voiceIndex]) is False:
            return

        try:
            if self.voiceSound is not None:
                self.voiceSound.stop()

            freq = 44100  # sampling rate, 44100(CD), 16000(Naver TTS), 24000(google TTS)
            bitsize = -16  # signed 16 bit. support 8,-8,16,-16
            channels = 2  # 1 is mono, 2 is stereo
            buffer = 2048  # number of samples (experiment to get right sound)

            # default : pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=4096)
            mixer.init(freq, bitsize, channels, buffer)
            self.voiceSound = mixer.Sound(self.idleVoiceFile[voiceIndex])
            self.voiceSound.set_volume(self.voiceVolume / 100)
            self.voiceSound.play()

        except Exception as e:
            print("IdleVoice Exception: " + str(e))

    # MOUSE Click drag EVENT function
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clickTime = time.time()
            self.m_flag = True
            self.m_Position = event.globalPos() - self.pos()  # Get the position of the mouse relative to the window
            event.accept()
            self.setCursor(QCursor(Qt.OpenHandCursor))  # Change mouse icon

    def mouseMoveEvent(self, QMouseEvent):
        if Qt.LeftButton and self.m_flag:
            self.move(QMouseEvent.globalPos() - self.m_Position)  # Change window position
            QMouseEvent.accept()

    def mouseReleaseEvent(self, QMouseEvent):
        if self.m_flag:
            if time.time() - self.clickTime < 0.4:
                self.characterTouch()

        self.writeDataFile()
        self.m_flag = False
        self.setCursor(QCursor(Qt.ArrowCursor))

    def characterTouch(self):
        if self.idleVoiceFile:
            voiceIndex = random.randrange(0, len(self.idleVoiceFile))
            self.idleVoicePlay(voiceIndex)

    def stickerHide(self):
        self.hide()

    def stickerQuit(self):
        self.close()

    def setupWindow(self):
        centralWidget = QWidget(self)
        self.setCentralWidget(centralWidget)

        if self.AlwaysOnTop:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.show()

    def contextMenuEvent(self, event):
        action = self.cmenu.exec_(self.mapToGlobal(event.pos()))
        if action == self.menu_hide: # 숨기기
            self.stickerHide()
        elif action == self.menu_setting: # 부관 설정
            self.openSetting(new=False)
        elif action == self.menu_group: # 그룹 설정
            self.groupEvent.emit()
        elif action == self.menu_preset: # 프리셋 설정
            self.presetEvent.emit()
        elif action == self.menu_manage: # 위젯 설정
            self.manageEvent.emit()
        elif action == self.menu_retire: # 부관 임무에서 해제
            self.removeEvent.emit(self.key)
        elif action == self.menu_quit: # 종료
            self.quitEvent.emit()

    def openSetting(self, new=False):
        if self.secondWindow is None:
            self.secondWindow = SecondWindow(new)
            self.secondWindow.setParent(self)
            self.secondWindow.setSetting(self.chaFile, self.loginVoiceFile, self.idleVoiceFile, self.chaSize, self.voiceVolume,
                                         self.isSizeRestricted, self.AlwaysOnTop)
            r = self.secondWindow.showModal()

            if r:
                # 캐릭터 파일
                if os.path.exists(self.secondWindow.chaFile):
                    if not self.chaFile:
                        # 스티커 생성
                        self.assignEvent.emit(self.key, self)

                    self.chaFile = self.secondWindow.chaFile

                # 캐릭터 크기 제한
                self.isSizeRestricted = self.secondWindow.imageCheckBox.isChecked()

                # 캐릭터 사이즈
                try:
                    if self.secondWindow.chaSizeLine.text():
                        self.chaSize = int(self.secondWindow.chaSizeLine.text())
                    else:
                        self.chaSize = 0
                except:
                    pass

                # 접속 대사
                tempLoginVoice = []
                for file in self.secondWindow.loginVoiceFile:
                    if os.path.exists(file):
                        tempLoginVoice.append(file)
                if tempLoginVoice:
                    self.loginVoiceFile = self.secondWindow.loginVoiceFile

                # 일반 대사
                tempIdleVoice = []
                for file in self.secondWindow.idleVoiceFile:
                    if os.path.exists(file):
                        tempIdleVoice.append(file)
                if tempIdleVoice:
                    self.idleVoiceFile = self.secondWindow.idleVoiceFile

                # Always on Top 설정
                if self.AlwaysOnTop != self.secondWindow.AOTCheckBox.isChecked():
                    self.AlwaysOnTop = self.secondWindow.AOTCheckBox.isChecked()
                    self.setupWindow()

                self.voiceVolume = self.secondWindow.voiceSlider.value()
                self.setCharacter()
                self.writeDataFile()
            else:
                if os.path.exists(self.chaFile) is False:
                    self.removeEvent.emit(self.key)
                    self.stickerQuit()

        self.secondWindow = None


class SecondWindow(QDialog, QWidget):
    parent = None
    chaFile = ""
    isSizeRestricted = True

    loginVoiceFile = []
    idleVoiceFile = []

    convertTh = None
    '''
        chaLabel
        loginVoice_label
        idleVoice_label

        chaButton
        loginVoiceButton
        idleVoiceButton
        applyButton
        cancelButton

        voiceSlider

        imageCheckBox

        chaSizeLineedit
    '''

    def __init__(self, new=False):
        super().__init__()
        self.initUI()
        if new:
            self.setWindowTitle("새 부관 추가")
        else:
            self.setWindowTitle("부관 설정")
        self.setWindowIcon(QIcon(iconPath))
        self.setWindowFlags(Qt.WindowStaysOnTopHint) # | Qt.AA_DisableHighDpiScaling)
        # self.setFixedSize(301, 310)

        self.chaButton.clicked.connect(self.setCharacter)
        self.loginVoiceButton.clicked.connect(self.setLoginVoice)
        self.idleVoiceButton.clicked.connect(self.setIdleVoice)
        self.applyButton.clicked.connect(self.applySetting)
        self.cancelButton.clicked.connect(self.closeSetting)

        self.onlyInt = QIntValidator()
        self.chaSizeLine.setValidator(self.onlyInt)

    def initUI(self):
        ### 위젯 생성 ###
        # 항상 위에 고정 체크박스
        self.AOTCheckBox = QCheckBox("항상 위에 고정")

        # 캐릭터 그룹박스
        self.chaGroupBox = QGroupBox("캐릭터")
        self.chaButton = QPushButton("캐릭터 설정")
        self.chaLabel = QLabel("")
        self.imageCheckBox = QCheckBox("이미지 크기 제한")
        self.chaSizeLine = QLineEdit("400")
        self.pxLabel = QLabel("px")

        # 보이스 그룹박스
        self.voiceGroupBox = QGroupBox("보이스")
        self.loginVoiceButton = QPushButton("접속 대사")
        self.loginVoice_label = QLabel("")
        self.idleVoiceButton = QPushButton("일반 대사")
        self.idleVoice_label = QLabel("")
        self.volumeLabel = QLabel("볼륨")
        self.voiceSlider = QSlider()

        # 보이스 랜덤 재생 라벨
        self.voiceNoticeLabel = QLabel("(여러 개 선택 시 랜덤 재생)")

        # 적용 취소 버튼
        self.applyButton = QPushButton("적용")
        self.cancelButton = QPushButton("취소")

        # 캐릭터 그룹박스 설정
        cha_HBL1_Widget = QWidget()
        cha_HBL1 = QHBoxLayout()
        cha_HBL1.addWidget(self.chaButton, alignment=Qt.AlignLeft)
        cha_HBL1.addWidget(self.chaLabel)
        cha_HBL1_Widget.setLayout(cha_HBL1)
        cha_HBL1.setContentsMargins(0, 0, 0, 0)

        cha_HBL2_Widget = QWidget()
        cha_HBL2 = QHBoxLayout()
        cha_HBL2.addWidget(self.imageCheckBox, alignment=Qt.AlignLeft)
        cha_HBL2.addWidget(self.chaSizeLine)
        cha_HBL2.addWidget(self.pxLabel)
        cha_HBL2_Widget.setLayout(cha_HBL2)
        cha_HBL2.setContentsMargins(0, 0, 0, 0)

        chaVBox = QVBoxLayout()
        chaVBox.addWidget(cha_HBL1_Widget, alignment=Qt.AlignLeft)
        chaVBox.addWidget(cha_HBL2_Widget, alignment=Qt.AlignLeft)
        self.chaGroupBox.setLayout(chaVBox)

        # 보이스 그룹박스
        voice_HBL1_widget = QWidget()
        voice_HBL1 = QHBoxLayout()
        voice_HBL1.addWidget(self.loginVoiceButton, alignment=Qt.AlignLeft)
        voice_HBL1.addWidget(self.loginVoice_label)
        voice_HBL1_widget.setLayout(voice_HBL1)
        voice_HBL1.setContentsMargins(0, 0, 0, 0)

        voice_HBL2_widget = QWidget()
        voice_HBL2 = QHBoxLayout()
        voice_HBL2.addWidget(self.idleVoiceButton, alignment=Qt.AlignLeft)
        voice_HBL2.addWidget(self.idleVoice_label)
        voice_HBL2_widget.setLayout(voice_HBL2)
        voice_HBL2.setContentsMargins(0, 0, 0, 0)

        voice_HBL3_widget = QWidget()
        voice_HBL3 = QHBoxLayout()
        voice_HBL3.addWidget(self.volumeLabel, alignment=Qt.AlignLeft)
        voice_HBL3.addWidget(self.voiceSlider)
        voice_HBL3_widget.setLayout(voice_HBL3)
        voice_HBL3.setContentsMargins(0, 0, 0, 0)

        voiceVBox = QVBoxLayout()
        voiceVBox.addWidget(voice_HBL1_widget, alignment=Qt.AlignLeft)
        voiceVBox.addWidget(voice_HBL2_widget, alignment=Qt.AlignLeft)
        voiceVBox.addWidget(voice_HBL3_widget, alignment=Qt.AlignLeft)
        self.voiceGroupBox.setLayout(voiceVBox)

        # 적용 취소 버튼
        applyWidget = QWidget()
        applyLayout = QHBoxLayout()
        applyLayout.addStretch(1)
        applyLayout.addWidget(self.applyButton)
        applyLayout.addWidget(self.cancelButton)
        applyWidget.setLayout(applyLayout)

        # 레이아웃 적용
        vBox = QVBoxLayout()
        vBox.addWidget(self.AOTCheckBox, alignment=Qt.AlignTop | Qt.AlignRight)
        vBox.addWidget(self.chaGroupBox)
        vBox.addWidget(self.voiceGroupBox)
        vBox.addWidget(self.voiceNoticeLabel)
        vBox.addWidget(applyWidget)

        self.setLayout(vBox)

        # 레이아웃 기타 설정
        self.chaSizeLine.setMinimumWidth(61)
        self.chaSizeLine.setMaximumWidth(61)
        # self.chaLabel.setMinimumWidth(130)
        # self.chaLabel.setMaximumWidth(200)
        # self.loginVoice_label.setMaximumWidth(200)
        # self.idleVoice_label.setMaximumWidth(200)

        # self.volumeLabel.setMinimumWidth(51)
        self.volumeLabel.setStyleSheet("padding: 0px 5px 0px 0px")
        self.voiceSlider.setMinimum(0)
        self.voiceSlider.setMaximum(99)
        self.voiceSlider.setSingleStep(1)
        self.voiceSlider.setPageStep(10)
        self.voiceSlider.setValue(99)
        self.voiceSlider.setMinimumWidth(181)
        # self.voiceSlider.setMaximumWidth(181)
        self.voiceSlider.setOrientation(Qt.Horizontal)

    def setParent(self, p):
        self.parent = p

    def setSetting(self, chaFile, loginVoiceList, idleVoiceList, chaSize, voiceV,
                   isSizeRestricted, aot):
        self.chaFile = chaFile
        self.loginVoiceFile = loginVoiceList
        self.idleVoiceFile = idleVoiceList
        self.chaLabel.setText(chaFile.split("/")[-1])
        self.chaSizeLine.setText(str(chaSize))
        self.voiceSlider.setValue(voiceV)
        self.isSizeRestricted = isSizeRestricted
        self.imageCheckBox.setChecked(isSizeRestricted)
        self.AOTCheckBox.setChecked(aot)

        self.loginVoice_label.setText("(%d개 설정됨)" % len(self.loginVoiceFile))
        self.idleVoice_label.setText("(%d개 설정됨)" % len(self.idleVoiceFile))

    # 컨버트 도중 다른 조작 못하게 막는 조치 해아함
    # 설정 창을 닫는 행위
    # 설정창 적용 또는 취소 버튼을 누르는 행위
    # 트레이 아이콘에서 숨기기 버튼으로 설정창을 닫게 하는 행위
    # 아니면 컨버트를 중단시키는 코드를 넣어야 할듯

    class ConvertWebmtoGif(QThread):
        chaFile = ""
        resultEvent = pyqtSignal(str)

        def run(self):
            filename = os.path.splitext(self.chaFile)[0].split("/")[-1]
            command = [
                ffmpegEXE,
                "-y",
                "-c:v",
                "libvpx-vp9",
                "-i",
                self.chaFile,
                "-lavfi",
                "split[v],palettegen,[v]paletteuse",
                "./character/" + filename + ".gif"
            ]
            if subprocess.run(command, creationflags=subprocess.CREATE_NO_WINDOW).returncode == 0:
                print("FFmpeg Script Ran Successfully")
                self.chaFile = "./character/" + filename + ".gif"
                self.resultEvent.emit(self.chaFile)
            else:
                print("There was an error running your FFmpeg script")
                self.resultEvent.emit("")
            self.quit()

    def setCharacter(self):
        fname = QFileDialog.getOpenFileName(self, "캐릭터 선택", "./character", "Character File(*.webp *.png *.gif *.webm)")
        if fname[0]:
            self.chaFile = fname[0]
            if self.chaFile.split(".")[-1] == "webm":
                self.chaLabel.setText("webm 파일 변환중...")
                self.convertTh = self.ConvertWebmtoGif()
                self.convertTh.chaFile = self.chaFile
                self.convertTh.resultEvent.connect(self.setGifCharacter)
                self.convertTh.start()
            else:
                self.chaLabel.setText(self.chaFile.split('/')[-1])

    @pyqtSlot(str)
    def setGifCharacter(self, chaFile):
        print("setgifcharacter")
        if chaFile:
            self.chaFile = chaFile
            self.chaLabel.setText(self.chaFile.split('/')[-1])
        else:
            self.chaLabel.setText("변환 실패")

    def setLoginVoice(self):
        fname = QFileDialog.getOpenFileNames(self, "접속 대사 선택", "./voice", "Audio File(*.mp3 *.wav)")
        if fname[0]:
            self.loginVoiceFile = fname[0]
            self.loginVoice_label.setText("(%d개 설정됨)" % len(self.loginVoiceFile))

    def setIdleVoice(self):
        fname = QFileDialog.getOpenFileNames(self, "일반 대사 선택", "./voice", "Audio File(*.mp3 *.wav)")
        if fname[0]:
            self.idleVoiceFile = fname[0]
            self.idleVoice_label.setText("(%d개 설정됨)" % len(self.idleVoiceFile))

    def applySetting(self):
        self.accept()

    def closeSetting(self):
        self.reject()

    def closeEvent(self, *args, **kwargs):
        self.reject()

    def showModal(self):
        return super().exec_()