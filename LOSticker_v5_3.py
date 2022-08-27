import os, sys, json, random, time, subprocess
from PyQt5.QtWidgets import QMainWindow, QSystemTrayIcon, QAction, QMenu, QLabel, QWidget, QDialog, QFileDialog, \
    QApplication, QTableWidget, QPushButton, QTableWidgetItem, QVBoxLayout, QHBoxLayout, QCheckBox, QHeaderView
from PyQt5 import uic
from PyQt5.QtCore import QThread, pyqtSignal, QSize, Qt, pyqtSlot
from PyQt5.QtGui import QIcon, QCursor, QIntValidator, QMovie
from PIL import Image, ImageQt
from pygame import mixer
from ManageWindow import ManageWindow
from Sticker2 import Sticker, SettingWindow

'''
빌드 후 임시폴더 위치를 찾기 위한 설정
currentDir = exe파일 위치
meipassDir = 임시폴더 위치(외부 리소스 경로)
개발도중에는 exe파일 위치와 임시폴더 위치가 동일
'''
currentDir = os.getcwd()
try:
    meipassDir = sys._MEIPASS
except:
    meipassDir = currentDir

os.chdir(meipassDir)
# scaleWindowUi = uic.loadUiType("./scale.ui")[0]
iconPath = os.path.abspath("./lise.ico")

os.chdir(currentDir)


# os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
# os.environ["QT_SCALE_FACTOR"] = "1"
# os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
# QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True) #enable highdpi scaling
# QApplication.setAttribute(Qt.AA_DisableHighDpiScaling, True) #enable highdpi scaling
# QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True) #use highdpi icons

class SaveTimer(QThread):
    isSaved = True
    saveSignal = pyqtSignal()
    manager = None

    def __init__(self, _manager):
        super().__init__()
        self.manager = _manager

    def run(self):
        while True:
            # 0.1초마다 노래 하나 끝났는지 확인
            for i in range(10):
                time.sleep(0.1)
                if self.manager.bgmChannel:
                    if not self.manager.bgmChannel.get_busy():
                        self.manager.bgmPlay(self.manager.nextBgmIndex)

            # 1초마다 세이브 확인
            if self.isSaved is False:
                self.saveSignal.emit()
                self.isSaved = True


