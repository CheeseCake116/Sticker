import os, sys, random, subprocess
from PyQt5.QtWidgets import *
from PyQt5.QtCore import QThread, pyqtSignal, QSize, Qt, pyqtSlot, QObject, QEvent
from PyQt5.QtGui import QIcon, QCursor, QMovie, QTransform, QDoubleValidator, QPixmap
from PIL import Image, ImageQt
from pygame import mixer
from datetime import datetime

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


class Sticker(QWidget):
    """
    stickers = {
        'options': {
            "AlwaysOnTop": False,
            "GroupName": "기본 프리셋"
        },
        'characters': {
            '0' : {
                "Position": [-19, 80],  # 위치
                "Depth": 0,             # 놓인 순서
                "Visible": True,
                "CharacterImage": ".../Sticker/character/BR_Andvari_0_O_S.webp",
                "LoginVoiceFiles": [
                    ".../Sticker/voice/BR_Andvari_Login.mp3"
                ],
                "IdleVoiceFiles": [
                    ".../Sticker/voice/BR_Andvari_SPIdle_02_01.mp3"
                ],
                "Flip": False
                "Size": 100,
                "Rotation": 0,
                "VoiceVolume": 50
            }
        }
        ...
    }
    """

    saveEvent = pyqtSignal(dict)
    manageEvent = pyqtSignal()  # 부관 설정창 열기
    groupEvent = pyqtSignal(str)  # 그룹 설정창 열기
    presetEvent = pyqtSignal()  # 프리셋 설정창 열기
    quitEvent = pyqtSignal()  # 프로그램 종료

    def __init__(self, manager, data, key):
        super().__init__()
        self.stickerManager = manager  # StickerManager 객체
        self.stickers = {}    # 캐릭터 정보
        self.labels = {}    # 각 캐릭터 QLabel 객체 딕셔너리. {'0' : {QLabel 객체}, ... }
        self.key = key  # 그룹 번호
        self.voiceSound = {}      # 보이스 재생하는 sound 객체
        self.readDataFile(data)

        self.setWindowTitle("라오 부관")
        self.setWindowIcon(QIcon(iconPath))

        self.AlwaysOnTop = False    # 항상 위

        # 마우스 관련
        self.m_flag = False     # 캐릭터를 클릭했는지
        self.m_Position = None  # 마우스 위치
        self.m_distance = 0     # 마우스 이동거리
        self.m_info = None      # 해당 객체에 마우스 호버중인지. (키, bool)

        # 캐릭터 설정창
        self.SettingWindow = None
        self.editWindow = None

        # 이벤트 관련
        self.saveEvent.connect(self.stickerManager.stickerSave)
        self.manageEvent.connect(self.stickerManager.openManageUi)
        self.groupEvent.connect(self.stickerManager.openGroupUi)
        self.presetEvent.connect(self.stickerManager.openPresetUi)
        self.quitEvent.connect(self.stickerManager.programQuit)

        # 컨텍스트 메뉴
        self.cmenu = QMenu(self)
        self.menu_setting = self.cmenu.addAction("부관 설정")
        self.menu_move = self.cmenu.addAction("이동")
        self.menu_move.setCheckable(True)
        self.menu_move.setChecked(False)
        self.menu_edit = self.cmenu.addAction("편집")
        self.menu_hide = self.cmenu.addAction("잠시 숨기기")
        self.menu_retire = self.cmenu.addAction("내보내기")
        self.cmenu.addSeparator()
        self.menu_group = self.cmenu.addAction("그룹 설정")
        self.menu_preset = self.cmenu.addAction("프리셋 관리")
        self.menu_manage = self.cmenu.addAction("위젯 설정")
        self.menu_quit = self.cmenu.addAction("종료")

        # 윈도우 설정
        self.setupWindow()

    def closeEvent(self, QCloseEvent):
        print("스티커 꺼짐")

    def readDataFile(self, jsonData):
        # 저장용 기본 데이터 생성
        defaultData = {
            'options': {
                'AlwaysOnTop': False,
                'GroupName': '기본 프리셋'
            },
            'characters': {
            }
        }

        defaultChaData = {
            'CharacterName': "기본 부관",
            'Position': [0, 0],
            'Depth': 0,
            'Visible': True,
            'CharacterImage': "",
            'LoginVoiceFiles': [],
            'IdleVoiceFiles': [],
            'SpecialVoiceFiles': [],
            'Flip': False,
            'Size': 100,
            'Rotation': 0,
            'VoiceVolume': 50
        }

        if jsonData:
            try:
                # 데이터 검증
                if "AlwaysOnTop" in jsonData['options']:
                    self.AlwaysOnTop = jsonData['options']['AlwaysOnTop']
                    defaultData['options']['AlwaysOnTop'] = self.AlwaysOnTop
                if 'options' in jsonData:
                    self.AlwaysOnTop = jsonData.get('AlwaysOnTop', False)
                    defaultData['options']['AlwaysOnTop'] = self.AlwaysOnTop
                    defaultData['options']['GroupName'] = jsonData.get('GroupName', '기본 프리셋')

                for key, data in jsonData['characters'].items():
                    chaData = defaultChaData.copy()

                    chaData["CharacterName"] = data.get("CharacterName", "기본 부관")
                    chaData["Position"] = data.get("Position", [0, 0])
                    chaData["Depth"] = data.get("Depth", 0)
                    chaData["Visible"] = data.get("Visible", True)
                    chaData["CharacterImage"] = data.get("CharacterImage", "")
                    chaData["LoginVoiceFiles"] = data.get("LoginVoiceFiles", [])
                    chaData["IdleVoiceFiles"] = data.get("IdleVoiceFiles", [])
                    chaData["SpecialVoiceFiles"] = data.get("SpecialVoiceFiles", [])
                    chaData["Flip"] = data.get("Flip", False)
                    chaData["Size"] = data.get("Size", 100)
                    chaData["Rotation"] = data.get("Rotation", 0)
                    chaData["VoiceVolume"] = data.get("VoiceVolume", 50)

                    self.setCharacter(data=chaData, key=key)

                    # dafaultData에 각 캐릭터 정보를 추가
                    defaultData['characters'][key] = chaData

                # 완성된 defaultData를 stickers에 할당
                self.stickers = defaultData
                print(self.stickers)

            except Exception as e:
                print("read Exception: " + str(e))
                self.stickers = {}

    def writeDataFile(self):
        self.saveEvent.emit({self.key: self.stickers})

    # 다른 그룹 데이터를 불러옴
    def resetSticker(self, data, key):
        print("ResetSticker")
        self.stickers = data
        self.key = key
        self.stickers = {}
        self.labels = {}
        self.readDataFile(data)

    # Sticker 이미지 생성
    # Sticker 클릭 이벤트 설정
    def setCharacter(self, data, key):
        try:
            # QLabel 생성
            if key in self.labels and self.labels[key]:
                chaLabel = self.labels[key]
            else:
                chaLabel = QLabel('', self)

            # 캐릭터 데이터
            chaFile = data['CharacterImage']
            chaFlip = data['Flip']
            chaSize = data['Size']
            chaRotation = data['Rotation']
            visible = data['Visible']
            self.voiceSound[key] = None

            # 파일이 존재하지 않는 경우
            if os.path.exists(chaFile) is False:
                return

            # webm 파일은 gif 변환 과정이 필요하므로 건너뜀
            if chaFile.split(".")[-1] == "webm":
                return

            img = Image.open(chaFile)
            width, height = img.size
            width *= chaSize / 100
            height *= chaSize / 100
            chaLabel.resize(width, height)

            # QLabel 이동
            x, y = data['Position']
            chaLabel.move(x, y)

            # 이미지 파일 적용
            # gif일 경우
            if chaFile.split(".")[-1] == "gif":
                movie = QMovie(chaFile)
                movie.setScaledSize(QSize(width, height))
                chaLabel.setMovie(movie)
                movie.start()

            # 일반 이미지일 경우
            else:
                flipValue = 1
                if chaFlip:
                    flipValue = -1

                pixImage = ImageQt.toqpixmap(Image.open(chaFile))
                transform = QTransform().scale(flipValue * chaSize / 100, chaSize / 100).rotate(flipValue * chaRotation / 100)
                pixImage = pixImage.transformed(transform, mode=Qt.SmoothTransformation)
                size = pixImage.size()
                chaLabel.resize(size.width(), size.height())
                chaLabel.setPixmap(pixImage)

            # 이미지 숨김 상태인지
            if visible:
                chaLabel.show()
            else:
                chaLabel.hide()

            # 클릭 이벤트 설정
            self.clickable(chaLabel, key, QEvent.MouseButtonPress, Qt.LeftButton).connect(self.stickerMousePressEvent)
            self.clickable(chaLabel, key, QEvent.MouseMove, Qt.NoButton).connect(self.stickerMouseMoveEvent)
            self.clickable(chaLabel, key, QEvent.MouseButtonRelease, Qt.LeftButton).connect(self.stickerMouseReleaseEvent)
            self.clickable(chaLabel, key, QEvent.MouseButtonRelease, Qt.RightButton).connect(self.stickerContextMenuEvent)

            self.labels[key] = chaLabel

        except Exception as e:
            print("Character Exception: " + str(e))

    # 클릭 이벤트필터 정의
    def clickable(self, widget, key, eventType, buttonType):
        class Filter(QObject):
            clicked = pyqtSignal(object, str)
            chaKey = key

            def eventFilter(self, obj, event):
                if obj == widget:
                    if event.type() == eventType:
                        if buttonType is None or event.button() == buttonType:
                            self.clicked.emit(event, self.chaKey)
                            return True
                return False

        filter = Filter(widget)
        widget.installEventFilter(filter)
        return filter.clicked

    def stickerMousePressEvent(self, event, key):
        self.m_flag = True
        self.m_Position = event.globalPos() - self.labels[key].pos()
        event.accept()  # 클릭이벤트를 처리하고 종료. ignore 시 부모위젯으로 이벤트가 넘어감
        self.setCursor(QCursor(Qt.OpenHandCursor))  # Change mouse icon
        self.m_info = (key, True)

    def stickerMouseMoveEvent(self, event, key):
        if self.m_flag:
            if self.menu_move.isChecked():  # 캐릭터 이동
                self.labels[key].move(event.globalPos() - self.m_Position)

            # 처음 클릭한 캐릭터 밖으로 나가지 않았는지
            elif self.m_info == (key, True) and self.labels[key].rect().contains(event.pos()):  # 캐릭터 쓰다듬기
                value = event.globalPos() - self.labels[key].pos() - self.m_Position  # 마우스 이동거리

                self.m_distance += (value.x() ** 2 + value.y() ** 2) ** 0.5
                self.m_Position = event.globalPos() - self.labels[key].pos()
                if self.m_distance > 300:
                    self.specialVoicePlay(key)
                    self.m_flag = False
                    self.m_distance = 0
                    self.setCursor(QCursor(Qt.ArrowCursor))
            event.accept()

    def stickerMouseReleaseEvent(self, event, key):
        if self.m_flag:
            # 이동 종료
            if self.menu_move.isChecked():
                pos = self.labels[key].pos()
                self.stickers['characters'][key]['Position'] = [pos.x(), pos.y()]
                self.writeDataFile()
            # 쓰다듬기
            elif self.labels[key].rect().contains(event.pos()):
                self.idleVoicePlay(key)

            self.m_flag = False
            self.setCursor(QCursor(Qt.ArrowCursor))
            event.accept()
        self.m_info = None

    # 캐릭터를 쓰다듬는 것을 좀 더 정교화하기 위해 마우스가 캐릭터 위를 빠져나갔는지 체크하려고 했는데
    # 잘 안되어서 파기
    # def stickerEnterEvent(self, event, key):
    #     print(key, " Enter")
    #     if self.m_flag and self.m_info and self.m_info[0] == key:
    #         self.m_info = (key, True)
    #         event.accept()
    #
    # def stickerLeaveEvent(self, event, key):
    #     print(key, " Leave")
    #     if self.m_flag and self.m_info and self.m_info[0] == key:
    #         self.m_info = (key, False)
    #         event.accept()

    def stickerContextMenuEvent(self, event, key):
        if not self.labels[key].rect().contains(event.pos()):
            return

        action = self.cmenu.exec_(self.labels[key].pos() + event.pos())  # event.pos()만 하니까 화면 좌상단 구석에 생김
        if action == self.menu_setting:     # 부관 설정
            self.openSetting(key)
        elif action == self.menu_edit:      # 편집
            self.openEditWindow(key)
        elif action == self.menu_hide:      # 잠시 숨기기
            self.hideSticker(key)
        elif action == self.menu_retire:    # 내보내기
            self.characterQuit(key)
        elif action == self.menu_group:     # 그룹 설정
            self.groupEvent.emit(self.key)
        elif action == self.menu_preset:    # 프리셋 설정
            self.presetEvent.emit()
        elif action == self.menu_manage:    # 위젯 설정
            self.manageEvent.emit()
        elif action == self.menu_quit:      # 종료
            self.quitEvent.emit()

        event.accept()

    def loginVoicePlay(self):
        # 숨겨져 있지 않은 캐릭 / 보이스가 존재하는 캐릭터만 솎아내기
        loginVoiceFiles = {}
        for key, data in self.stickers['characters'].items():
            if data["Visible"] and data["LoginVoiceFiles"]:
                loginVoiceFiles[key] = data["LoginVoiceFiles"]

        # 보이스가 단 한개도 없는 경우
        if not loginVoiceFiles:
            return

        # 랜덤 캐릭터 선택
        randomKey = random.choice(list(loginVoiceFiles.keys()))

        # 랜덤 보이스 선택
        voiceFile = random.choice(loginVoiceFiles[randomKey])   # 랜덤 보이스

        # 선택된 보이스 파일이 존재하지 않는 경우
        if os.path.exists(voiceFile) is False:
            return

        # 보이스 볼륨
        voiceVolume = self.stickers['characters'][randomKey]['VoiceVolume']

        # 재생
        self.soundPlay(voiceFile, voiceVolume, randomKey)

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
        self.soundPlay(voiceFile, voiceVolume, key)

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
        self.soundPlay(voiceFile, voiceVolume, key)

    def soundPlay(self, soundFile, soundVolume, key):
        try:
            # 보이스가 재생 중이면 해당 보이스 정지
            if key in self.voiceSound and self.voiceSound[key] is not None:
                self.voiceSound[key].stop()

            freq = 44100  # sampling rate, 44100(CD), 16000(Naver TTS), 24000(google TTS)
            bitsize = -16  # signed 16 bit. support 8,-8,16,-16
            channels = 2  # 1 is mono, 2 is stereo
            buffer = 2048  # number of samples (experiment to get right sound)

            # default : pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=4096)
            mixer.init(freq, bitsize, channels, buffer)
            self.voiceSound[key] = mixer.Sound(soundFile)
            self.voiceSound[key].set_volume(soundVolume / 100)
            self.voiceSound[key].play()

        except Exception as e:
            print("IdleVoice Exception: " + str(e))

    def hideSticker(self, key):
        if self.key in self.stickerManager.groupUis and self.stickerManager.groupUis[self.key]:
            self.stickerManager.groupUis[self.key].hideSticker(key)
        else:
            self.labels[key].hide()
            self.stickers['characters'][key]["Visible"] = False
            self.writeDataFile()

    def openEditWindow(self, key):
        chaFile = self.stickers['characters'][key]['CharacterImage']
        if not os.path.exists(chaFile):
            QMessageBox.warning(self, '파일 없음', "해당 부관의 이미지 파일을 찾을 수 없습니다.")
            return

        self.editWindow = CharacterEditWindow(self, key, chaFile, self.stickers['characters'][key])
        self.editWindow.editPixmapEvent.connect(self.editPixmapSticker)
        self.editWindow.editMovieEvent.connect(self.editMovieSticker)
        self.editWindow.show()

    @pyqtSlot(str, object, bool, float, float)
    def editPixmapSticker(self, key, pixmap, flip, size, rotation):
        info = self.stickers['characters'][key]
        info["Flip"] = flip
        info["Size"] = size
        info["Rotation"] = rotation
        self.writeDataFile()

        # 실제값보다 100배 큰 정수이므로 100으로 나눠서 사용
        size /= 100
        rotation /= 100

        flipValue = 1
        if flip:
            flipValue = -1

        chaLabel = self.labels[key]
        if pixmap:
            transform = QTransform().scale(flipValue * size, size).rotate(flipValue * rotation)
            newPixmap = pixmap.transformed(transform, mode=Qt.SmoothTransformation)
            chaLabel.setPixmap(newPixmap)
            chaLabel.resize(newPixmap.width(), newPixmap.height())

    @pyqtSlot(str, object, tuple, bool, float, float)
    def editMovieSticker(self, key, movie, orgSize, flip, size, rotation):
        info = self.stickers['characters'][key]
        info["Flip"] = flip
        info["Size"] = size
        info["Rotation"] = rotation
        self.writeDataFile()

        # 실제값보다 100배 큰 정수이므로 100으로 나눠서 사용
        size /= 100
        rotation /= 100

        flipValue = 1
        if flip:
            flipValue = -1

        chaLabel = self.labels[key]
        if movie:
            width, height = orgSize
            width *= size
            height *= size

            movie.setScaledSize(QSize(width, height))
            chaLabel.setMovie(movie)
            movie.start()
            chaLabel.resize(width, height)

    def groupQuit(self):
        for key, label in self.labels.items():
            movie = label.movie()
            if movie:
                movie.deleteLater()
            # label.close()

        self.labels = {}
        self.stickers = {}
        self.close()

    # 캐릭터 업무해제 요청
    def characterQuit(self, key):
        # 그룹 UI가 켜져있다면 그 UI의 해당 캐릭터를 삭제해야 함
        groupUis = self.stickerManager.groupUis
        if self.key in groupUis and groupUis[self.key]:
            # 행 번호 찾기
            currentRow = None
            groupUi = groupUis[self.key]
            for idx, item in enumerate(groupUi.groupItems):
                if item.chaKey == key:
                    currentRow = idx
                    break

            # 해당 행 제거
            if currentRow:
                groupUi.table.removeRow(currentRow)
                groupUi.rowCount -= 1
                del groupUi.groupItems[currentRow]  # 표에서 제거
        
        # 세이브데이터 수정
        if key in self.stickerManager.jsonData['Stickers'][self.key]['characters']:
            del self.stickerManager.jsonData['Stickers'][self.key]['characters'][key]
        
        # 사운드 객체 제거
        if key in self.voiceSound:
            del self.voiceSound[key]
        
        # 캐릭터 삭제
        self.labels[key].close()
        
        # 저장
        self.stickerManager.thereIsSomethingToSave()

    def setupWindow(self):
        # centralWidget = QWidget(self)
        # self.setCentralWidget(centralWidget)

        if self.AlwaysOnTop:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.showMaximized()

    def openSetting(self, chaKey):
        self.stickerManager.openSettingUi(self.key, chaKey)
    
    def __del__(self):
        print("스티커 객체 삭제")

