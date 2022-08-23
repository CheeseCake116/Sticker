import os, sys, json, random, time, subprocess
from PyQt5.QtWidgets import QMainWindow, QSystemTrayIcon, QAction, QMenu, QLabel, QWidget, QDialog, QFileDialog, QApplication, QTableWidget, QPushButton, QTableWidgetItem
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
            for i in range(10):
                time.sleep(0.1)
                if self.manager.bgmChannel:
                    if not self.manager.bgmChannel.get_busy():
                        self.manager.bgmPlay(self.manager.nextBgmIndex)

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
        manage_action = QAction("관리창 열기", self)
        hide_action = QAction("숨기기", self)
        call_action = QAction("숨김 해제", self)
        quit_action = QAction("종료", self)
        manage_action.triggered.connect(self.openManageUi)
        hide_action.triggered.connect(self.hideStickers)
        call_action.triggered.connect(self.callSticker)
        quit_action.triggered.connect(self.programQuit)
        tray_menu = QMenu()
        tray_menu.addAction(manage_action)
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

class StickerTableWidget(QWidget):
    """표를 보여주는 위젯"""
    def __init__(self, rowCount=0):
        super().__init__()
        self.setWindowTitle("전체 부관")

        table = QTableWidget(self)
        table.resize(300, 200)
        # 표의 크기를 지정
        table.setColumnCount(5)
        table.setRowCount(rowCount)
        # 열 제목 지정
        table.setHorizontalHeaderLabels(
            ['이름', '상태', '위젯 설정', '숨기기', '업무 종료']
        )
        for i in range(3):
            btn = QPushButton("삭제")
            table.setCellWidget(i,2, btn)

        # 셀 내용 채우기
        table.setItem(0, 0, QTableWidgetItem('A'))
        table.setItem(1, 0, QTableWidgetItem('B'))
        table.setItem(2, 0, QTableWidgetItem('C'))
        table.setItem(0, 1, QTableWidgetItem('1'))
        table.setItem(1, 1, QTableWidgetItem('2'))
        table.setItem(2, 1, QTableWidgetItem('3'))






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