class StickerManager(QMainWindow):
    # 현재 켜져 있는 부관
    # stickerDict = {}
    currentSticker = None

    # 로딩 가능한 부관 전체 및 읽기/쓰기용 딕셔너리
    jsonData = {
        'BGM': {
            'BGMFiles': [],
            'BGMVolume': 70
        },
        'Stickers': {}
    }

    initFile = {
        "PresetKey": '0',
        "BGM": {
            'BGMFiles': [],
            'BGMVolume': 70
        },
        "Stickers": {}
    }

    initGroup = {
        "options": {
            "GroupName": "",
            "AlwaysOnTop": False
        },
        "characters": {}
    }

    initCharacter = {
        "CharacterName": "",
        "Position": [0, 0],  # 위치
        "Depth": 0,  # 놓인 순서
        "CharacterImage": "",
        "LoginVoiceFiles": [],
        "IdleVoiceFiles": [],
        "SpecialVoiceFiles": [],
        "CharacterSize": 800,
        "SizeRestrict": False,
        "VoiceVolume": 50
    }

    presetKey = None  # 현재 실행중인 프리셋의 키 번호
    manageUi = None  # ManageWindow 객체
    groupUis = {}  # 다중부관 그룹 관리 객체. 각 프리셋 당 하나씩 관리. 키값 : UI객체
    presetUi = None  # 프리셋 관리 객체
    settingUi = None  # 캐릭터 설정창 객체
    bgmFile = []  # 브금 파일명 리스트
    bgmSound = None  # Sound 객체. 음원 재생용
    bgmChannel = None  # Channel 객체
    nextBgmIndex = 0  # 순차재생 다음 인덱스
    bgmVolume = 50  # 브금 볼륨
    tray_icon = None  # QSystemTrayIcon 객체
    saveTimer = None  # SaveTimer 객체. 주기적으로 정보를 자동저장함

    def __init__(self):
        super().__init__()
        # Init QSystemTrayIcon
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(iconPath))

        # 세이브용 스레드 실행
        self.saveTimer = SaveTimer(self)
        self.saveTimer.saveSignal.connect(self.writeDataFile)
        self.saveTimer.start()

        # 트레이 메뉴 설정
        manage_action = QAction("홈 열기", self)
        preset_action = QAction("프리셋 열기", self)
        hide_action = QAction("숨기기", self)
        call_action = QAction("숨김 해제", self)
        quit_action = QAction("종료", self)
        manage_action.triggered.connect(self.openManageUi)
        preset_action.triggered.connect(self.openPresetUi)
        hide_action.triggered.connect(self.hideGroup)
        call_action.triggered.connect(self.callGroup)
        quit_action.triggered.connect(self.programQuit)
        tray_menu = QMenu()
        tray_menu.addAction(manage_action)
        tray_menu.addAction(preset_action)
        tray_menu.addAction(hide_action)
        tray_menu.addAction(call_action)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

        # 세이브 파일 리딩
        self.readDataFile()

        # 로그인 보이스 실행
        if self.currentSticker:
            self.currentSticker.loginVoicePlay()

    def readDataFile(self):
        try:
            with open("./data.LOSJ", "r", encoding="UTF-8") as jsonFile:
                tempJsonData = json.load(jsonFile)

                # 키 에러를 일으키지 않도록 모든 키의 접근은 키의 존재를 확인한 후 진행
                # 실행할 프리셋 번호 확인
                self.presetKey = None
                if 'PresetKey' in tempJsonData:
                    if tempJsonData['PresetKey'] in tempJsonData['Stickers']:  # 선택된 프리셋 번호가 프리셋에 존재하는지
                        self.presetKey = tempJsonData['PresetKey']

                self.jsonData['PresetKey'] = self.presetKey

                # 브금 설정
                if 'BGM' in tempJsonData:
                    bgmData = tempJsonData['BGM']
                    if 'BGMFiles' in bgmData:
                        self.bgmFile = bgmData['BGMFiles']
                        self.jsonData['BGM']['BGMFiles'] = bgmData['BGMFiles']

                    try:
                        if 'BGMVolume' in bgmData:
                            self.bgmVolume = int(bgmData['BGMVolume'])
                            self.jsonData['BGM']['BGMVolume'] = bgmData['BGMVolume']
                    except:
                        pass

                    # 브금 실행
                    if not self.bgmSound:
                        self.bgmPlay()

                # 스티커 정보
                if 'Stickers' in tempJsonData:
                    stickerData = tempJsonData['Stickers']
                    for key in stickerData:
                        # 프리셋 정보
                        data = stickerData[key]

                        # 딕셔너리에 저장
                        self.jsonData['Stickers'][key] = data

                        # 실행해야 할 프리셋과 키가 같으면 스티커 생성
                        if self.presetKey == key:
                            self.loadSticker(data=data, key=key)


        except Exception as e:
            if not os.path.exists("./data.LOSJ"):
                self.jsonData = self.initFile

        finally:
            # 걸러진 데이터로 다시 저장
            self.thereIsSomethingToSave()

            # 캐릭터가 없으면 프리셋 창 오픈
            if not self.currentSticker:
                self.openPresetUi()

    def loadSticker(self, data, key):
        sticker = Sticker(self, data=data, key=key)
        self.currentSticker = sticker
        sticker.showMaximized()
        self.presetKey = key
        self.jsonData['PresetKey'] = key
        self.thereIsSomethingToSave()

    def writeDataFile(self):
        with open("./data.LOSJ", "w", encoding="UTF-8") as jsonFile:
            json.dump(self.jsonData, jsonFile, indent=2)
            print("save")

    # 저장할 필요가 있을 때만 자동저장을 호출함
    def thereIsSomethingToSave(self):
        if self.saveTimer:
            self.saveTimer.isSaved = False

    def bgmPlay(self, bgmIndex=0):
        # bgm 목록이 존재하는가
        if not self.bgmFile:
            if self.bgmSound:
                self.bgmSound.stop()
                self.bgmSound = None
                self.bgmChannel = None
                self.nextBgmIndex = 0
            return

        # bgmIndex가 -1이면 랜덤재생
        if bgmIndex == -1:
            bgmIndex = random.randrange(0, len(self.bgmFile))

        # 인덱스가 크기를 벗어나진 않는가
        if bgmIndex >= len(self.bgmFile):
            bgmIndex = 0

        # bgm 파일이 존재하는가
        if not os.path.exists(self.bgmFile[bgmIndex]):
            return

        try:
            if self.bgmSound is not None:
                self.bgmSound.stop()

            freq = 44100  # sampling rate, 44100(CD), 16000(Naver TTS), 24000(google TTS)
            bitsize = -16  # signed 16 bit. support 8,-8,16,-16
            channels = 2  # 1 is mono, 2 is stereo
            buffer = 2048  # number of samples (experiment to get right sound)

            # default : pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=4096)
            mixer.init(freq, bitsize, channels, buffer)
            self.bgmSound = mixer.Sound(self.bgmFile[bgmIndex])
            if self.bgmChannel is None:
                self.bgmChannel = mixer.find_channel()
            self.bgmChannel.set_volume(self.bgmVolume / 100)
            self.bgmChannel.play(self.bgmSound)
            # self.bgmSound.set_volume(self.bgmVolume / 100)
            # self.bgmChannel = self.bgmSound.play()

            self.nextBgmIndex = bgmIndex + 1

        except Exception as e:
            print("BGM Exception: " + str(e))

    # 각 그룹에 부여된 키 중 비어있는 키를 찾기
    def findProperGroupKey(self):
        key = 0
        while str(key) in self.jsonData['Stickers']:
            key += 1
        return str(key)

    # 각 부관에 부여된 키 중 비어있는 키를 찾기
    def findProperChaKey(self, gkey):
        key = 0
        while str(key) in self.jsonData['Stickers'][gkey]['characters']:
            key += 1
        return str(key)

    # 스티커 정보 저장
    def stickerSave(self, data):
        self.jsonData['Stickers'].update(data)
        self.thereIsSomethingToSave()

    def stickerAdd(self):
        pass

    # 모든 스티커 숨기기
    def hideGroup(self):
        if self.currentSticker:
            self.currentSticker.hide()
            if self.settingUi:
                self.settingUi.close()

    # 숨긴 스티커 볼러오기
    def callGroup(self):
        if self.currentSticker:
            self.currentSticker.show()

    def stickerRemove(self, key):
        if key in self.stickerDict:
            del self.stickerDict[key]
        if key in self.jsonData['Stickers']:
            del self.jsonData['Stickers'][key]
        self.thereIsSomethingToSave()

    def bgmChanged(self, _bgmFile):
        self.bgmFile = _bgmFile
        self.jsonData['BGM']['BGMFiles'] = _bgmFile
        self.thereIsSomethingToSave()
        self.bgmPlay()

    def bgmVolumeChanged(self, _bgmVolume):
        self.bgmVolume = _bgmVolume
        self.jsonData['BGM']['BGMVolume'] = _bgmVolume
        if self.bgmChannel:
            self.bgmChannel.set_volume(self.bgmVolume / 100)
        self.thereIsSomethingToSave()

    def managerUiQuit(self):
        self.manageUi = None

    def programQuit(self):
        if self.currentSticker:
            self.currentSticker.close()
        if self.manageUi:
            self.manageUi.close()
        sys.exit()

    def openManageUi(self):
        if not self.manageUi:
            self.manageUi = ManageWindow()
            self.manageUi.addEvent.connect(self.stickerAdd)
            self.manageUi.loadEvent.connect(self.callGroup)
            self.manageUi.quitEvent.connect(self.managerUiQuit)
            self.manageUi.endEvent.connect(self.programQuit)
            self.manageUi.bgmChangeEvent.connect(self.bgmChanged)
            self.manageUi.bgmVolumeEvent.connect(self.bgmVolumeChanged)
            self.manageUi.volumeSlider.setValue(self.bgmVolume)

        self.manageUi.show()

    def openGroupUi(self, groupKey):
        subName = self.jsonData['Stickers'][groupKey]['options']['GroupName']

        if groupKey not in self.groupUis or self.groupUis[groupKey] is None:
            self.groupUis[groupKey] = GroupManager(manage=self, subName=subName, gKey=groupKey)

        self.groupUis[groupKey].show()

    # 그룹 창이 닫힌 경우
    def closeGroupUi(self, groupKey):
        if groupKey in self.groupUis:
            self.groupUis[groupKey] = None

    # 그룹이 삭제된 경우
    def deleteGroupUi(self, groupKey):
        if groupKey in self.groupUis:
            del self.groupUis[groupKey]

    def openPresetUi(self):
        if not self.presetUi:
            self.presetUi = PresetManager(self)

        self.presetUi.show()

    def openSettingUi(self, groupKey, chaKey):
        if self.settingUi is None:
            # 전송할 데이터 준비
            data = self.jsonData['Stickers'][groupKey]['characters'][chaKey]
            chaFile = data['CharacterImage']  # 이미지 파일 경로
            loginVoiceFile = data['LoginVoiceFiles']  # 로그인 보이스 경로 리스트
            idleVoiceFile = data['IdleVoiceFiles']  # 터치 보이스 경로 리스트
            specialVoiceFile = data['SpecialVoiceFiles']  # 특수터치 보이스 경로 리스트
            chaSize = data['CharacterSize']  # 캐릭터 사이즈 제한값
            voiceVolume = data['VoiceVolume']  # 보이스 볼륨값
            isSizeRestricted = data['SizeRestrict']  # 사이즈 제한 여부

            self.settingUi = SettingWindow()
            self.settingUi.setParent(self)
            self.settingUi.setSetting(chaFile, loginVoiceFile, idleVoiceFile, specialVoiceFile, chaSize, voiceVolume,
                                      isSizeRestricted)
            r = self.settingUi.showModal()

            if r:
                # 캐릭터 파일
                if os.path.exists(self.settingUi.chaFile):
                    # if not self.chaFile:
                    #     # 스티커 생성
                    #     self.assignEvent.emit(self.key, self)

                    chaFile = self.settingUi.chaFile

                # 캐릭터 크기 제한
                isSizeRestricted = self.settingUi.imageCheckBox.isChecked()

                # 캐릭터 사이즈
                try:
                    if self.settingUi.chaSizeLine.text():
                        chaSize = int(self.settingUi.chaSizeLine.text())
                    else:
                        chaSize = 800
                except:
                    pass

                # 접속 대사 각 파일 존재하는지 검사 후 저장
                tempLoginVoice = []
                for file in self.settingUi.loginVoiceFile:
                    if os.path.exists(file):
                        tempLoginVoice.append(file)
                if tempLoginVoice:
                    loginVoiceFile = tempLoginVoice

                # 일반 대사
                tempIdleVoice = []
                for file in self.settingUi.idleVoiceFile:
                    if os.path.exists(file):
                        tempIdleVoice.append(file)
                if tempIdleVoice:
                    idleVoiceFile = tempIdleVoice

                # 특수터치 대사
                tempSpecialVoice = []
                for file in self.settingUi.specialVoiceFile:
                    if os.path.exists(file):
                        tempSpecialVoice.append(file)
                if tempSpecialVoice:
                    specialVoiceFile = tempSpecialVoice

                # 보이스 볼륨
                voiceVolume = self.settingUi.voiceSlider.value()

                # 데이터 저장
                data['CharacterImage'] = chaFile
                data['LoginVoiceFiles'] = loginVoiceFile
                data['IdleVoiceFiles'] = idleVoiceFile
                data['SpecialVoiceFiles'] = specialVoiceFile
                data['CharacterSize'] = chaSize
                data['VoiceVolume'] = voiceVolume
                data['SizeRestrict'] = isSizeRestricted
                self.jsonData['Stickers'][groupKey]['characters'][chaKey] = data

                # 현재 실행되어 있는 스티커일경우
                if groupKey == self.presetKey:
                    self.currentSticker.stickers['characters'][chaKey] = data
                    self.currentSticker.setCharacter(data, chaKey)  # 스티커에 할당

                self.thereIsSomethingToSave()  # 저장

        self.settingUi = None


