import os, sys, json, random, time, subprocess
from PyQt5.QtWidgets import QMainWindow, QSystemTrayIcon, QAction, QMenu, QLabel, QWidget, QDialog, QFileDialog,\
    QApplication, QTableWidget, QPushButton, QTableWidgetItem, QVBoxLayout, QHBoxLayout
from PyQt5 import uic
from PyQt5.QtCore import QThread, pyqtSignal, QSize, Qt, pyqtSlot
from PyQt5.QtGui import QIcon, QCursor, QIntValidator, QMovie
from PIL import Image, ImageQt
from pygame import mixer
from ManageWindow import ManageWindow
from Sticker import Sticker

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
# print(os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"])
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
    stickerDict = {}

    # 로딩 가능한 부관 전체 및 읽기/쓰기용 딕셔너리
    jsonData = {
        'BGM': {
            'BGMFiles': [],
            'BGMVolume': 70
        },
        'Stickers': {}
    }

    '''
    파일 형태
    jsonData = {
        'BGM' : {
            'BGMFiles': [...],
            'BGMVolume': 70
        }
        'Stickers' : {
            '0' : {
                "Position": [-19, 80],
                "AlwaysOnTop": true,
                "CharacterImage": "C:/Users/CheeseCake/PycharmProjects/pythonProject/LastOrigin/Sticker/character/BR_Andvari_0_O_S.webp",
                "LoginVoiceFiles": [
                    "C:/Users/CheeseCake/PycharmProjects/pythonProject/LastOrigin/Sticker/voice/BR_Andvari_Login.mp3"
                ],
                "IdleVoiceFiles": [
                    "C:/Users/CheeseCake/PycharmProjects/pythonProject/LastOrigin/Sticker/voice/BR_Andvari_SPIdle_02_01.mp3"
                ],
                "CharacterSize": 800,
                "SizeRestrict": false,
                "VoiceVolume": 50
            }
            '1' : {...}
        }
    }
    '''

    manageUi = None # ManageWindow 객체
    groupUis = [] # 다중부관 그룹 관리 객체. 각 프리셋 당 하나씩 관리
    presetUi = None # 프리셋 관리 객체
    bgmFile = [] # 브금 파일명 리스트
    bgmSound = None # Sound 객체. 음원 재생용
    bgmChannel = None # Channel 객체
    nextBgmIndex = 0 # 순차재생 다음 인덱스
    bgmVolume = 50 # 브금 볼륨
    tray_icon = None # QSystemTrayIcon 객체
    saveTimer = None # SaveTimer 객체. 주기적으로 정보를 자동저장함

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
        hide_action.triggered.connect(self.hideStickers)
        call_action.triggered.connect(self.callSticker)
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

        # 다중부관인 경우 랜덤 보이스 실행
        if len(self.stickerDict) > 0:
            key = list(self.stickerDict.keys())[random.randrange(0, len(self.stickerDict))]
            self.stickerDict[key].loginVoicePlay(-1)

    def readDataFile(self):
        try:
            with open("./data.LOSJ", "r") as jsonFile:
                tempJsonData = json.load(jsonFile)

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
                    if not self.bgmSound:
                        self.bgmPlay()

                if 'Stickers' in tempJsonData:
                    stickerData = tempJsonData['Stickers']
                    for key in stickerData:
                        if key not in self.stickerDict:
                            data = stickerData[key]
                            if os.path.exists(data['CharacterImage']):
                                sticker = Sticker(self, data, key)
                                self.stickerDict[key] = sticker
                                if key not in self.jsonData['Stickers']:
                                    self.jsonData['Stickers'][key] = data
                                sticker.show()
                self.writeDataFile()

        except Exception as e:
            print("read Exception: " + str(e))
        finally:
            if not self.stickerDict:
                self.openManageUi()

    def writeDataFile(self):
        with open("./data.LOSJ", "w") as jsonFile:
            json.dump(self.jsonData, jsonFile, indent=2)
            print("save")

    # 저장할 필요가 있을 때만 자동저장을 호출함
    def thereIsSomethingToSave(self):
        if self.saveTimer:
            self.saveTimer.isSaved = False

    # 숨긴 스티커 볼러오기
    def callSticker(self):
        for key in self.stickerDict:
            self.stickerDict[key].show()

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
            print("Voice Exception: " + str(e))

    # 각 스티커에 부여된 키 중 비어있는 키를 찾기
    def findProperKey(self):
        key = 0
        while str(key) in self.stickerDict:
            key += 1
        return str(key)

    # 특정 스티커 숨기기
    def stickerHide(self, key):
        if key in self.stickerDict:
            self.stickerDict[key].hide()

    # 스티커 정보 저장
    def stickerSave(self, data):
        self.jsonData['Stickers'].update(data)
        self.thereIsSomethingToSave()

    def stickerAssign(self, key, sticker):
        # 최초 생성 시
        if key and sticker:
            if key not in self.stickerDict:
                self.stickerDict[key] = sticker

    def stickerAdd(self):
        key = self.findProperKey()
        sticker = Sticker(self, None, key)
        sticker.show()

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

    # 모든 스티커 숨기기
    def hideStickers(self):
        for key in self.stickerDict:
            sticker = self.stickerDict[key]
            if sticker.secondWindow:
                sticker.secondWindow.close()
            sticker.hide()

    def managerUiQuit(self):
        self.manageUi = None

    def programQuit(self):
        for key in self.stickerDict:
            self.stickerDict[key].close()
        if self.manageUi:
            self.manageUi.close()
        sys.exit()

    def openManageUi(self):
        if not self.manageUi:
            self.manageUi = ManageWindow()
            self.manageUi.addEvent.connect(self.stickerAdd)
            self.manageUi.loadEvent.connect(self.callSticker)
            self.manageUi.quitEvent.connect(self.managerUiQuit)
            self.manageUi.endEvent.connect(self.programQuit)
            self.manageUi.bgmChangeEvent.connect(self.bgmChanged)
            self.manageUi.bgmVolumeEvent.connect(self.bgmVolumeChanged)
            self.manageUi.volumeSlider.setValue(self.bgmVolume)

        self.manageUi.show()

    def openGroupUi(self, idx, subName=""):
        if self.groupUis[idx] is None:
            self.groupUis[idx] = GroupManager(subName=subName)

        self.groupUis[idx].show()
        print(self.groupUis)

    def closeGroupUi(self, ui):
        if ui in self.groupUis:
            idx = self.groupUis.index(ui)
            self.groupUis[idx] = None
            print(self.groupUis)

    def deleteGroupUi(self, ui):
        if ui in self.groupUis:
            idx = self.groupUis.index(ui)
            del self.groupUis[idx]
            print(self.groupUis)

    def openPresetUi(self):
        if not self.presetUi:
            self.presetUi = PresetManager()

        self.presetUi.show()

