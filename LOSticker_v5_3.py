import os, sys, random, pickle, psutil
from PyQt5.QtWidgets import QMainWindow, QSystemTrayIcon, QAction, QMenu, QApplication
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtGui import QIcon
from pygame import mixer
from ManageWindow import ManageWindow
from Sticker3 import Sticker, SettingWindow
from PresetGroup import PresetManager, GroupManager

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
iconPath = os.path.abspath("./lise.ico")

os.chdir(currentDir)


class SaveTimer(QThread):
    isSaved = True
    saveSignal = pyqtSignal()
    manager = None

    def __init__(self, _manager):
        super().__init__()
        self.manager = _manager

    def run(self):
        mem = psutil.virtual_memory()
        while True:
            # 매 초마다 브금 꺼졌는지 확인
            self.sleep(1)
            if self.manager.bgmChannel:
                if not self.manager.bgmChannel.get_busy():
                    self.manager.bgmPlay(self.manager.nextBgmIndex)

            # 1초마다 세이브 확인
            if self.isSaved is False:
                self.saveSignal.emit()
                self.isSaved = True


class StickerManager(QMainWindow):
    # 현재 켜져 있는 부관
    currentSticker = None

    # 로딩 가능한 부관 전체 및 읽기/쓰기용 딕셔너리
    # 현재는 pickle을 쓰지만 이전에는 json파일을 썼어서 변수명이 이럼
    jsonData = {
        'BGM': {
            'BGMFiles': [],
            'BGMVolume': 70
        },
        'Stickers': {}
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
        group_action = QAction("현재 그룹 열기", self)
        preset_action = QAction("프리셋 열기", self)
        hide_action = QAction("숨기기", self)
        call_action = QAction("숨김 해제", self)
        quit_action = QAction("종료", self)
        manage_action.triggered.connect(self.openManageUi)
        group_action.triggered.connect(self.openGroupUi)
        preset_action.triggered.connect(self.openPresetUi)
        hide_action.triggered.connect(self.hideGroup)
        call_action.triggered.connect(self.callGroup)
        quit_action.triggered.connect(self.programQuit)
        tray_menu = QMenu()
        tray_menu.addAction(manage_action)
        tray_menu.addAction(group_action)
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

        # 프리셋UI 실행시켜놓기. 얘는 스티커 창 다 꺼져도 프로그램은 안 꺼지고 백그라운드 실행되도록 남아있어야 함
        if not self.presetUi:
            self.presetUi = PresetManager(self)

    def readDataFile(self):
        try:
            # with open("./data.LOSJ", "r", encoding="UTF-8") as jsonFile:
            with open("./data.LOSJ", "rb") as pickleFile:
                # tempJsonData = json.load(jsonFile)
                tempData = pickle.load(pickleFile)

                # 브금 설정
                bgmData = tempData.get('BGM')
                if bgmData:
                    self.bgmFile = bgmData.get('BGMFiles', [])
                    self.jsonData['BGM']['BGMFiles'] = self.bgmFile
                    self.bgmVolume = bgmData.get('BGMVolume', 50)
                    self.jsonData['BGM']['BGMVolume'] = self.bgmVolume

                    # 브금 실행
                    self.bgmPlay()

                # 키 에러를 일으키지 않도록 모든 키의 접근은 키의 존재를 확인한 후 진행
                # 실행할 프리셋 번호 확인
                self.presetKey = None
                if 'PresetKey' in tempData:
                    if 'Stickers' in tempData:
                        if tempData['PresetKey'] in tempData['Stickers']:  # 실행할 프리셋이 실재하는지
                            self.presetKey = tempData.get('PresetKey', None)

                        # 스티커 정보
                        stickerData = tempData.get('Stickers', {})
                        for key, data in stickerData.items():
                            # 딕셔너리에 저장
                            # 나머지 데이터 검증은 Sticker2에서 진행
                            self.jsonData['Stickers'][key] = data

                            # 실행해야 할 프리셋과 키가 같으면 스티커 생성
                            if self.presetKey == key:
                                self.loadSticker(data=data, key=key)

                self.jsonData['PresetKey'] = self.presetKey

        except Exception as e:
            # 기본 데이터로 초기화
            self.jsonData = {
                "PresetKey": None,
                "BGM": {
                    'BGMFiles': [],
                    'BGMVolume': 70
                },
                "Stickers": {}
            }

        finally:
            # 걸러진 데이터로 다시 저장
            self.thereIsSomethingToSave()

            # 캐릭터가 없으면 프리셋 창 오픈
            if not self.currentSticker:
                self.openPresetUi()


    def loadSticker(self, data, key):
        if self.currentSticker:
            self.currentSticker.resetSticker(data, key)
        else:
            self.currentSticker = Sticker(self, data=data, key=key)
        self.presetKey = key
        self.currentSticker.showMaximized()
        self.jsonData['PresetKey'] = key
        self.thereIsSomethingToSave()

    def writeDataFile(self):
        with open("./data.LOSJ", "wb") as pickleFile:
            pickle.dump(self.jsonData, pickleFile)
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

    def openGroupUi(self, groupKey=None):
        # 트레이메뉴의 "현재 그룹 열기"는 groupKey가 False로 전달됨
        # 이 경우 self.presetKey에 해당하는 그룹이 열리는데, 설정되어 있지 않으면면 UI 열지 않음
        if not groupKey and not self.presetKey:
            return

        if not groupKey:
            groupKey = self.presetKey

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
        else:
            self.presetUi.show()


    def openSettingUi(self, groupKey, chaKey):
        if self.settingUi is None:
            # 전송할 데이터 준비
            data = self.jsonData['Stickers'][groupKey]['characters'][chaKey]
            chaFile = data['CharacterImage']  # 이미지 파일 경로
            loginVoiceFile = data['LoginVoiceFiles']  # 로그인 보이스 경로 리스트
            idleVoiceFile = data['IdleVoiceFiles']  # 터치 보이스 경로 리스트
            specialVoiceFile = data['SpecialVoiceFiles']  # 특수터치 보이스 경로 리스트
            voiceVolume = data['VoiceVolume']  # 보이스 볼륨값

            self.settingUi = SettingWindow()
            self.settingUi.setParent(self)
            self.settingUi.setSetting(chaFile, loginVoiceFile, idleVoiceFile, specialVoiceFile, voiceVolume)
            r = self.settingUi.showModal()

            if r:
                # 캐릭터 파일
                if os.path.exists(self.settingUi.chaFile):
                    # if not self.chaFile:
                    #     # 스티커 생성
                    #     self.assignEvent.emit(self.key, self)

                    chaFile = self.settingUi.chaFile

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
                data['VoiceVolume'] = voiceVolume
                self.jsonData['Stickers'][groupKey]['characters'][chaKey] = data
                print(f"groupKey = {groupKey}, presetKey = {self.presetKey}")

                # 현재 실행되어 있는 스티커일경우
                if groupKey == self.presetKey:
                    self.currentSticker.stickers['characters'][chaKey] = data
                    self.currentSticker.setCharacter(data, chaKey)  # 스티커에 할당

                self.thereIsSomethingToSave()  # 저장

        self.settingUi = None
    
    def closeEvent(self, event):
        print("메인윈도우 종료")
    
    def __del__(self):
        print("메인윈도우 삭제")


if __name__ == "__main__":
    # QApplication : 프로그램을 실행시켜주는 클래스
    app = QApplication(sys.argv)

    manage = StickerManager()

    # 프로그램을 이벤트루프로 진입시키는(프로그램을 작동시키는) 코드
    app.exec()