class GroupManager(QWidget):
    groupKey = '-1'
    rowCount = 0
    table = None
    groupItems = []
    stickerManager = None  # StickerManager 객체

    def __init__(self, manage, subName="", gKey='-1'):
        super().__init__()
        self.groupKey = gKey
        self.stickerManager = manage
        self.setWindowTitle(subName + " 그룹 관리")
        self.InitUi()

    def InitUi(self):
        # 위젯 추가
        # 항상 위에 고정 체크박스
        self.AOTCheckBox = QCheckBox("항상 위에 고정")

        # Always on Top 설정
        self.AOTCheckBox.setChecked(self.stickerManager.jsonData['Stickers'][self.groupKey]['options']['AlwaysOnTop'])
        self.AOTCheckBox.stateChanged.connect(self.setAlwaysOnTop)

        self.newButton = QPushButton("새 부관 추가")  # 그룹 추가 버튼 위젯
        self.table = QTableWidget(self)  # 테이블 위젯

        # 위젯 설정
        # self.newButton.setMinimumHeight(31)
        self.newButton.setStyleSheet("padding: 10px;")
        self.table.setMinimumSize(500, 200)
        self.table.setColumnCount(5)
        self.table.setRowCount(self.rowCount)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # 레이아웃 설정
        mainLayout = QHBoxLayout()
        mainLayout.setContentsMargins(0, 0, 0, 0)

        innerBox = QVBoxLayout()
        innerBox.setContentsMargins(20, 20, 20, 20)
        innerBox.addWidget(self.AOTCheckBox, alignment=Qt.AlignTop | Qt.AlignRight)
        innerBox.addWidget(self.newButton, alignment=Qt.AlignLeft)
        innerBox.addWidget(self.table)
        innerBoxWidget = QWidget()
        innerBoxWidget.setLayout(innerBox)
        mainLayout.addWidget(innerBoxWidget)
        self.setLayout(mainLayout)

        # 열 제목 지정
        self.table.setHorizontalHeaderLabels(
            ['부관 이름', '상태', '숨기기', '부관 설정', '업무 해제']
        )

        self.LoadItem()
        self.newButton.released.connect(self.AddItem)

    def LoadItem(self):
        # 부관 정보 로딩
        for chaKey, data in self.stickerManager.jsonData['Stickers'][self.groupKey]['characters'].items():
            chaName = ""
            if 'CharacterName' in data:
                chaName = data["CharacterName"]

            self.rowCount += 1
            self.table.setRowCount(self.rowCount)

            group = GroupItem(self, chaName, True, ckey=chaKey)
            self.groupItems.append(group)

            # 표에 초기 데이터 할당
            idx = self.rowCount - 1
            self.table.setItem(idx, 0, group.chaNameItem)
            self.table.setItem(idx, 1, group.stateItem)
            item = self.table.item(idx, 1)
            item.setFlags(item.flags() ^ Qt.ItemFlag.ItemIsEditable)
            self.table.setCellWidget(idx, 2, group.hideButton)
            self.table.setCellWidget(idx, 3, group.manageButton)
            self.table.setCellWidget(idx, 4, group.deleteButton)

    def AddItem(self):
        self.rowCount += 1
        self.table.setRowCount(self.rowCount)

        chaName = "부관 " + str(self.rowCount)
        chaKey = self.stickerManager.findProperChaKey(self.groupKey)

        group = GroupItem(self, chaName, True, ckey=chaKey)
        self.groupItems.append(group)

        # 표에 초기 데이터 할당
        idx = self.rowCount - 1
        self.table.setItem(idx, 0, group.chaNameItem)
        self.table.setItem(idx, 1, group.stateItem)
        item = self.table.item(idx, 1)
        item.setFlags(item.flags() ^ Qt.ItemFlag.ItemIsEditable)
        self.table.setCellWidget(idx, 2, group.hideButton)
        self.table.setCellWidget(idx, 3, group.manageButton)
        self.table.setCellWidget(idx, 4, group.deleteButton)

        # 스티커에 초기 부관 데이터 할당
        data = {
            chaKey: {
                "CharacterName": chaName,
                "Position": [0, 0],  # 위치
                "Depth": idx,  # 놓인 순서
                "CharacterImage": "",
                "LoginVoiceFiles": [],
                "IdleVoiceFiles": [],
                "SpecialVoiceFiles": [],
                "CharacterSize": 800,
                "SizeRestrict": False,
                "VoiceVolume": 50
            }
        }

        self.stickerManager.jsonData['Stickers'][self.groupKey]["characters"].update(data)

        self.stickerManager.thereIsSomethingToSave()

    def DeleteItem(self):
        currentRow = self.table.currentRow()  # 표에서 선택한 행
        chaKey = self.groupItems[currentRow].chaKey  # 해당 그룹의 키 번호

        self.table.removeRow(currentRow)
        self.rowCount -= 1
        del self.groupItems[currentRow]  # 표에서 제거
        del self.stickerManager.jsonData['Stickers'][self.groupKey]['characters'][chaKey]  # jsonData 수정

        # 실행중인 스티커라면 스티커 객체에 삭제해달라고 요청
        if self.groupKey == self.stickerManager.presetKey:
            self.stickerManager.currentSticker.characterQuit()

        self.stickerManager.thereIsSomethingToSave()

    def setAlwaysOnTop(self):
        aot = self.AOTCheckBox.isChecked()
        self.stickerManager.jsonData['Stickers'][self.groupKey]['options']['AlwaysOnTop'] = aot
        self.stickerManager.thereIsSomethingToSave()

        # 해당 스티커가 켜져있는경우 세팅해주기
        if self.groupKey == self.stickerManager.presetKey:
            sticker = self.stickerManager.currentSticker
            sticker.AlwaysOnTop = aot
            sticker.setupWindow()

    def closeEvent(self, event):
        self.stickerManager.closeGroupUi(self.groupKey)


