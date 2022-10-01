from PyQt5.QtWidgets import QWidget, QTableWidget, QPushButton, QTableWidgetItem, QVBoxLayout, QHBoxLayout, QCheckBox, \
    QHeaderView
from PyQt5.QtCore import pyqtSignal, Qt


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
        self.groupItems = []
        self.setWindowTitle(subName + " 그룹 관리")
        self.InitUi()

    def InitUi(self):
        # 항상 위에 고정 체크박스
        self.AOTCheckBox = QCheckBox("항상 위에 고정")

        # Always on Top 설정
        self.AOTCheckBox.setChecked(self.stickerManager.jsonData['Stickers'][self.groupKey]['options']['AlwaysOnTop'])
        self.AOTCheckBox.stateChanged.connect(self.setAlwaysOnTop)

        self.newButton = QPushButton("새 부관 추가")  # 그룹 추가 버튼 위젯
        self.table = QTableWidget(self)  # 테이블 위젯
        self.table.cellChanged.connect(self.cellChangeEvent)

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

            group = GroupItem(self, chaName, data["Visible"], ckey=chaKey)
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
                "Position": None,  # 위치
                "Depth": idx,  # 놓인 순서
                "Visible": True,
                "CharacterImage": "",
                "LoginVoiceFiles": [],
                "IdleVoiceFiles": [],
                "SpecialVoiceFiles": [],
                "Flip": False,
                "Size": 100,
                "Rotation": 0,
                "VoiceVolume": 50
            }
        }

        self.stickerManager.jsonData['Stickers'][self.groupKey]["characters"].update(data)

        self.stickerManager.thereIsSomethingToSave()

    def DeleteItem(self):
        currentRow = self.table.currentRow()  # 표에서 선택한 행
        chaKey = self.groupItems[currentRow].chaKey  # 해당 그룹의 캐릭터 키 번호

        self.table.removeRow(currentRow)
        self.rowCount -= 1
        del self.groupItems[currentRow]  # 표에서 제거
        del self.stickerManager.jsonData['Stickers'][self.groupKey]['characters'][chaKey]  # jsonData 수정

        # 실행중인 스티커라면 스티커 객체에 삭제해달라고 요청
        if self.groupKey == self.stickerManager.presetKey:
            self.stickerManager.currentSticker.characterQuit(chaKey)

        self.stickerManager.thereIsSomethingToSave()

    # 이름 변경 이벤트
    # 이름을 직접 변경할 때 뿐만 아니라 행이 생성될때도 작동하니 조심!
    def cellChangeEvent(self, row, col):
        # 다른 열에서 발생한 이벤트일 경우 탈출
        if col != 0:
            return

        # 행이 추가되면서 발동된 이벤트인경우 탈출
        # groupItem에 캐릭터 키가 할당되어 있는지
        if row < len(self.groupItems):
            chaKey = self.groupItems[row].chaKey
            # 해당 캐릭터 정보가 jsonData에 존재하는지
            chaDict = self.stickerManager.jsonData['Stickers'][self.groupKey]['characters']
            if not (chaKey in chaDict and chaDict[chaKey]):
                return

            data = self.table.item(row, col)
            chaName = data.text()
            self.stickerManager.jsonData['Stickers'][self.groupKey]['characters'][chaKey]["CharacterName"] = chaName
            self.stickerManager.thereIsSomethingToSave()

    # 그룹UI가 켜진 상태에서 해당 그룹이 부관으로 불러와지거나 내보내졌을 때, 부관의 상태를 변경하기 위한 함수
    def setReady(self, state):
        print("- Group", self.groupKey, "setReady ", state)
        for item in self.groupItems:
            item.setReady(state)

    def findRow(self, chaKey):
        row = None
        for idx, item in enumerate(self.groupItems):
            if item.chaKey == chaKey:
                row = idx
                break
        return row

    def hideSticker(self, chaKey):
        row = self.findRow(chaKey)

        if row is not None:
            self.groupItems[row].hideSticker()

    def callSticker(self, chaKey):
        row = self.findRow(chaKey)

        if row is not None:
            self.groupItems[row].callSticker()

    def setAlwaysOnTop(self):
        aot = self.AOTCheckBox.isChecked()
        self.stickerManager.jsonData['Stickers'][self.groupKey]['options']['AlwaysOnTop'] = aot
        self.stickerManager.thereIsSomethingToSave()

        # 해당 스티커가 켜져있는경우 세팅해주기
        if self.groupKey == self.stickerManager.presetKey:
            sticker = self.stickerManager.currentSticker
            sticker.AlwaysOnTop = aot
            sticker.setupWindow()

    def __del__(self):
        print("그룹매니저 삭제")