class CharacterEditWindow(QWidget):
    parent = None
    chaKey = '-1'
    flipValue = False
    sizeValue = 1
    rotateValue = 0
    chaFile = ""
    minsize = 0
    maxsize = 400
    minrotate = -18000
    maxrotate = 18000
    originSize = None

    # 원본 저장
    pixmap = None
    movie = None

    editPixmapEvent = pyqtSignal(str, object, bool, float, float)
    editMovieEvent = pyqtSignal(str, object, tuple, bool, float, float)

    def __init__(self, parent, key, chaFile, info):
        super().__init__()
        self.parent = parent
        self.chaKey = key
        self.chaFile = chaFile

        # 파일 검사
        if chaFile:
            ext = chaFile.split(".")[-1]
            if ext == "gif":
                self.movie = QMovie(chaFile)
            elif ext != "webm":
                self.pixmap = ImageQt.toqpixmap(Image.open(chaFile))
            else:
                QMessageBox.warning(self, "알 수 없는 파일", "이미지파일을 읽을 수 없습니다.")
                self.close()

        self.flipValue = info['Flip']
        self.sizeValue = info['Size']
        self.rotateValue = info['Rotation']
        self.originSize = Image.open(chaFile).size
        self.initUI()

    def initUI(self):
        # 위젯 생성
        self.flipLabel = QLabel("좌우반전")
        self.flipCheck = QCheckBox()
        self.sizeLabel = QLabel("크기")
        self.sizeSlider = QSlider()
        self.sizeLineEdit = QLineEdit()
        self.sizeValueLabel = QLabel("x")
        self.rotateLabel = QLabel("회전")
        self.rotateSlider = QSlider()
        self.rotateLineEdit = QLineEdit()
        self.rotateValueLabel = QLabel("°")

        # 핸들러 할당
        self.flipCheck.stateChanged.connect(self.flipChange)
        self.sizeSlider.valueChanged.connect(self.sizeChange)
        self.sizeLineEdit.setValidator(QDoubleValidator(self))
        self.sizeLineEdit.editingFinished.connect(self.sizeEditEvent)
        self.rotateSlider.valueChanged.connect(self.rotateChange)
        self.rotateLineEdit.setValidator(QDoubleValidator(self))
        self.rotateLineEdit.editingFinished.connect(self.rotateEditEvent)

        # 위젯 설정
        self.flipCheck.setChecked(self.flipValue)
        self.sizeSlider.setRange(self.minsize, self.maxsize)  # QSlider는 float값을 못 쓰는 듯
        self.sizeSlider.setOrientation(Qt.Horizontal)
        self.sizeSlider.setValue(self.sizeValue)
        self.rotateSlider.setRange(self.minrotate, self.maxrotate)
        self.rotateSlider.setOrientation(Qt.Horizontal)
        self.rotateSlider.setValue(self.rotateValue)

        # 레이아웃 설정
        edit_HBL1_Widget = QWidget()
        edit_HBL1 = QHBoxLayout()
        edit_HBL1.addWidget(self.flipLabel, alignment=Qt.AlignLeft)
        edit_HBL1.addWidget(self.flipCheck, alignment=Qt.AlignLeft)
        edit_HBL1.setContentsMargins(10, 10, 10, 10)
        edit_HBL1_Widget.setLayout(edit_HBL1)

        edit_HBL2_Widget = QWidget()
        edit_HBL2 = QHBoxLayout()
        edit_HBL2.addWidget(self.sizeLabel, alignment=Qt.AlignLeft)
        edit_HBL2.addWidget(self.sizeSlider, alignment=Qt.AlignLeft)
        edit_HBL2.addWidget(self.sizeLineEdit, alignment=Qt.AlignLeft)
        edit_HBL2.addWidget(self.sizeValueLabel, alignment=Qt.AlignLeft)
        edit_HBL2.setContentsMargins(10, 10, 10, 10)
        edit_HBL2_Widget.setLayout(edit_HBL2)

        edit_HBL3_Widget = QWidget()
        edit_HBL3 = QHBoxLayout()
        edit_HBL3.addWidget(self.rotateLabel, alignment=Qt.AlignLeft)
        edit_HBL3.addWidget(self.rotateSlider, alignment=Qt.AlignLeft)
        edit_HBL3.addWidget(self.rotateLineEdit, alignment=Qt.AlignLeft)
        edit_HBL3.addWidget(self.rotateValueLabel, alignment=Qt.AlignLeft)
        edit_HBL3.setContentsMargins(10, 10, 10, 10)
        edit_HBL3_Widget.setLayout(edit_HBL3)

        editVBox = QVBoxLayout()
        editVBox.addWidget(edit_HBL1_Widget, alignment=Qt.AlignLeft)
        editVBox.addWidget(edit_HBL2_Widget, alignment=Qt.AlignLeft)
        editVBox.addWidget(edit_HBL3_Widget, alignment=Qt.AlignLeft)
        self.setLayout(editVBox)

    def flipChange(self):
        self.flipValue = self.flipCheck.isChecked()
        self.editEventEmit()

    def sizeChange(self):
        self.sizeValue = self.sizeSlider.value()
        self.sizeLineEdit.setText("%.2f" % (self.sizeValue / 100))
        self.editEventEmit()

    def rotateChange(self):
        self.rotateValue = self.rotateSlider.value()
        self.rotateLineEdit.setText("%.2f" % (self.rotateValue / 100))
        self.editEventEmit()

    def sizeEditEvent(self):
        val = float(self.sizeLineEdit.text())
        if val < self.minsize / 100:
            val = 100
        elif val > self.maxsize / 100:
            val = self.maxsize / 100

        self.sizeLineEdit.setText("%.2f" % val)
        self.sizeValue = int(val * 100)
        self.sizeSlider.setValue(self.sizeValue)
        self.editEventEmit()
        self.sizeLineEdit.setSelection(0, 10)

    def rotateEditEvent(self):
        val = float(self.rotateLineEdit.text())
        if val < self.minrotate / 100 or val > self.maxrotate / 100:
            val = val % 360

        self.rotateLineEdit.setText("%.2f" % val)
        self.rotateValue = int(val * 100)
        self.rotateSlider.setValue(self.rotateValue)
        self.editEventEmit()
        self.rotateLineEdit.setSelection(0, 10)

    def editEventEmit(self):
        if self.pixmap:
            self.editPixmapEvent.emit(self.chaKey, self.pixmap, self.flipValue, self.sizeValue, self.rotateValue)
        elif self.movie:
            self.editMovieEvent.emit(self.chaKey, self.movie, self.originSize, self.flipValue, self.sizeValue, self.rotateValue)

    def closeEvent(self, QCloseEvent):
        newSize = (self.originSize[0] * self.sizeValue / 100, self.originSize[1] * self.sizeValue / 100)
        chaLabel = self.parent.labels[self.chaKey]


