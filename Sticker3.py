import os, sys, random, subprocess, re, zipfile
from PyQt5.QtWidgets import QMenu, QWidget, QPushButton, QVBoxLayout, QHBoxLayout, QCheckBox, QMessageBox, QLabel, \
    QLineEdit, QSlider, QDialog, QGroupBox, QFileDialog, QProgressBar
from PyQt5.QtCore import QThread, pyqtSignal, QSize, Qt, pyqtSlot, QObject, QEvent
from PyQt5.QtGui import QIcon, QCursor, QMovie, QTransform, QDoubleValidator, QPixmap, QImage
from PIL import Image, ImageQt
from pygame import mixer
from datetime import datetime
import cv2
import imageio.v3 as iio
import shutil

currentDir = os.getcwd()

try:
    meipassDir = sys._MEIPASS
except:
    meipassDir = currentDir

os.chdir(meipassDir)
iconPath = os.path.abspath("./lise.ico")
loadImg = os.path.abspath("./loading.png")

os.chdir(currentDir)
ffmpegEXE = os.path.abspath("./ffmpeg/ffmpeg.exe").replace("\\", "/")


# GIF 재생을 위해 각 프레임을 메모리에 올려서 갈아끼우는 방식
# QMovie에 올리는 것보다 CPU 활용이 훨씬 나음fcv
# 메모리를 많이 잡아먹긴 하지만 이미지를 작게 줄이면 좀 적게 먹음

class LoadingImage(QThread):
    stop = False

    def __init__(self, center, label):
        super().__init__()
        self.centerX, self.centerY = center
        self.label = label
        self.label.show()

    def run(self):
        count = 0
        pixload = QPixmap(loadImg)
        width = pixload.width()
        pixload = pixload.scaledToWidth(width / 2)
        while True:
            if self.stop:
                break
            loadTransform = QTransform().rotate(360 / 12 * count)
            pixImage = pixload.transformed(loadTransform, mode=Qt.SmoothTransformation)
            width = pixImage.width()
            height = pixImage.height()
            self.label.resize(width, height)
            self.label.move(self.centerX - (width / 2), self.centerY - (height / 2))
            self.label.setPixmap(pixImage)
            count += 1
            self.msleep(100)

        print("loading stop")
        self.label.hide()


class RefCountThread(QThread):
    parent = None
    def __init__(self, parent):
        super().__init__()
        self.parent = parent

    def run(self):
        while True:
            print(sys.getrefcount(self.parent))
            self.sleep(1)