class GroupItem:
    chaName = ""
    groupKey = '-1'
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
        self.groupKey = p.groupKey
        self.chaName = _chaName
        self.state = _state
        self.chaKey = ckey
        if _state:
            if self.groupKey == self.parent.stickerManager.presetKey:
                self.stateString = "업무 중"
            else:
                self.stateString = "업무 대기중"
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

    # 그룹 UI가 켜진 상태에서 해당 부관 그룹이 호출되었을 때 "업무 대기중"에서 "업무 중"으로 바꾸기 위한 함수
    def setReady(self, state):
        # "숨김"이 아니면
        if self.state:
            # 부관이 켜지면
            if state:
                self.stateString = "업무 중"
            # 부관이 꺼지면
            else:
                self.stateString = "업무 대기중"

        self.stateItem.setText(self.stateString)

    def changeState(self):
        if self.state:
            self.hideSticker()
        else:
            self.callSticker()

    def hideSticker(self):
        self.state = False
        self.stateString = "숨김"
        self.stateItem.setText(self.stateString)
        self.hideButton.setText("숨김 해제")

        if self.groupKey == self.parent.stickerManager.presetKey:
            sticker = self.parent.stickerManager.currentSticker
            sticker.labels[self.chaKey].hide()
            sticker.stickers['characters'][self.chaKey]["Visible"] = False
            sticker.writeDataFile()

    def callSticker(self):
        self.state = True
        self.stateString = "업무 중"
        self.stateItem.setText(self.stateString)
        self.hideButton.setText("숨기기")

        if self.groupKey == self.parent.stickerManager.presetKey:
            sticker = self.parent.stickerManager.currentSticker
            sticker.labels[self.chaKey].show()
            sticker.stickers['characters'][self.chaKey]["Visible"] = True
            sticker.writeDataFile()

    def openSettingUi(self):
        self.parent.stickerManager.openSettingUi(self.groupKey, self.chaKey)

    def __del__(self):
        print(f"그룹아이템 {self.chaKey} 삭제")


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
        # 위젯 추가
        self.newButton = QPushButton("프리셋 추가")  # 그룹 추가 버튼 위젯
        self.table = QTableWidget(self)  # 테이블 위젯
        self.table.cellChanged.connect(self.cellChangeEvent)

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

    # 그룹명 변경 이벤트
    def cellChangeEvent(self, row, col):
        # 그룹창 켤 때도 발생함
        if col != 0:
            return

        # 행이 추가되면서 발동된 이벤트인경우 탈출
        # presetItems에 그룹 키가 할당되어 있는지
        if row < len(self.presetItems):
            groupKey = self.presetItems[row].groupKey
            # 해당 캐릭터 정보가 jsonData에 존재하는지
            groupDict = self.stickerManager.jsonData['Stickers']
            if not (groupKey in groupDict and groupDict[groupKey]):
                return

            data = self.table.item(row, col)
            groupName = data.text()
            self.stickerManager.jsonData['Stickers'][groupKey]["options"]["GroupName"] = groupName
            self.stickerManager.thereIsSomethingToSave()

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

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def __del__(self):
        print("프리셋매니저 삭제")


class PresetItem:
    groupName = ""
    groupKey = None
    state = False
    stateString = ""
    callButton = None
    manageButton = None
    deleteButton = None
    parent = None
    stickerManager = None

    groupNameItem = None
    stateItem = None
    stateChangeEvent = pyqtSignal()

    def __init__(self, p, _groupName, _state, gKey):
        self.parent = p
        self.groupName = _groupName
        self.groupKey = gKey
        self.state = _state
        self.stickerManager = self.parent.stickerManager
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
        self.callButton.released.connect(self.callButtonHandler)
        self.manageButton.released.connect(self.openGroupUi)
        self.deleteButton.released.connect(self.deleteSticker)
        print(f"프리셋아이템 {self.groupKey} 생성")

    def callButtonHandler(self):
        if self.state:  # 업무 해제 버튼일 경우 혼자 꺼짐
            self.GetGroupOut()
        else:  # 불러오기 버튼일 경우 켜져있는 다른 프리셋이 꺼지고 이게 켜짐
            # 켜진 거 찾아서 끄기
            for preset in self.parent.presetItems:
                if preset.state is True:
                    preset.GetGroupOut()

            # 불러오기 한 거 켜기
            currentRow = self.parent.table.currentRow()
            self.parent.presetItems[currentRow].GetGroupIn()

    # 내보내기
    def GetGroupOut(self):
        self.state = False
        self.stateString = ""
        self.stateItem.setText(self.stateString)
        self.callButton.setText("불러오기")
        print(self.stickerManager.currentSticker.stickers)
        self.stickerManager.currentSticker.groupQuit()  # 스티커 종료
        self.stickerManager.currentSticker = None  # 현재 스티커 = None
        self.stickerManager.presetKey = None  # 현재 그룹 키 = None
        if self.groupKey in self.stickerManager.groupUis and self.stickerManager.groupUis[self.groupKey]:
            self.stickerManager.groupUis[self.groupKey].setReady(False)
        self.stickerManager.thereIsSomethingToSave()

    # 불러오기
    def GetGroupIn(self):
        self.state = True
        self.stateString = "업무 중"
        self.stateItem.setText(self.stateString)
        self.callButton.setText("업무 해제")
        self.stickerManager.presetKey = self.groupKey
        if self.groupKey in self.stickerManager.groupUis and self.stickerManager.groupUis[self.groupKey]:
            self.stickerManager.groupUis[self.groupKey].setReady(True)
        self.openSticker()  # 스티커 실행
        self.stickerManager.thereIsSomethingToSave()

    def openSticker(self):
        data = self.stickerManager.jsonData['Stickers'][self.groupKey]
        key = self.groupKey

        self.stickerManager.loadSticker(data, key)

    def deleteSticker(self):
        self.GetGroupOut()
        self.parent.DeleteItem()

    def openGroupUi(self):
        self.stickerManager.openGroupUi(groupKey=self.groupKey)

    def __del__(self):
        print(f"프리셋아이템 {self.groupKey} 삭제")