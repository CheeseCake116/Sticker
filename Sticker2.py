import os, sys, random, time, subprocess
from PyQt5.QtWidgets import *
from PyQt5.QtCore import QThread, pyqtSignal, QSize, Qt, pyqtSlot, QObject, QEvent
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
# SettingWindowUi = uic.loadUiType("./setting.ui")[0]
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


class Sticker(QWidget):
    key = -1  # 그룹 번호
    managerObj = None  # ManageWindow 객체
    stickerManager = None  # StickerManager 객체
    AlwaysOnTop = False  # 항상 위

    # chaFile = ""
    # isSizeRestricted = False
    # chaSize = 400
    #
    # loginVoiceFile = []
    # idleVoiceFile = []
    # voiceVolume = 50
    voiceSound = None

    stickers = {}
    '''
    {
        'options': {
            "AlwaysOnTop": False
        },
        'characters': {
            '0' : {
                "Position": [-19, 80],  # 위치
                "Depth": 0,             # 놓인 순서
                "CharacterImage": ".../Sticker/character/BR_Andvari_0_O_S.webp",
                "LoginVoiceFiles": [
                    ".../Sticker/voice/BR_Andvari_Login.mp3"
                ],
                "IdleVoiceFiles": [
                    ".../Sticker/voice/BR_Andvari_SPIdle_02_01.mp3"
                ],
                "CharacterSize": 800,
                "SizeRestrict": false,
                "VoiceVolume": 50
            }
        }
        ...
    }
    '''
    labels = {} # {'0' : {QLabel 객체}, ... }

    # 마우스 관련
    m_flag = False      # 캐릭터를 클릭했는지
    m_Position = None   # 마우스 위치
    m_distance = 0   # 마우스 이동거리

    SettingWindow = None
    clickTime = 0  # 마우스 클릭한 시간에 따라 보이스를 출력하거나 캐릭터를 이동시키거나.

    saveEvent = pyqtSignal(dict)
    assignEvent = pyqtSignal(str, object)
    manageEvent = pyqtSignal()  # 부관 설정창 열기
    groupEvent = pyqtSignal()  # 그룹 설정창 열기
    presetEvent = pyqtSignal()  # 프리셋 설정창 열기
    removeEvent = pyqtSignal(str)  # 부관 업무에서 해제
    quitEvent = pyqtSignal()  # 프로그램 종료

    def __init__(self, manager, data, key):
        super().__init__()
        self.managerObj = manager # StickerManager 객체
        self.stickers = data
        self.readDataFile(data)
        self.key = key

        self.setWindowTitle("라오 부관")
        self.setWindowIcon(QIcon(iconPath))
        # self.move(0, 0) # 창 최대크기라서 할 필요 없을듯

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

        self.setupWindow()
        
        print("스티커 오픈")

    def readDataFile(self, jsonData):
        if jsonData:
            try:
                # 데이터 검증
                if "AlwaysOnTop" in jsonData['options']:
                    self.AlwaysOnTop = jsonData['options']['AlwaysOnTop']
                for key, data in jsonData['characters'].items():
                    if "Position" in data:
                        if len(data["Position"]) == 2:  # 좌표계이므로 값이 2개인지
                            self.stickers['characters'][key]["Position"] = data["Position"]
                        else:
                            self.stickers['characters'][key]["Position"] = [0, 0]
                    if "Depth" in data:
                        self.stickers['characters'][key]["Depth"] = data["Depth"]
                    if 'CharacterImage' in data:
                        if os.path.exists(data['CharacterImage']):
                            self.stickers['characters'][key]["CharacterImage"] = data['CharacterImage']
                        else:
                            self.stickers['characters'][key]["CharacterImage"] = ""
                    if 'LoginVoiceFiles' in data:
                        self.stickers['characters'][key]['LoginVoiceFiles'] = data['LoginVoiceFiles']
                    if 'IdleVoiceFiles' in data:
                        self.stickers['characters'][key]['IdleVoiceFiles'] = data['IdleVoiceFiles']
                    if 'SpecialVoiceFiles' in data:
                        self.stickers['characters'][key]['SpecialVoiceFiles'] = data['SpecialVoiceFiles']
                    if 'SizeRestrict' in data:
                        self.stickers['characters'][key]['SizeRestrict'] = data['SizeRestrict']
                    if 'CharacterSize' in data:
                        self.stickers['characters'][key]['CharacterSize'] = data['CharacterSize']
                    if 'VoiceVolume' in data:
                        self.stickers['characters'][key]['VoiceVolume'] = data['VoiceVolume']
                    self.setCharacter(data=data, key=key)
            except Exception as e:
                print("read Exception: " + str(e))
                self.stickers = {}

    def writeDataFile(self):
        data = self.stickers.copy()
        for key in data:
            if "chaLabel" in data[key]:
                del data[key]['chaLabel']
        self.saveEvent.emit({self.key: data})

    # Sticker 이미지 생성
    # Sticker 클릭 이벤트 설정
    def setCharacter(self, data, key):
        try:
            chaLabel = QLabel('', self)
            chaFile = data['CharacterImage']
            isSizeRestricted = data['SizeRestrict']
            chaSize = data['CharacterSize']

            # 파일이 존재하지 않는 경우
            if os.path.exists(chaFile) is False:
                return

            # webm 파일은 gif 변환 과정이 필요하므로 다시 등록하게 하여 변환 과정을 거침
            if chaFile.split(".")[-1] in ["webm"]:
                self.openSetting()
                return

            img = Image.open(chaFile)
            width, height = img.size

            # 이미지 크기가 제한된 경우 CharacterSize > 0 체크
            if isSizeRestricted and chaSize > 0:
                maxsize = chaSize

                if width >= height:
                    height = int(height / width * maxsize)
                    width = maxsize
                else:
                    width = int(width / height * maxsize)
                    height = maxsize
            chaLabel.resize(width, height)
            x, y = data['Position']
            chaLabel.move(x, y)

            # 윈도우는 전체화면으로
            # self.setFixedSize(width, height)

            if chaFile.split(".")[-1] in ["gif"]:
                movie = QMovie(chaFile)
                movie.setScaledSize(QSize(width, height))
                chaLabel.setMovie(movie)
                movie.start()

            elif chaFile.split(".")[-1] in ["webm"]:
                self.convertWebmtoGif()
                movie = QMovie(chaFile)
                movie.setScaledSize(QSize(width, height))
                chaLabel.setMovie(movie)
                movie.start()

            else:
                pilImage = Image.open(chaFile)
                pilImage_resize = pilImage.resize((width, height), Image.Resampling.LANCZOS)
                chaLabel.setPixmap(ImageQt.toqpixmap(pilImage_resize))

            # 클릭 이벤트 설정
            self.clickable(chaLabel, key, QEvent.MouseButtonPress, Qt.LeftButton).connect(self.stickerMousePressEvent)
            self.clickable(chaLabel, key, QEvent.MouseMove, Qt.LeftButton).connect(self.stickerMouseMoveEvent)
            self.clickable(chaLabel, key, QEvent.MouseButtonRelease, Qt.LeftButton).connect(self.stickerMouseReleaseEvent)

            self.labels[key] = chaLabel
            print(dir(QEvent))

        except Exception as e:
            print("Character Exception: " + str(e))

    # 클릭 이벤트필터 정의
    def clickable(self, widget, key, eventType, buttonType):
        class Filter(QObject):
            clicked = pyqtSignal(object, str)
            chaKey = key

            def eventFilter(self, obj, event):
                if obj == widget:
                    # print(obj, event)
                    if event.type() == eventType:
                        self.clicked.emit(event, self.chaKey)
                        return True
                return False

        filter = Filter(widget)
        widget.installEventFilter(filter)
        return filter.clicked

    def stickerMousePressEvent(self, event, key):
        self.clickTime = time.time()
        self.m_flag = True
        # self.m_Position = event.globalPos() - self.pos()  # Get the position of the mouse relative to the window
        self.m_Position = event.globalPos()  # Get the position of the mouse relative to the window
        event.accept()  # 클릭이벤트를 처리하고 종료. ignore 시 부모위젯으로 이벤트가 넘어감
        self.setCursor(QCursor(Qt.OpenHandCursor))  # Change mouse icon

    def stickerMouseMoveEvent(self, event, key):
        if Qt.LeftButton and self.m_flag:
            value = event.globalPos() - self.m_Position  # Change window position
            print((value.x() ** 2 + value.y() ** 2) ** 0.5)

            self.m_distance += (value.x() ** 2 + value.y() ** 2) ** 0.5
            self.m_Position = event.globalPos()
            if self.m_distance > 200:
                self.specialVoicePlay(key)
                self.m_flag = False
                self.m_distance = 0
                # self.setCursor(QCursor(Qt.ArrowCursor))
            # if time.time() - self.clickTime > 0.8:
            #     self.specialVoicePlay(key)
            event.accept()

    def stickerMouseReleaseEvent(self, event, key):
        if self.m_flag:
            if time.time() - self.clickTime < 0.4:
                self.idleVoicePlay(key)

        # self.writeDataFile()
        self.m_flag = False
        self.setCursor(QCursor(Qt.ArrowCursor))
        event.accept()

    def loginVoicePlay(self):
        # 보이스가 존재하는 캐릭터만 솎아내기
        loginVoiceFiles = {}
        for key, data in self.stickers['characters'].items():
            if data["LoginVoiceFiles"]:
                loginVoiceFiles[key] = data["LoginVoiceFiles"]

        # 보이스가 단 한개도 없는 경우
        if not loginVoiceFiles:
            return

        # 랜덤 캐릭터 선택
        print(list(loginVoiceFiles.keys()))
        randomKey = random.choice(list(loginVoiceFiles.keys()))
        print(randomKey)

        # 랜덤 보이스 선택
        voiceFile = random.choice(loginVoiceFiles[randomKey])   # 랜덤 보이스

        # 선택된 보이스 파일이 존재하지 않는 경우
        if os.path.exists(voiceFile) is False:
            return

        # 보이스 볼륨
        voiceVolume = self.stickers['characters'][randomKey]['VoiceVolume']

        # 재생
        self.soundPlay(voiceFile, voiceVolume)

    def idleVoicePlay(self, key):
        idleVoiceFile = self.stickers['characters'][key]['IdleVoiceFiles']

        # 해당 캐릭터의 보이스가 없는 경우
        if not idleVoiceFile:
            return

        # 랜덤 보이스 선택
        voiceFile = random.choice(idleVoiceFile)

        # 해당 보이스 파일이 경로에 없는 경우
        if os.path.exists(voiceFile) is False:
            return

        # 보이스 볼륨
        voiceVolume = self.stickers['characters'][key]['VoiceVolume']

        # 재생
        self.soundPlay(voiceFile, voiceVolume)

    def specialVoicePlay(self, key):
        specialVoiceFile = self.stickers['characters'][key]['SpecialVoiceFiles']

        # 해당 캐릭터의 보이스가 없는 경우
        if not specialVoiceFile:
            return

        # 랜덤 보이스 선택
        voiceFile = random.choice(specialVoiceFile)

        # 해당 보이스 파일이 경로에 없는 경우
        if os.path.exists(voiceFile) is False:
            return

        # 보이스 볼륨
        voiceVolume = self.stickers['characters'][key]['VoiceVolume']

        # 재생
        self.soundPlay(voiceFile, voiceVolume)

    def soundPlay(self, soundFile, soundVolume):
        try:
            if self.voiceSound is not None:
                self.voiceSound.stop()

            freq = 44100  # sampling rate, 44100(CD), 16000(Naver TTS), 24000(google TTS)
            bitsize = -16  # signed 16 bit. support 8,-8,16,-16
            channels = 2  # 1 is mono, 2 is stereo
            buffer = 2048  # number of samples (experiment to get right sound)

            # default : pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=4096)
            mixer.init(freq, bitsize, channels, buffer)
            self.voiceSound = mixer.Sound(soundFile)
            self.voiceSound.set_volume(soundVolume / 100)
            self.voiceSound.play()

        except Exception as e:
            print("IdleVoice Exception: " + str(e))

    # # MOUSE Click drag EVENT function
    # def mousePressEvent(self, event):
    #     print("클릭")
    #     if event.button() == Qt.LeftButton:
    #         for key, label in self.labels.items():
    #             label.mousePressEvent = lambda event: print(event)
    #             label.mousePressEvent("!!")
    #             print(label.size())
    #             label.move(0, 0)
    #         self.clickTime = time.time()
    #         self.m_flag = True
    #         self.m_Position = event.globalPos() - self.pos()  # Get the position of the mouse relative to the window
    #         event.accept()
    #         self.setCursor(QCursor(Qt.OpenHandCursor))  # Change mouse icon
    #
    # def mouseMoveEvent(self, QMouseEvent):
    #     if Qt.LeftButton and self.m_flag:
    #         self.move(QMouseEvent.globalPos() - self.m_Position)  # Change window position
    #         QMouseEvent.accept()
    #
    # def mouseReleaseEvent(self, QMouseEvent):
    #     if self.m_flag:
    #         if time.time() - self.clickTime < 0.4:
    #             self.characterTouch()

        self.writeDataFile()
        self.m_flag = False
        self.setCursor(QCursor(Qt.ArrowCursor))

    def stickerHide(self):
        self.hide()

    def stickerQuit(self):
        self.close()

    def characterQuit(self):
        pass

    def setupWindow(self):
        # centralWidget = QWidget(self)
        # self.setCentralWidget(centralWidget)

        if self.AlwaysOnTop:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    def contextMenuEvent(self, event):
        action = self.cmenu.exec_(self.mapToGlobal(event.pos()))
        if action == self.menu_hide:  # 숨기기
            self.stickerHide()
        elif action == self.menu_setting:  # 부관 설정
            self.openSetting()
        elif action == self.menu_group:  # 그룹 설정
            self.groupEvent.emit()
        elif action == self.menu_preset:  # 프리셋 설정
            self.presetEvent.emit()
        elif action == self.menu_manage:  # 위젯 설정
            self.manageEvent.emit()
        elif action == self.menu_retire:  # 부관 임무에서 해제
            self.removeEvent.emit(self.key)
        elif action == self.menu_quit:  # 종료
            self.quitEvent.emit()

    def openSetting(self):
        self.stickerManager.openSettingUi(self.key, self.chaKey)
    
    def closeEvent(self, *args, **kwargs):
        print("스티커 종료")