class GroupManager(QWidget):
    rowCount = 0
    table = None
    groupItems = []

    def __init__(self, _rowCount=0, subName="", rowCount=5):
        super().__init__()
        self.rowCount = _rowCount
        self.setWindowTitle(subName + " 그룹 관리")
        self.InitUi()

    def InitUi(self):
        # 위젯 추가
        self.newButton = QPushButton("새 부관 추가")  # 그룹 추가 버튼 위젯
        self.table = QTableWidget(self)  # 테이블 위젯

        # 위젯 설정
        # self.newButton.setMinimumHeight(31)
        self.newButton.setStyleSheet("padding: 10px;")
        self.table.setMinimumSize(600, 200)
        self.table.setColumnCount(5)
        self.table.setRowCount(self.rowCount)

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
            ['부관 이름', '상태', '숨기기', '부관 설정', '업무 해제']
        )

        self.newButton.released.connect(self.AddItem)

    def AddItem(self):
        self.rowCount += 1
        self.table.setRowCount(self.rowCount)

        # 프리셋 생성
        group = GroupItem(self, "부관 " + str(self.rowCount), True)
        self.groupItems.append(group)

        # 표에 초기 데이터 할당
        idx = self.rowCount - 1
        self.table.setItem(idx, 0, group.chaNameItem)
        self.table.setItem(idx, 1, group.stateItem)
        self.table.setCellWidget(idx, 2, group.hideButton)
        self.table.setCellWidget(idx, 3, group.manageButton)
        self.table.setCellWidget(idx, 4, group.deleteButton)

        # groupUis에 데이터 추가
        # manage.groupUis.append(None)

    def DeleteItem(self):
        currentRow = self.table.currentRow()
        print(currentRow)
        self.table.removeRow(currentRow)
        self.rowCount -= 1
        del self.groupItems[currentRow]
        # del manage.groupUis[currentRow]

    def closeEvent(self, event):
        manage.closeGroupUi(self)