class GroupItem:
    chaName = ""
    chaKey = '-1'
    state = False
    stateString = ""
    hideButton = None
    manageButton = None
    deleteButton = None
    parent = None

    chaNameItem = None
    stateItem = None

    def __init__(self, p, _chaName, _state, ckey):
        self.parent = p
        self.chaName = _chaName
        self.state = _state
        self.chaKey = ckey
        if _state:
            self.stateString = "업무 중"
            self.hideButton = QPushButton("숨기기")
        else:
            self.stateString = "숨김"
            self.hideButton = QPushButton("숨김 해제")
        self.manageButton = QPushButton("부관 설정")
        self.deleteButton = QPushButton("업무 해제")
        self.chaNameItem = QTableWidgetItem(self.chaName)
        self.stateItem = QTableWidgetItem(self.stateString)

        # 이벤트 설정
        self.hideButton.released.connect(self.changeState)
        self.manageButton.released.connect(self.openSettingUi)
        self.deleteButton.released.connect(self.parent.DeleteItem)

    def changeState(self):
        if self.state:
            self.state = False
            self.stateString = "숨김"
            self.stateItem.setText(self.stateString)
            self.hideButton.setText("숨김 해제")
        else:
            self.state = True
            self.stateString = "업무 중"
            self.stateItem.setText(self.stateString)
            self.hideButton.setText("숨기기")

    def openSettingUi(self):
        self.parent.stickerManager.openSettingUi(self.parent.groupKey, self.chaKey)


