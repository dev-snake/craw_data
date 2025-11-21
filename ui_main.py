# Form implementation generated manually for PyQt6
# Based on file: ui/main_window.ui

from PyQt6 import QtCore, QtGui, QtWidgets


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1200, 800)
        self.centralwidget = QtWidgets.QWidget(parent=MainWindow)
        self.centralwidget.setObjectName("centralwidget")

        self.mainLayout = QtWidgets.QHBoxLayout(self.centralwidget)
        self.mainLayout.setObjectName("mainLayout")

        # ============= Sidebar =============
        self.sidebar = QtWidgets.QFrame(parent=self.centralwidget)
        self.sidebar.setMinimumSize(QtCore.QSize(220, 0))
        self.sidebar.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.sidebar.setObjectName("sidebar")

        self.sidebarLayout = QtWidgets.QVBoxLayout(self.sidebar)
        self.sidebarLayout.setObjectName("sidebarLayout")

        self.labelTitle = QtWidgets.QLabel(parent=self.sidebar)
        self.labelTitle.setText("Enterprise Crawler")
        self.sidebarLayout.addWidget(self.labelTitle)

        self.inputURL = QtWidgets.QLineEdit(parent=self.sidebar)
        self.inputURL.setPlaceholderText("Enter URL to crawl...")
        self.sidebarLayout.addWidget(self.inputURL)

        self.btnStart = QtWidgets.QPushButton(parent=self.sidebar)
        self.btnStart.setText("Start Crawling")
        self.sidebarLayout.addWidget(self.btnStart)

        self.btnStop = QtWidgets.QPushButton(parent=self.sidebar)
        self.btnStop.setText("Stop")
        self.sidebarLayout.addWidget(self.btnStop)

        self.btnLoadConfig = QtWidgets.QPushButton(parent=self.sidebar)
        self.btnLoadConfig.setText("Load Config")
        self.sidebarLayout.addWidget(self.btnLoadConfig)

        self.btnSaveConfig = QtWidgets.QPushButton(parent=self.sidebar)
        self.btnSaveConfig.setText("Save Config")
        self.sidebarLayout.addWidget(self.btnSaveConfig)

        self.sidebarSpacer = QtWidgets.QSpacerItem(
            20, 40, QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Expanding
        )
        self.sidebarLayout.addItem(self.sidebarSpacer)

        self.mainLayout.addWidget(self.sidebar)

        # ============= Main Panel =============
        self.mainPanel = QtWidgets.QFrame(parent=self.centralwidget)
        self.mainPanel.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.mainPanel.setObjectName("mainPanel")

        self.mainPanelLayout = QtWidgets.QVBoxLayout(self.mainPanel)
        self.mainPanelLayout.setObjectName("mainPanelLayout")

        # Tabs
        self.tabWidget = QtWidgets.QTabWidget(parent=self.mainPanel)
        self.tabWidget.setObjectName("tabWidget")

        # ---------- Tab: Results ----------
        self.tabResults = QtWidgets.QWidget()
        self.tabResults.setObjectName("tabResults")
        self.resultsLayout = QtWidgets.QVBoxLayout(self.tabResults)

        self.textResult = QtWidgets.QTextEdit(parent=self.tabResults)
        self.textResult.setReadOnly(True)
        self.resultsLayout.addWidget(self.textResult)

        self.tabWidget.addTab(self.tabResults, "Results")

        # ---------- Tab: Logs ----------
        self.tabLogs = QtWidgets.QWidget()
        self.tabLogs.setObjectName("tabLogs")
        self.logLayout = QtWidgets.QVBoxLayout(self.tabLogs)

        self.textLog = QtWidgets.QTextEdit(parent=self.tabLogs)
        self.textLog.setReadOnly(True)
        self.logLayout.addWidget(self.textLog)

        self.tabWidget.addTab(self.tabLogs, "Logs")

        self.mainPanelLayout.addWidget(self.tabWidget)
        self.mainLayout.addWidget(self.mainPanel)

        MainWindow.setCentralWidget(self.centralwidget)

        # Menubar & Statusbar
        self.menubar = QtWidgets.QMenuBar(parent=MainWindow)
        MainWindow.setMenuBar(self.menubar)

        self.statusbar = QtWidgets.QStatusBar(parent=MainWindow)
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    # ----------------------------
    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "Enterprise Web Crawler"))