class GroupItem:
    chaName = ""
    state = False
    stateString = ""
    hideButton = None
    manageButton = None
    deleteButton = None
    parent = None

    chaNameItem = None
    stateItem = None

    def __init__(self, p, _chaName, _state):
        self.parent = p
        self.chaName = _chaName
        self.state = _state
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
        print("change")
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

    def findMyIndex(self):
        if self in self.parent.groupItems:
            idx = self.parent.groupItems.index(self)
            return idx

    def openSettingUi(self):
        pass

class PresetManager(QWidget):
    rowCount = 0
    table = None
    presetItems = []

    def __init__(self, _rowCount=0):
        super().__init__()
        self.rowCount = _rowCount
        self.setWindowTitle("전체 부관")
        self.InitUi()

    def InitUi(self):
        # 위젯 추가
        self.newButton = QPushButton("새 그룹 추가") # 그룹 추가 버튼 위젯
        self.table = QTableWidget(self) # 테이블 위젯

        # 위젯 설정
        # self.newButton.setMinimumHeight(31)
        self.newButton.setStyleSheet("padding: 10px;")
        self.table.setMinimumSize(600, 200)
        self.table.setColumnCount(5)
        self.table.setRowCount(self.rowCount)

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

        self.newButton.released.connect(self.AddItem)

    def AddItem(self):
        self.rowCount += 1
        self.table.setRowCount(self.rowCount)

        # 프리셋 생성
        preset = PresetItem(self, "프리셋 " + str(self.rowCount), True)
        self.presetItems.append(preset)

        # 표에 초기 데이터 할당
        idx = self.rowCount - 1
        self.table.setItem(idx, 0, preset.groupNameItem)
        self.table.setItem(idx, 1, preset.stateItem)
        self.table.setCellWidget(idx, 2, preset.callButton)
        self.table.setCellWidget(idx, 3, preset.manageButton)
        self.table.setCellWidget(idx, 4, preset.deleteButton)

        # groupUis에 데이터 추가
        manage.groupUis.append(None)

    def DeleteItem(self):
        currentRow = self.table.currentRow()
        print(currentRow)
        self.table.removeRow(currentRow)
        self.rowCount -= 1
        del self.presetItems[currentRow]
        del manage.groupUis[currentRow]

class PresetItem:
    groupName = ""
    state = False
    stateString = ""
    callButton = None
    manageButton = None
    deleteButton = None
    parent = None

    groupNameItem = None
    stateItem = None

    def __init__(self, p, _groupName, _state):
        self.parent = p
        self.groupName = _groupName
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

        # 이벤트 설정
        self.callButton.released.connect(self.changeState)
        self.manageButton.released.connect(self.openGroupUi)
        self.deleteButton.released.connect(self.parent.DeleteItem)

    def changeState(self):
        print("change")
        if self.state:
            self.state = False
            self.stateString = ""
            self.stateItem.setText(self.stateString)
            self.callButton.setText("불러오기")
        else:
            self.state = True
            self.stateString = "업무 중"
            self.stateItem.setText(self.stateString)
            self.callButton.setText("업무 해제")

    def findMyIndex(self):
        if self in self.parent.presetItems:
            idx = self.parent.presetItems.index(self)
            return idx

    def openGroupUi(self):
        idx = self.findMyIndex()
        print(idx)
        manage.openGroupUi(idx, subName=self.groupName)


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