class PresetManager(QWidget):
    rowCount = 0
    currentGroup = 0
    table = None
    presetItems = []
    stickerManager = None  # StickerManager 객체

    def __init__(self, manage, _rowCount=0):
        super().__init__()
        self.rowCount = _rowCount
        self.setWindowTitle("전체 부관")
        self.stickerManager = manage
        self.InitUi()

    # UI 설정
    def InitUi(self):
        self.sender
        # 위젯 추가
        self.newButton = QPushButton("프리셋 추가")  # 그룹 추가 버튼 위젯
        self.table = QTableWidget(self)  # 테이블 위젯

        # 위젯 설정
        # self.newButton.setMinimumHeight(31)
        self.newButton.setStyleSheet("padding: 10px;")
        self.table.setMinimumSize(500, 200)
        self.table.setColumnCount(5)
        self.table.setRowCount(self.rowCount)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # 레이아웃 설정
        mainLayout = QHBoxLayout()
        mainLayout.setContentsMargins(0, 0, 0, 0)

        innerBox = QVBoxLayout()
        innerBox.setContentsMargins(20, 20, 20, 20)
        innerBox.addWidget(self.newButton, alignment=Qt.AlignLeft)
        innerBox.addWidget(self.table)
        innerBoxWidget = QWidget()
        innerBoxWidget.setLayout(innerBox)
        mainLayout.addWidget(innerBoxWidget)
        self.setLayout(mainLayout)

        # 열 제목 지정
        self.table.setHorizontalHeaderLabels(
            ['그룹명', '상태', '호출', '부관 설정', '삭제']
        )

        self.LoadItem()
        self.newButton.released.connect(self.AddItem)

    def LoadItem(self):
        # 프리셋 데이터 로딩
        for key, data in self.stickerManager.jsonData['Stickers'].items():
            groupName = None
            state = False
            if 'GroupName' in data['options']:  # 그룹명이 정해져 있다면
                groupName = data['options']['GroupName']  # 정해진 이름 부여
            if key == self.stickerManager.presetKey:  # 실행해야 할 스티커라면
                state = True  # 업무중으로 변환

            self.rowCount += 1
            self.table.setRowCount(self.rowCount)

            # 프리셋 생성
            preset = PresetItem(self, groupName, state, gKey=key)
            self.presetItems.append(preset)

            # 표에 초기 데이터 할당
            idx = self.rowCount - 1
            self.table.setItem(idx, 0, preset.groupNameItem)
            self.table.setItem(idx, 1, preset.stateItem)
            item = self.table.item(idx, 1)
            item.setFlags(item.flags() ^ Qt.ItemFlag.ItemIsEditable)
            self.table.setCellWidget(idx, 2, preset.callButton)
            self.table.setCellWidget(idx, 3, preset.manageButton)
            self.table.setCellWidget(idx, 4, preset.deleteButton)

            # groupUis에 데이터 추가
            self.stickerManager.groupUis[key] = None

    # "새 그룹 추가" 버튼 클릭 시 작동
    def AddItem(self, groupName=None, gKey=None, state=False):
        self.rowCount += 1
        self.table.setRowCount(self.rowCount)

        # 프리셋 이름이 따로 정해지지 않았으면 번호로 지정
        if not groupName:
            groupName = "프리셋 " + str(self.rowCount)

        # 그룹 키가 따로 정해지지 않았으면 적당한 번호를 가져옴
        if not gKey:
            gKey = self.stickerManager.findProperGroupKey()

        # 프리셋 생성
        preset = PresetItem(self, groupName, state, gKey=gKey)
        self.presetItems.append(preset)

        # 표에 초기 데이터 할당
        idx = self.rowCount - 1
        self.table.setItem(idx, 0, preset.groupNameItem)
        self.table.setItem(idx, 1, preset.stateItem)
        item = self.table.item(idx, 1)
        item.setFlags(item.flags() ^ Qt.ItemFlag.ItemIsEditable)
        self.table.setCellWidget(idx, 2, preset.callButton)
        self.table.setCellWidget(idx, 3, preset.manageButton)
        self.table.setCellWidget(idx, 4, preset.deleteButton)

        # groupUis에 데이터 추가
        self.stickerManager.groupUis[gKey] = None

        # 새로운 프리셋이면 jsonData에 추가
        if gKey not in self.stickerManager.jsonData['Stickers']:
            newData = {
                gKey: {
                    'options': {
                        "GroupName": groupName,
                        "AlwaysOnTop": False,  # 항상 위에
                    },
                    'characters': {}
                }
            }
            self.stickerManager.stickerSave(newData)

        self.stickerManager.thereIsSomethingToSave()

    # "불러오기" 버튼 클릭 시 작동
    def changeState(self):
        currentRow = self.table.currentRow()
        for preset in self.presetItems:
            if preset.state is True:
                preset.changeState()

        self.presetItems[currentRow].changeState()

    # "삭제" 버튼 클릭 시 작동
    def DeleteItem(self):
        currentRow = self.table.currentRow()  # 선택한 행
        groupKey = self.presetItems[currentRow].groupKey  # 선택한 행의 그룹 키 번호
        self.table.removeRow(currentRow)  # 표에서 제거
        self.rowCount -= 1
        self.stickerManager.deleteGroupUi(groupKey)  # GroupUI 딕셔너리에서 삭제
        del self.presetItems[currentRow]  # presetItems 리스트에서 삭제
        del self.stickerManager.jsonData['Stickers'][groupKey]  # jsonData에서 삭제

        self.stickerManager.thereIsSomethingToSave()