# 부관 설정창
class SettingWindow(QDialog, QWidget):
    parent = None
    chaFile = ""

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

    def initUI(self):
        # 위젯 생성

        # 캐릭터 그룹박스
        self.chaGroupBox = QGroupBox("캐릭터")
        self.chaButton = QPushButton("캐릭터 설정")
        self.chaLabel = QLabel("")                          # 설정된 캐릭터 이미지 파일명 표시하는 라벨
        self.chaProgress = QProgressBar(self)
        self.chaProgress.setRange(0, 10000)
        self.chaProgress.setValue(0)
        self.chaProgress.setTextVisible(False)
        self.chaCancelButton = QPushButton("변환취소")
        self.chaCancelButton.released.connect(self.convertStop)

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

        self.cha_HBL3_Widget = QWidget()
        cha_HBL3 = QHBoxLayout()
        cha_HBL3.addWidget(self.chaProgress, alignment=Qt.AlignLeft)
        cha_HBL3.addWidget(self.chaCancelButton)
        self.cha_HBL3_Widget.setLayout(cha_HBL3)
        cha_HBL3.setContentsMargins(0, 0, 0, 0)
        self.cha_HBL3_Widget.hide()

        chaVBox = QVBoxLayout()
        chaVBox.addWidget(cha_HBL1_Widget, alignment=Qt.AlignLeft)
        chaVBox.addWidget(self.cha_HBL3_Widget, alignment=Qt.AlignLeft)
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
        vBox.addWidget(self.chaGroupBox)
        vBox.addWidget(self.voiceGroupBox)
        vBox.addWidget(self.voiceNoticeLabel)
        vBox.addWidget(applyWidget)

        self.setLayout(vBox)

        # 레이아웃 기타 설정
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

    def setSetting(self, chaFile, loginVoiceList, idleVoiceList, specialVoiceList, voiceV):
        self.chaFile = chaFile
        self.loginVoiceFile = loginVoiceList
        self.idleVoiceFile = idleVoiceList
        self.specialVoiceFile = specialVoiceList
        self.chaLabel.setText(chaFile.split("/")[-1])
        self.voiceSlider.setValue(voiceV)

        self.loginVoice_label.setText("(%d개 설정됨)" % len(self.loginVoiceFile))
        self.idleVoice_label.setText("(%d개 설정됨)" % len(self.idleVoiceFile))
        self.specialVoice_label.setText("(%d개 설정됨)" % len(self.specialVoiceFile))

    class ConvertWebmtoGif(QThread):
        chaFile = ""
        resultEvent = pyqtSignal(str)
        updateEvent = pyqtSignal(str, int)  # 라벨 표시값, 진행바에 사용될 정수값
        cancelEvent = pyqtSignal()  # 변환 취소된 후 종료될 때 작동
        killEvent = pyqtSignal()
        stop = False
        process = None

        def __init__(self, chaFile):
            super().__init__()
            self.chaFile = chaFile

        def run(self):
            filename = os.path.splitext(self.chaFile)[0].split("/")[-1]
            # newChaFile = "./character/" + filename + ".gif"
            newChaFile = "./character/" + filename + "-%d.png"
            # count = 1
            # while os.path.exists(newChaFile):
            #     count += 1
            #     newChaFile = "./character/" + filename + " (%d)" % count + ".gif"

            command = [
                ffmpegEXE,
                "-y",
                "-c:v", "libvpx-vp9",
                "-i", self.chaFile,
                "-lavfi", "split[v],palettegen,[v]paletteuse",
                newChaFile
            ]

            # 기존 gif 변환 코드
            # command = [
            #     ffmpegEXE,
            #     "-y",
            #     "-c:v", "libvpx-vp9",
            #     "-i", self.chaFile,
            #     "-lavfi", "split[v],palettegen,[v]paletteuse",
            #     newChaFile
            # ]

            # test 1
            # try:
            #     if subprocess.run(command2).returncode == 0:
            #         print("FFmpeg Script Ran Successfully")
            #         self.chaFile = "./character/" + filename + ".gif"
            #         self.resultEvent.emit(self.chaFile)
            #
            #     else:
            #         print("There was an error running your FFmpeg script")
            #         self.resultEvent.emit("")
            #
            #     self.quit()
            # except Exception as e:
            #     print(e)
            #     self.quit()

            # test 2
            # if subprocess.run(command, creationflags=subprocess.CREATE_NO_WINDOW).returncode == 0:
            #     print("FFmpeg Script Ran Successfully")
            #     self.chaFile = "./character/" + filename + ".gif"
            #     self.resultEvent.emit(self.chaFile)
            #
            # else:
            #     print("There was an error running your FFmpeg script")
            #     self.resultEvent.emit("")
            #
            # self.quit()

            try:
                duration = None
                self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                           universal_newlines=True)

                for line in self.process.stdout:
                    print(line)
                    if self.stop:
                        break

                    if "DURATION" in line:
                        dataList = line.split()
                        dt = datetime.strptime(dataList[2][0:12], "%H:%M:%S.%f")  # '00:00:01.933'
                        duration = (dt.hour * 3600 + dt.minute * 60 + dt.second) * 1000000 + dt.microsecond
                        self.updateEvent.emit("0%", 0)
                    if "time=" in line:
                        dataList = line.split()
                        dt = datetime.strptime(dataList[6][5:], "%H:%M:%S.%f")  # '00:00:01.91'
                        currentTime = (dt.hour * 3600 + dt.minute * 60 + dt.second) * 1000000 + dt.microsecond
                        rate = currentTime / duration
                        self.updateEvent.emit("%.2f" % (rate * 100) + "%", int(rate * 10000))

                # 변환 취소 시 process가 kill되므로 for문도 빠져나와짐
                if self.stop:
                    # FFmpeg가 변환중인 파일을 잡고 있으므로 잠시 기다리기
                    self.sleep(1)

                    # 변환중이던 파일 삭제
                    if os.path.exists(newChaFile):
                        os.remove(newChaFile)

                    # 변환 취소됨을 알림
                    self.cancelEvent.emit()

                    # 객체 삭제
                    self.quit()

                else:
                    self.process = None
                    print("FFmpeg Script Ran Successfully")
                    self.chaFile = newChaFile
                    self.resultEvent.emit(self.chaFile)
                    self.quit()

            except Exception as e:
                print("ConvertException: ", e)
                self.quit()

    def setCharacter(self):
        if self.convertTh:
            QMessageBox.warning(self, "gif 변환 중", "gif 변환 중입니다.\n변환 작업을 취소해야 부관을 변경할 수 있습니다.")
            return

        fname = QFileDialog.getOpenFileName(self, "캐릭터 선택", "./character", "Character File(*.webp *.png *.gif *.webm)")
        if fname[0]:
            self.chaFile = fname[0]
            if self.chaFile.split(".")[-1] == "webm":
                buttonReply = QMessageBox.information(
                    self, 'gif 변환 알림', "webm 파일은 변환을 거쳐야 사용할 수 있습니다.\n지금 변환하시겠습니까?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )

                if buttonReply == QMessageBox.Yes:
                    self.chaLabel.setText("파일 변환중...")
                    self.cha_HBL3_Widget.show()
                    self.chaProgress.setValue(0)
                    self.convertTh = self.ConvertWebmtoGif(self.chaFile)
                    self.convertTh.updateEvent.connect(self.progressUpdate)
                    self.convertTh.resultEvent.connect(self.setGifCharacter)
                    self.convertTh.cancelEvent.connect(self.convertCanceled)
                    self.convertTh.start()
                else:
                    self.chaFile = None
                    self.chaLabel.setText("")
            else:
                self.chaLabel.setText(self.chaFile.split('/')[-1])

    @pyqtSlot(str, int)
    def progressUpdate(self, rate_str, rate_int):
        self.chaLabel.setText("파일 변환중... " + rate_str)
        self.chaProgress.setValue(rate_int)

    # 변환 취소 요청
    @pyqtSlot()
    def convertStop(self):
        # FFmpeg 종료
        self.convertTh.stop = True
        if self.convertTh:
            self.convertTh.process.kill()

        self.chaLabel.setText("변환 취소 중...")

    # 변환 취소된 후
    @pyqtSlot()
    def convertCanceled(self):
        self.convertTh = None
        self.cha_HBL3_Widget.hide()

        # 기존에 설정해둔 이미지가 있을 경우 텍스트 복구
        if self.chaFile:
            self.chaLabel.setText(self.chaFile.split('/')[-1])
        else:
            self.chaLabel.setText("")


    @pyqtSlot(str)
    def setGifCharacter(self, chaFile):
        self.convertTh = None
        self.cha_HBL3_Widget.hide()
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
        if self.convertTh:
            QMessageBox.warning(self, 'gif 변환 중', 'gif 변환 도중에는 창을 닫을 수 없습니다.')
        else:
            self.accept()

    def closeSetting(self):
        if self.convertTh:
            QMessageBox.warning(self, 'gif 변환 중', 'gif 변환 도중에는 창을 닫을 수 없습니다.')
        else:
            self.reject()

    def closeEvent(self, event):
        if self.convertTh:
            QMessageBox.warning(self, 'gif 변환 중', 'gif 변환 도중에는 창을 닫을 수 없습니다.')
            event.ignore()
        else:
            self.reject()

    def showModal(self):
        return super().exec_()
    
    def __del__(self):
        print("세팅윈도우 삭제")