class GifThread(QThread):
    stop = False
    pause = False
    scale_thresh = 1

    def __init__(self, parent, chaFile, chaLabel, pos, scale, rotation, flipValue):
        super().__init__()
        self.parent = parent
        self.chaFile = chaFile
        self.filename = ""
        self.chaLabel = chaLabel
        self.pixList = None
        self.fileList = None
        self.stop = False
        self.pause = False
        self.x, self.y = pos
        self.scale = scale
        self.rotation = rotation
        self.flip = flipValue
        self.width = 10
        self.height = 10
        self.currentIndex = 0
        # self.refCountTh = RefCountThread(self)
        # self.refCountTh.start()

    def reset(self, chaFile, pos, scale, rotation, flipValue):
        if self.chaFile != chaFile:
            self.chaFile = chaFile
            self.filename = ""
            self.fileList = None
            self.pixList = None

        self.stop = False
        self.pause = False
        self.x, self.y = pos
        self.scale = scale
        self.rotation = rotation
        self.flip = flipValue
        self.currentIndex = 0

    # 해당 프레임 파일 주소를 반환
    def getFileName(self, idx):
        # 파일 번호는 1부터 시작
        return f"{meipassDir}/temp/forUnzip/{self.filename}-{str(idx + 1)}.png"

    # 현재 인덱스의 픽스맵을 리턴
    def getCurrentPixmap(self):
        return QPixmap(self.getFileName(self.currentIndex))

    def setPosition(self, x=None, y=None, width=None, height=None):
        if x is None or height is None:
            x = self.x
            y = self.y
        if width is None or height is None:
            size = self.chaLabel.pixmap().size()
            width = size.width()
            height = size.height()
        self.chaLabel.move(x - width / 2, y - height / 2)
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def run(self):
        # 첫 생성 시에만 압축 풀기
        if self.fileList is None:
            try:
                print("unzip")
                self.unzip()
            except Exception as e:
                print("GifRunError :", e)

        # 애니메이션 루프 재생
        # self.pixmapAnimation()
        self.pixmapAnimation_Threshold(quality=0.5)
        # self.fileAnimation()

        # 루프 종료 시 stop 체크
        if self.stop:
            # self.pixList = []
            print("쓰레드 quit")

    def unzip(self):
        # 경로 설정
        file_path = f'{meipassDir}/temp/forUnzip'

        # 압축 해제
        output_unzip = zipfile.ZipFile(self.chaFile, "r")  # "r": read 모드
        output_unzip.extractall(file_path)
        output_unzip.close()

        # 초기 설정
        filelist = output_unzip.namelist()
        if not filelist:
            raise Exception("압축파일 존재하지 않음")
        self.filename = filelist[0].split("/")[-1][:-6] # "-1.png"를 제거
        self.fileList = [None] * len(filelist)

        # 파일 번호 추출해서 순서대로 리스트에 할당
        for file in filelist:
            findStr = "-[0-9]+[.]png"
            m = re.findall(findStr, file)
            number: int = int(m[-1][1:-4]) - 1

            # 파일명 정렬해서 저장
            self.fileList[number] = file

    def makePixmapList(self):
        self.pixList = []
        transform = self.getTransform()
        for file in self.fileList:
            qImg = QPixmap(f"{meipassDir}/temp/forUnzip/{file}")
            if transform:
                qImg = qImg.transformed(transform, mode=Qt.SmoothTransformation)
            self.pixList.append(qImg)

    def makePixmapList_Threshold(self, quality=1.0):
        print("makePixmapList")
        self.pixList = []
        if self.scale <= quality:
            transform = self.getTransform()
        else:
            transform = QTransform().scale(self.flip * quality, quality).rotate(self.flip * self.rotation)
        for file in self.fileList:
            qImg = QPixmap(f"{meipassDir}/temp/forUnzip/{file}")
            if transform:
                qImg = qImg.transformed(transform, mode=Qt.SmoothTransformation)
            self.pixList.append(qImg)

    def pixmapAnimation(self):
        # Pixmap 생성
        self.makePixmapList()

        # width, height 구하기
        size = self.pixList[0].size()
        self.width = size.width()
        self.height = size.height()

        # QLabel 설정
        self.setPosition(x=self.x, y=self.y, width=self.width, height=self.height)
        self.chaLabel.resize(self.width, self.height)

        self.stop = False
        # 작동 시작. pixmap을 순서대로 계속 갈아끼우는 것으로 애니메이션 구현
        while True:
            # 현재 인덱스를 반환하기 위한 변수
            self.currentIndex = 0

            for frame in self.pixList:
                self.currentIndex += 1

                if self.stop or self.pause:  # quit으로 한 번에 탈출이 안 되서 일단 반복문 탈출
                    break

                try:
                    self.chaLabel.setPixmap(frame)
                except Exception as e:
                    print("L2DException:", e)
                self.msleep(33)

            if self.stop or self.pause:
                break

    def pixmapAnimation_Threshold(self, quality=1.0):
        print("pixmapAnimation")
        # Pixmap 생성
        self.makePixmapList_Threshold(quality=quality)

        # width, height 구하기
        size = self.pixList[0].size()
        self.width = size.width()
        self.height = size.height()

        if self.scale > quality:
            self.width *= self.scale / quality
            self.height *= self.scale / quality

        # QLabel 설정
        self.setPosition(x=self.x, y=self.y, width=self.width, height=self.height)
        self.chaLabel.resize(self.width, self.height)

        print("intoLoop")

        self.stop = False
        # 작동 시작. pixmap을 순서대로 계속 갈아끼우는 것으로 애니메이션 구현
        while True:
            # 현재 인덱스를 반환하기 위한 변수
            self.currentIndex = 0

            for frame in self.pixList:
                self.currentIndex += 1

                if self.stop or self.pause:  # quit으로 한 번에 탈출이 안 되서 일단 반복문 탈출
                    break

                try:
                    if self.scale > quality:
                        frame = frame.scaledToHeight(self.height, mode=Qt.SmoothTransformation)
                    self.chaLabel.setPixmap(frame)
                except Exception as e:
                    print("L2DException:", e)
                self.msleep(33)

            if self.stop or self.pause:
                break

    def fileAnimation(self):
        # 트랜스폼 객체
        transform = self.getTransform()

        size = None
        self.stop = False
        # 작동 시작. pixmap을 순서대로 계속 갈아끼우는 것으로 애니메이션 구현
        while True:
            # 현재 인덱스를 반환하기 위한 변수
            self.currentIndex = 0

            for file in self.fileList:
                self.currentIndex += 1

                if self.stop or self.pause:  # quit으로 한 번에 탈출이 안 되서 일단 반복문 탈출
                    break

                if self.parent.m_flag is False:
                    try:
                        pImg = QPixmap(f"{meipassDir}/temp/forUnzip/{file}")
                        if transform:
                            pImg = pImg.transformed(transform, mode=Qt.SmoothTransformation)

                        # width, height 구하기
                        if size is None:
                            size = pImg.size()
                            self.width = size.width()
                            self.height = size.height()

                            self.setPosition(x=self.x, y=self.y, width=self.width, height=self.height)
                            self.chaLabel.resize(self.width, self.height)

                        self.chaLabel.setPixmap(pImg)
                    except Exception as e:
                        print("L2DException:", e)
                self.msleep(33)

            if self.stop or self.pause:
                break

    def getTransform(self):
        edited = False
        transform = QTransform()
        if self.flip != 1 or self.scale != 1:
            edited = True
            transform = transform.scale(self.flip * self.scale, self.scale)
        if self.rotation != 0:
            edited = True
            transform = transform.rotate(self.flip * self.rotation)

        # 뒤집기, 크기 변형, 회전 등이 적용된 경우
        if edited:
            return transform
        # 없으면 None을 전달해 변형 연산을 적용하지 않도록
        else:
            return None


    def setSize(self, width=0, height=0, scale=1):
        if width and height:
            width *= scale
            height *= scale
        else:
            width = self.width * scale
            height = self.height * scale

        self.chaLabel.resize(width, height)

    def __del__(self):
        print("쓰레드 삭제")


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
        self.gifThs = {}    # 각 캐릭터의 라투디를 재생해주는 GifThread 객체 딕셔너리
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
        self.menu_stop = self.cmenu.addAction("라투디 정지")
        self.menu_stop.setCheckable(True)
        self.menu_stop.setChecked(False)
        self.menu_hide = self.cmenu.addAction("잠시 숨기기")
        self.menu_retire = self.cmenu.addAction("내보내기")
        self.cmenu.addSeparator()
        self.menu_group = self.cmenu.addAction("그룹 설정")
        self.menu_preset = self.cmenu.addAction("프리셋 관리")
        self.menu_manage = self.cmenu.addAction("위젯 설정")
        self.menu_quit = self.cmenu.addAction("종료")

        # 윈도우 설정
        self.setupWindow()

        # 로딩창
        self.loadLabel = QLabel('', self)
        self.loadLabel.hide()

    # 스티커 종료 시 작동
    def closeEvent(self, QCloseEvent):
        print("스티커 꺼짐")

    # 데이터 로딩
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
            'Position': None,
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
                    chaData["Position"] = data.get("Position", None)
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

                    # 후처리
                    if chaData["Position"] is None:
                        chaData["Position"] = [self.size().width() / 2, self.size().height() / 2]  # 화면 중앙

                    self.setCharacter(data=chaData, key=key)

                    # dafaultData에 각 캐릭터 정보를 추가
                    defaultData['characters'][key] = chaData


                # 완성된 defaultData를 stickers에 할당
                self.stickers = defaultData
                print(self.stickers)

            except Exception as e:
                print("read Exception: " + str(e))
                self.stickers = {}

    # LOSticker에게로 데이터 전송 후 세이브파일 작성
    def writeDataFile(self):
        self.saveEvent.emit({self.key: self.stickers})

    # 다른 그룹 데이터를 불러옴
    def resetSticker(self, data, key):
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
            chaSize = data['Size'] / 100
            chaRotation = data['Rotation'] / 100
            visible = data['Visible']
            position = data['Position']
            self.voiceSound[key] = None

            # 센터 계산
            if position is None:
                position = [self.size().width() / 2, self.size().height() / 2]
                data['Position'] = position

            # 파일이 존재하지 않는 경우
            if os.path.exists(chaFile) is False:
                return

            # 뒤집기 변수
            flipValue = 1
            if chaFlip:
                flipValue = -1

            # 이미지 파일 적용
            # gif일 경우
            if chaFile.split(".")[-1] in ["webm", "gif"]:
                # .frms 로딩
                ext = chaFile.split(".")[-1]
                frmsFile = chaFile[:-len(ext)] + "frms"

                if os.path.exists(frmsFile):
                    # 해당 부관에 이미 라투디 이미지가 할당된 경우
                    if key in self.gifThs and self.gifThs:
                        self.gifThs[key].stop = True
                        self.gifThs[key].wait(1000)
                        self.gifThs[key].reset(frmsFile, pos=position, scale=chaSize,
                                               rotation=chaRotation, flipValue=flipValue)
                    else:
                        self.gifThs[key] = GifThread(self, frmsFile, chaLabel, pos=position, scale=chaSize,
                                                     rotation=chaRotation, flipValue=flipValue)
                    self.gifThs[key].start()

                # frms 변환이 이루어지지 않은 경우
                else:
                    QMessageBox.warning(self, '변환 필요', "애니메이션 파일은 변환이 필요합니다.\n부관 설정에서 이미지를 다시 설정해주세요.")

            # 일반 이미지일 경우
            else:
                # 캐릭터 Pixmap 생성
                pixImage = QPixmap(chaFile)

                # 변형 적용
                transform = QTransform().scale(flipValue * chaSize, chaSize).rotate(flipValue * chaRotation)
                pixImage = pixImage.transformed(transform, mode=Qt.SmoothTransformation)

                # 라벨 설정
                width = pixImage.width() * chaSize
                height = pixImage.height() * chaSize
                x, y = position
                chaLabel.move(x - width / 2, y - height / 2)
                chaLabel.resize(width, height)
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

    # 부관 좌클릭 시작 이벤트
    def stickerMousePressEvent(self, event, key):
        self.m_flag = True
        self.m_Position = event.globalPos() - self.labels[key].pos()
        event.accept()  # 클릭이벤트를 처리하고 종료. ignore 시 부모위젯으로 이벤트가 넘어감
        self.setCursor(QCursor(Qt.OpenHandCursor))  # Change mouse icon
        self.m_info = (key, True)

    # 부관 쓰다듬기, 드래그 이벤트(캐릭터 이동, 쓰다듬기)
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

    # 부관 좌클릭 종료 이벤트(이동 종료, 일반 대사 출력)
    def stickerMouseReleaseEvent(self, event, key):
        if self.m_flag:
            # 이동 종료
            if self.menu_move.isChecked():
                pos = self.labels[key].pos()
                size = self.labels[key].pixmap().size()
                newPos = [pos.x() + size.width() / 2, pos.y() + size.height() / 2]
                self.stickers['characters'][key]['Position'] = newPos
                if key in self.gifThs and self.gifThs[key]:
                    self.gifThs[key].x = newPos[0]
                    self.gifThs[key].y = newPos[1]
                self.writeDataFile()
            # 쓰다듬기
            elif self.labels[key].rect().contains(event.pos()):
                self.idleVoicePlay(key)

            self.m_flag = False
            self.setCursor(QCursor(Qt.ArrowCursor))
            event.accept()
        self.m_info = None

    # x, y를 중심 좌표로 하여 이동
    def setPosition(self, key, x=None, y=None, width=None, height=None):
        label = self.labels[key]

        # 라투디면 쓰레드에 저장
        if key in self.gifThs and self.gifThs[key]:
            self.gifThs[key].setPosition(x, y, width, height)

        if x is None or y is None:
            pos = self.stickers['characters'][key]['Position']
            x, y = pos

        if width is None or height is None:
            width = label.pixmap().width()
            height = label.pixmap().height()

        label.move(x - width / 2, y - height / 2)


    # 부관 우클릭 시 나타나는 컨텍스트 메뉴 이벤트
    def stickerContextMenuEvent(self, event, key):
        if not self.labels[key].rect().contains(event.pos()):
            return

        action = self.cmenu.exec_(self.labels[key].pos() + event.pos())  # event.pos()만 하니까 화면 좌상단 구석에 생김
        if action == self.menu_setting:     # 부관 설정
            self.openSetting(key)
        elif action == self.menu_edit:      # 편집
            self.openEditWindow(key)
        elif action == self.menu_stop:      # 편집
            self.stopGifThread(key)
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

    def stopGifThread(self, key):
        if self.menu_stop.isChecked():
            self.gifThs[key].pause = True
        else:
            self.gifThs[key].pause = False
            self.gifThs[key].start()

    # 접속 대사 재생
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

    # 일반 대사 재생
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

    # 특수 대사 재생
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

    # 보이스 재생
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

    # 부관 숨기기
    def hideSticker(self, key):
        if self.key in self.stickerManager.groupUis and self.stickerManager.groupUis[self.key]:
            self.stickerManager.groupUis[self.key].hideSticker(key)
        else:
            self.labels[key].hide()
            self.stickers['characters'][key]["Visible"] = False
            self.writeDataFile()

    # 편집 창 열기
    def openEditWindow(self, key):
        chaFile = self.stickers['characters'][key]['CharacterImage']
        if not os.path.exists(chaFile):
            QMessageBox.warning(self, '파일 없음', "해당 부관의 이미지 파일을 찾을 수 없습니다.")
            return

        self.editWindow = CharacterEditWindow(self, key, chaFile, self.stickers['characters'][key])
        self.editWindow.editPixmapEvent.connect(self.editPixmapSticker)
        self.editWindow.show()

    # 편집 창에서 캐릭터의 크기, 회전 등을 수정했을 때 작동
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
            width = newPixmap.width()
            height = newPixmap.height()
            chaLabel.setPixmap(newPixmap)
            self.setPosition(key, width=width, height=height)
            chaLabel.resize(width, height)

        # 라투디 이미지일경우 쓰레드 객체에 정보 전달
        if key in self.gifThs and self.gifThs[key]:
            self.gifThs[key].flip = flipValue
            self.gifThs[key].scale = size
            self.gifThs[key].rotation = rotation

    # 프리셋 관리 창에서 스티커 종료 시 작동
    def groupQuit(self):
        print("groupQuit")
        for key, gifTh in self.gifThs.items():
            if gifTh:
                gifTh.stop = True
                gifTh.wait()

        self.gifThs = {}

        for key, label in self.labels.items():
            movie = label.movie()
            if movie:
                movie.deleteLater()
            label.close()


        self.gifThs = {}
        self.labels = {}
        self.stickers = {}
        self.close()
        print("groupQuit 완료")

    def gifThreadQuit(self, key):
        if key in self.gifThs and self.gifThs[key]:
            gifThs = self.gifThs[key]
            print("쓰레드 stop")
            gifThs.stop = True
            print("쓰레드 wait 5000")
            gifThs.wait(5000)
            print("쓰레드 terminate")
            gifThs.terminate()
            print("쓰레드 wait")
            gifThs.wait()
            print("작업 종료")

            # del self.gifThs[key]
            self.gifThs[key].deleteLater()
            del self.gifThs[key]

    # 캐릭터 업무해제 요청
    def characterQuit(self, key):
        # 라투디라면 쓰레드 종료
        self.gifThreadQuit(key)

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
        if key in self.labels and self.labels[key]:
            self.labels[key].close()
            del self.labels[key]
        
        # 저장
        self.stickerManager.thereIsSomethingToSave()

    # 스티커 윈도우 설정
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

    # 부관 설정 오픈
    def openSetting(self, chaKey):
        self.stickerManager.openSettingUi(self.key, chaKey)
    
    def __del__(self):
        print("스티커 객체 삭제")

    # 캐릭터 애니메이션 정지/시작 (편집 창)
    def setCharacterPause(self, key, value):
        self.gifThs[key].pause = value
        if value is False:
            self.gifThs[key].start()

    # 캐릭터 애니메이션 현재 Pixmap 전달
    def getCharacterPixmap(self, key):
        return self.gifThs[key].getCurrentPixmap()

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

    # 원본 저장
    pixmap = None

    editPixmapEvent = pyqtSignal(str, object, bool, float, float)

    def __init__(self, parent, key, chaFile, info):
        super().__init__()
        self.parent = parent
        self.chaKey = key
        self.chaFile = chaFile

        # 파일 검사
        if chaFile:
            ext = chaFile.split(".")[-1]
            if ext == "webm":
                self.parent.setCharacterPause(key, value=True)
                self.pixmap = self.parent.getCharacterPixmap(key)
            else:
                self.pixmap = QPixmap(chaFile)

        self.flipValue = info['Flip']
        self.sizeValue = info['Size']
        self.rotateValue = info['Rotation']
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

        # LineEdit 값 할당
        self.sizeChange()
        self.rotateChange()

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

    def closeEvent(self, QCloseEvent):
        self.parent.setCharacterPause(self.chaKey, value=False)


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
        self.chaProgress.setRange(0, 0)
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
        zipEvent = pyqtSignal()  # 압축 작업에 들어갔음을 알림
        cancelEvent = pyqtSignal()  # 변환 취소된 후 종료될 때 작동
        stop = False
        process = None

        def __init__(self, chaFile):
            super().__init__()
            print("gifThread Init")
            self.chaFile = chaFile

        @staticmethod
        def timeToInt(timestr):
            times = timestr.split(':')
            hour = int(times[0])
            minute = int(times[1])
            second = float(times[2])
            return (hour * 3600) + (minute * 60) + second

        def findFiles(self, filename):
            fileList = []
            return fileList

        def deleteFiles(self, filename):
            fileList = []

        def __del__(self):
            print("변환쓰레드 삭제")

        def run(self):
            print("gifThread Run")
            # 파일 확장자 추출
            ext = self.chaFile.split(".")[-1]

            # gif일 경우
            if ext == "gif":
                self.gifToPngs()

            # webm일 경우
            elif ext == "webm":
                print("gifThread webmToPngs")
                self.webmToPngs()

        def gifToPngs(self):
            # 새 파일명 설정
            filename = os.path.splitext(self.chaFile)[0].split("/")[-1]

            # 프레임 추출 후 저장
            frames = iio.imread(self.chaFile, index=None, mode="RGBA")
            length = len(frames)
            for idx, frame in enumerate(frames):
                if self.stop:
                    self.cancelEvent.emit()
                    return

                newChaFile = f"{meipassDir}/temp/forZip/{filename}-{idx}.png"
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGBA)
                cv2.imwrite(newChaFile, frame)
                rate = (idx + 1) / length
                self.updateEvent.emit("%.2f" % (rate * 100) + "%", int(rate * 10000))

            self.pngsToFrms(filename)
            self.resultEvent.emit(self.chaFile)

        def webmToPngs(self):
            # 새 파일명 설정
            filename = os.path.splitext(self.chaFile)[0].split("/")[-1]
            newChaFile = f"{meipassDir}/temp/forZip/{filename}-%d.png"

            # ffmpeg 명령어
            command = [
                ffmpegEXE,
                "-y",
                "-ss", "00:00",  # 그냥 돌리면 진행률이 안 뜨길래 추가 옵션을 아무거나 하나 달음
                "-c:v", "libvpx-vp9",
                "-i", self.chaFile,
                "-lavfi", "split[v],palettegen,[v]paletteuse",
                newChaFile
            ]

            # subprocess에서 ffmpeg 실행
            try:
                duration = None
                self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                                universal_newlines=True)

                # 출력되는 내용 읽기
                for line in self.process.stdout:
                    if self.stop:
                        break

                    # 출력된 내용을 파싱하여 진행률 표기
                    if "DURATION" in line:
                        dataList = line.split()
                        duration = self.timeToInt(dataList[2][0:12])
                        # self.updateEvent.emit("0%", 0)
                    if "time=" in line:
                        timetext = re.search("time=-?[0-9:.]+", line)  # time=xx:xx:xx.xxx 찾기
                        if timetext:
                            dataList = timetext.group()[5:]

                        # 0이 아닌 양수일 때만 진행률 계산
                        tempTime = self.timeToInt(dataList)
                        if tempTime > 0:
                            currentTime = tempTime
                            rate = currentTime / duration
                            self.updateEvent.emit("%.2f" % (rate * 100) + "%", int(rate * 10000))

                # 변환 취소 시 raise로 탈출
                if self.stop:
                    if self.process:
                        self.process.kill()
                    raise Exception("변환 취소됨")

                else:
                    self.process = None
                    print("FFmpeg Script Ran Successfully")

                    # 변환된 파일 압축
                    print("gifThread pngsToFrms")
                    self.pngsToFrms(filename)

                    # 종료 알림
                    print("gifThread end")
                    self.resultEvent.emit(self.chaFile)

            except Exception as e:
                print("ConvertException: ", e)

                # 변환 취소됨을 알림
                self.cancelEvent.emit()

        def pngsToFrms(self, filename):
            # 변환된 파일 압축
            self.zipEvent.emit()
            file_path = os.path.abspath(f"{meipassDir}/temp/forZip")
            owd = os.getcwd()  # 현재 working directory 를 기록해둔다
            os.chdir(file_path)  # 압축 파일 생성할 폴더로 working directory 를 이동시킨다

            zip_file = zipfile.ZipFile(f"{filename}.frms", "w")  # "w": write 모드
            for (path, dir, files) in os.walk(file_path):
                for file in files:
                    if file.endswith('.png') and filename + "-" in file:
                        # 상대경로를 활용하여 압축한다. (os.path.relpath)
                        zip_file.write(os.path.join(os.path.relpath(path, file_path), file),
                                       compress_type=zipfile.ZIP_DEFLATED)

            zip_file.close()

            # 완성된 압축파일 이동
            os.chdir(owd)  # 원래의 working directory 로 되돌린다
            shutil.move(f"{file_path}/{filename}.frms", f"./character/{filename}.frms")

            # 변환에 사용한 파일 삭제
            for file in os.scandir(file_path):
                os.remove(file.path)

    def setCharacter(self):
        if self.convertTh and self.convertTh.process:
            QMessageBox.warning(self, "gif 변환 중", "gif 변환 중입니다.\n변환 작업을 취소해야 부관을 변경할 수 있습니다.")
            return

        fname = QFileDialog.getOpenFileName(self, "캐릭터 선택", "./character", "Character File(*.webp *.png *.gif *.webm)")
        if fname[0]:
            chaFile = fname[0]

            # 애니메이션이면 frms 파일이 없을 경우 변환 쓰레드 호출
            ext = chaFile.split(".")[-1]
            if ext in ["webm", "gif"] and not os.path.exists(chaFile[:-len(ext)] + "frms"):
                self.callConvertThread(chaFile, ext)
            else:
                self.chaFile = chaFile
                self.chaLabel.setText(chaFile.split('/')[-1])

    def callConvertThread(self, chaFile, ext):
        buttonReply = QMessageBox.information(
            self, 'gif 변환 알림', f"{ext} 파일은 변환을 거쳐야 사용할 수 있습니다.\n지금 변환하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if buttonReply == QMessageBox.Yes:
            self.chaLabel.setText("파일 변환중...")
            self.cha_HBL3_Widget.show()
            self.chaProgress.setValue(0)
            self.convertTh = self.ConvertWebmtoGif(chaFile)
            self.convertTh.updateEvent.connect(self.progressUpdate)
            self.convertTh.resultEvent.connect(self.setGifCharacter)
            self.convertTh.cancelEvent.connect(self.convertCanceled)
            self.convertTh.zipEvent.connect(self.noticeOnZipping)
            self.convertTh.start()
        else:
            self.chaLabel.setText(chaFile.split('/')[-1])

    # 변환 중 프로그레스 바 설정
    @pyqtSlot(str, int)
    def progressUpdate(self, rate_str, rate_int):
        self.chaProgress.setRange(0, 10000)
        self.chaLabel.setText("파일 변환중... " + rate_str)
        self.chaProgress.setValue(rate_int)

    # 변환 취소 요청
    @pyqtSlot()
    def convertStop(self):
        # FFmpeg 종료
        self.convertTh.stop = True
        if self.convertTh:
            if self.convertTh.process:
                self.convertTh.process.kill()
                self.chaLabel.setText("변환 취소 중...")
            else:
                self.convertCanceled()

    # 변환 취소된 후
    @pyqtSlot()
    def convertCanceled(self):
        self.convertTh.deleteLater()
        self.convertTh = None
        self.cha_HBL3_Widget.hide()

        # 기존에 설정해둔 이미지가 있을 경우 텍스트 복구
        if self.chaFile:
            self.chaLabel.setText(self.chaFile.split('/')[-1])
        else:
            self.chaLabel.setText("")

    @pyqtSlot()
    def noticeOnZipping(self):
        self.chaLabel.setText("변환을 마무리하는 중...")
        self.cha_HBL3_Widget.hide()

    # 변환 완료 후 실행됨
    @pyqtSlot(str)
    def setGifCharacter(self, chaFile):
        self.convertTh = None
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