class PresetItem:
    groupName = ""
    groupKey = None
    state = False
    stateString = ""
    callButton = None
    manageButton = None
    deleteButton = None
    parent = None

    groupNameItem = None
    stateItem = None
    stateChangeEvent = pyqtSignal()

    def __init__(self, p, _groupName, _state, gKey):
        self.parent = p
        self.groupName = _groupName
        self.groupKey = gKey
        self.state = _state
        if _state:
            self.stateString = "업무 중"
            self.callButton = QPushButton("업무 해제")
        else:
            self.stateString = ""
            self.callButton = QPushButton("불러오기")
        self.manageButton = QPushButton("그룹 설정")
        self.deleteButton = QPushButton("그룹 해체")
        self.groupNameItem = QTableWidgetItem(self.groupName)
        self.stateItem = QTableWidgetItem(self.stateString)

        # 로딩 때 스티커 안 켜졌을때
        if self.state and self.parent.stickerManager.currentSticker is None:
            self.openSticker()

        # 이벤트 설정
        self.callButton.released.connect(self.callButtonHandler)
        self.manageButton.released.connect(self.openGroupUi)
        self.deleteButton.released.connect(self.parent.DeleteItem)

    def openSticker(self):
        data = self.parent.stickerManager.jsonData['Stickers'][self.groupKey]
        key = self.groupKey
        self.parent.stickerManager.loadSticker(data, key)

    def callButtonHandler(self):
        if self.state:  # 업무 해제 버튼일 경우 혼자 꺼짐
            self.changeState()
        else:  # 불러오기 버튼일 경우 켜져있는 다른 프리셋이 꺼지고 이게 켜짐
            self.parent.changeState()

    def changeState(self):
        if self.state:  # 끄기
            self.state = False
            self.stateString = ""
            self.stateItem.setText(self.stateString)
            self.callButton.setText("불러오기")
            self.parent.stickerManager.currentSticker.groupQuit()  # 스티커 종료
            self.parent.stickerManager.currentSticker = None  # 현재 스티커 = None
            self.parent.stickerManager.presetKey = None  # 현재 그룹 키 = None

        else:  # 켜기
            self.state = True
            self.stateString = "업무 중"
            self.stateItem.setText(self.stateString)
            self.callButton.setText("업무 해제")
            self.openSticker()  # 스티커 실행

    def openGroupUi(self):
        self.parent.stickerManager.openGroupUi(groupKey=self.groupKey)


# 크기 조절, 회전을 맡는 UI인데 개편작업으로 삭제
# class ScaleWindow(QMainWindow, scaleWindowUi):
#     size = 1
#     rotate = 0
#
#     def __init__(self):
#         super().__init__()
#         self.setWindowIcon(QIcon(iconPath))
#         self.setWindowTitle("부관 크기 및 회전 설정")
#         self.setFixedSize(432, 174)
#         self.defaultButton.released.connect()
#         self.sizeSlider.valueChanged.connect()
#         self.rotateSlider.valueChanged.connect()
#
#     def sizeChange(self):
#         self.size = self.sizeSlider.value()
#         self.sizeValue.setText("× %.2f" % self.size)
#
#     def rotateChange(self):
#         self.rotate = self.rotateSlider.value()
#         self.rotateValue.setText(str("%.1f °" % self.rotate)


if __name__ == "__main__":
    # QApplication : 프로그램을 실행시켜주는 클래스
    app = QApplication(sys.argv)

    manage = StickerManager()

    # 프로그램을 이벤트루프로 진입시키는(프로그램을 작동시키는) 코드
    app.exec()