# 부관 설정창
class SettingWindow(QDialog, QWidget):
    parent = None
    chaFile = ""
    isSizeRestricted = True

    loginVoiceFile = []
    idleVoiceFile = []
    specialVoiceFile = []

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
        self.specialVoiceButton.clicked.connect(self.setSpecialVoice)
        self.applyButton.clicked.connect(self.applySetting)
        self.cancelButton.clicked.connect(self.closeSetting)

        self.onlyInt = QIntValidator()
        self.chaSizeLine.setValidator(self.onlyInt)

    def initUI(self):
        # 위젯 생성
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
        self.specialVoiceButton = QPushButton("특수 대사")
        self.specialVoice_label = QLabel("")
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

        voice_HBL4_widget = QWidget()
        voice_HBL4 = QHBoxLayout()
        voice_HBL4.addWidget(self.specialVoiceButton, alignment=Qt.AlignLeft)
        voice_HBL4.addWidget(self.specialVoice_label)
        voice_HBL4_widget.setLayout(voice_HBL4)
        voice_HBL4.setContentsMargins(0, 0, 0, 0)

        voice_HBL3_widget = QWidget()
        voice_HBL3 = QHBoxLayout()
        voice_HBL3.addWidget(self.volumeLabel, alignment=Qt.AlignLeft)
        voice_HBL3.addWidget(self.voiceSlider)
        voice_HBL3_widget.setLayout(voice_HBL3)
        voice_HBL3.setContentsMargins(0, 0, 0, 0)

        voiceVBox = QVBoxLayout()
        voiceVBox.addWidget(voice_HBL1_widget, alignment=Qt.AlignLeft)
        voiceVBox.addWidget(voice_HBL2_widget, alignment=Qt.AlignLeft)
        voiceVBox.addWidget(voice_HBL4_widget, alignment=Qt.AlignLeft)
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

    def setSetting(self, chaFile, loginVoiceList, idleVoiceList, specialVoiceList, chaSize, voiceV,
                   isSizeRestricted):
        self.chaFile = chaFile
        self.loginVoiceFile = loginVoiceList
        self.idleVoiceFile = idleVoiceList
        self.specialVoiceFile = specialVoiceList
        self.chaLabel.setText(chaFile.split("/")[-1])
        self.chaSizeLine.setText(str(chaSize))
        self.voiceSlider.setValue(voiceV)
        self.isSizeRestricted = isSizeRestricted
        self.imageCheckBox.setChecked(isSizeRestricted)
        # self.AOTCheckBox.setChecked(aot)

        self.loginVoice_label.setText("(%d개 설정됨)" % len(self.loginVoiceFile))
        self.idleVoice_label.setText("(%d개 설정됨)" % len(self.idleVoiceFile))
        self.specialVoice_label.setText("(%d개 설정됨)" % len(self.specialVoiceFile))

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

    def setSpecialVoice(self):
        fname = QFileDialog.getOpenFileNames(self, "특수터치 대사 선택", "./voice", "Audio File(*.mp3 *.wav)")
        if fname[0]:
            self.specialVoiceFile = fname[0]
            self.specialVoice_label.setText("(%d개 설정됨)" % len(self.specialVoiceFile))

    def applySetting(self):
        self.accept()

    def closeSetting(self):
        self.reject()

    def closeEvent(self, *args, **kwargs):
        self.reject()

    def showModal(self):
        return super().exec_()