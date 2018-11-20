import sys
import pyqtgraph as pg
import numpy as np
import cv2
import os
import glob
import csv

# import the Qt library
try:
    from PyQt4.QtCore import *
    from PyQt4.QtGui import *
    pyqt_version = 4
except:
    from PyQt5.QtCore import *
    from PyQt5.QtGui import *
    from PyQt5.QtWidgets import *
    pyqt_version = 5

# set styles of title and subtitle labels
ROUNDED_STYLESHEET_DARK    = "background-color: rgba(0, 0, 0, 0.3); border-radius: 2px; border: 1px solid rgba(0, 0, 0, 0.5); padding: 2px;"
ROUNDED_STYLESHEET_LIGHT   = "background-color: rgba(255, 255, 255, 1); border-radius: 2px; border: 1px solid rgba(0, 0, 0, 0.2); padding: 2px;"
rounded_stylesheet         = ROUNDED_STYLESHEET_LIGHT

bold_font = QFont()
bold_font.setBold(True)

behaviors = ["J-Turn", "C-Bend", "Swim"]

colors = [(255, 100, 0), (0, 100, 255), (100, 0, 255)]

framerate = 349

class Window(QMainWindow):
    def __init__(self):
        QMainWindow.__init__(self)

        # create main widget
        self.main_widget = QWidget(self)
        self.main_widget.setMinimumSize(QSize(1000, 400))

        # set colors
        self.bg_color = (self.palette().color(self.backgroundRole()).red(), self.palette().color(self.backgroundRole()).green(), self.palette().color(self.backgroundRole()).blue())
        pg.setConfigOption('background', self.bg_color)
        if self.bg_color[0] < 100:
            rounded_stylesheet   = ROUNDED_STYLESHEET_DARK
            pg.setConfigOption('foreground', (150, 150, 150))
        else:
            rounded_stylesheet   = ROUNDED_STYLESHEET_LIGHT
            pg.setConfigOption('foreground', (20, 20, 20))

        # create main layout
        self.main_layout = QVBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Vertical)
        self.main_layout.addWidget(self.splitter)

        # create plot widget
        self.plot_widget = QWidget(self)
        self.plot_layout = QHBoxLayout(self.plot_widget)
        self.plot_layout.setContentsMargins(0, 0, 0, 0)
        self.splitter.addWidget(self.plot_widget)

        self.graph_widget = pg.GraphicsLayoutWidget()
        # self.graph_widget.setMaximumHeight(300)
        self.graph_widget.scene().sigMouseClicked.connect(self.plot_clicked)
        self.graph_widget.scene().sigMouseMoved.connect(self.mouse_moved)
        self.graph_widget.ci.layout.setColumnStretchFactor(0, 2)
        self.graph_widget.ci.layout.setColumnStretchFactor(1, 4)
        self.plot_layout.addWidget(self.graph_widget)

        # create video preview plot
        self.video_viewbox = self.graph_widget.addViewBox(lockAspect=True, name='video_plot', border=None, row=0, col=0, invertY=True)
        self.video_plot = pg.ImageItem()
        self.video_viewbox.addItem(self.video_plot)

        # create tail trace plot
        self.tail_plot = self.graph_widget.addPlot(name='tail_plot', row=0, col=1)
        self.tail_plot.setLabel('left', "Tail Angle")
        self.tail_plot.setLabel('bottom', "Time (s)")
        self.tail_plot.showButtons()
        self.tail_plot.setMouseEnabled(x=True,y=False)

        # create bottom widget
        self.bottom_widget = QWidget()
        self.bottom_layout = QVBoxLayout(self.bottom_widget)
        self.splitter.addWidget(self.bottom_widget)

        # create videos list
        self.tail_angles_list = QListWidget(self)
        self.tail_angles_list.setStyleSheet(rounded_stylesheet)
        self.tail_angles_list.itemSelectionChanged.connect(self.item_selected)
        self.tail_angles_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.tail_angles_list.installEventFilter(self)
        self.bottom_layout.addWidget(self.tail_angles_list)

        # create shortcut to delete tail angles
        self.delete_tail_angles_shortcut = QShortcut(QKeySequence('Delete'), self.tail_angles_list)
        self.delete_tail_angles_shortcut.activated.connect(self.delete_selected_tail_angles)

        # create button widget
        self.button_widget = QWidget()
        self.button_layout = QHBoxLayout(self.button_widget)
        self.bottom_layout.addWidget(self.button_widget)

        # create button to add tail angles
        self.add_tail_angles_button = QPushButton('Add Tail Angles...')
        self.add_tail_angles_button.setStyleSheet('font-weight: bold;')
        self.add_tail_angles_button.setIcon(QIcon("icons/add_tail_angles_icon.png"))
        self.add_tail_angles_button.setIconSize(QSize(16,16))
        self.add_tail_angles_button.clicked.connect(self.import_tail_angles)
        self.button_layout.addWidget(self.add_tail_angles_button)

        # create button to add tail angles from a folder
        self.add_tail_angles_from_folder_button = QPushButton('Add Tail Angles from Folder...')
        self.add_tail_angles_from_folder_button.setStyleSheet('font-weight: bold;')
        self.add_tail_angles_from_folder_button.setIcon(QIcon("icons/add_tail_angles_icon.png"))
        self.add_tail_angles_from_folder_button.setIconSize(QSize(16,16))
        self.add_tail_angles_from_folder_button.clicked.connect(self.import_tail_angles_from_folder)
        self.button_layout.addWidget(self.add_tail_angles_from_folder_button)

        # create button to remove tail angles
        self.remove_tail_angles_button = QPushButton('Remove')
        self.remove_tail_angles_button.setIcon(QIcon("icons/remove_tail_angles_icon.png"))
        self.remove_tail_angles_button.setIconSize(QSize(16,16))
        self.remove_tail_angles_button.setDisabled(True)
        self.remove_tail_angles_button.clicked.connect(self.delete_selected_tail_angles)
        self.button_layout.addWidget(self.remove_tail_angles_button)

        self.button_layout.addStretch()

        # create button to add a video
        self.add_video_button = QPushButton('Add Video...')
        self.add_video_button.setIcon(QIcon("icons/add_video_icon.png"))
        self.add_video_button.setIconSize(QSize(16,16))
        self.add_video_button.setDisabled(True)
        self.add_video_button.clicked.connect(self.import_video)
        self.button_layout.addWidget(self.add_video_button)

        # create button to add videos matching the names of the tail angle files from a folder
        self.add_videos_folder_button = QPushButton('Add Videos from Folder...')
        self.add_videos_folder_button.setIcon(QIcon("icons/add_video_icon.png"))
        self.add_videos_folder_button.setIconSize(QSize(16,16))
        self.add_videos_folder_button.clicked.connect(self.import_videos_from_folder)
        self.button_layout.addWidget(self.add_videos_folder_button)

        # create button to save results
        self.save_results_button = QPushButton('Save Results...')
        self.save_results_button.setStyleSheet('font-weight: bold;')
        self.save_results_button.setIcon(QIcon("icons/save_icon.png"))
        self.save_results_button.setIconSize(QSize(16,16))
        self.save_results_button.clicked.connect(self.save_results)
        self.button_layout.addWidget(self.save_results_button)

        # set main widget
        self.setCentralWidget(self.main_widget)

        # set window buttons
        if pyqt_version == 5:
            self.setWindowFlags(Qt.CustomizeWindowHint | Qt.WindowCloseButtonHint | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowFullscreenButtonHint)
        else:
            self.setWindowFlags(Qt.CustomizeWindowHint | Qt.WindowCloseButtonHint | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)

        # create menu
        self.menu = QMenu(self.main_widget)

        for behavior in behaviors:
            action = QAction(behavior, self.menu, checkable=True)
            action.setIcon(self.create_round_icon(color=colors[behaviors.index(behavior)]))
            self.menu.addAction(action)

        delete_action = QAction("Delete", self.menu)
        delete_action.setFont(bold_font)
        self.menu.addAction(delete_action)

        self.menu.triggered.connect(self.action_chosen)
        
        self.set_initial_state()

        self.show()

    def set_initial_state(self):
        self.behavior_start_time    = None
        self.behavior_end_time      = None
        self.behavior_times         = []
        self.tail_angles            = []
        self.tail_angle_paths       = []
        self.video_paths            = []
        self.videos                 = []
        self.behavior_items         = []
        self.selected_tail_angles   = 0
        self.preview_line_item      = None
        self.behaviors              = []
        self.selected_behavior      = 0
        self.current_frame          = 0

        self.setWindowTitle("")

    def plot_tail_angles(self, tail_angles):
        self.tail_plot.clear()

        if tail_angles is not None:
            one_frame    = 1.0/framerate

            x = np.linspace(0, tail_angles.shape[0]*one_frame, tail_angles.shape[0])
            self.tail_plot.plot(x, np.nanmean(tail_angles[:, -3:], axis=1), pen=pg.mkPen((255, 0, 0, 255), width=2), autoDownsample=True)
            self.tail_plot.vb.setLimits(xMin=0, xMax=x[-1])
            self.tail_plot.vb.autoRange()

            return True
        else:
            return False

    def mouse_moved(self, position):
        # get x-y coordinates of where the mouse is
        items = self.graph_widget.scene().items(position)
        if self.tail_plot in items:
            pos = self.tail_plot.vb.mapSceneToView(position)

            x = pos.x()
            y = pos.y()

            if self.preview_line_item is None:
                self.preview_line_item = pg.InfiniteLine(pos=x, angle=90, pen=pg.mkPen((0, 0, 0, 100)))
                self.tail_plot.vb.addItem(self.preview_line_item)
            else:
                self.preview_line_item.setValue(x)

            if len(self.videos) > 0 and self.videos[self.selected_tail_angles] is not None:
                frame_num = int(x*framerate)

                if 0 <= frame_num < len(self.tail_angles[self.selected_tail_angles]) and frame_num != self.current_frame:
                    capture = self.videos[self.selected_tail_angles]

                    if frame_num != self.current_frame+1:
                        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                    _, frame = capture.read()
                    frame = frame.transpose((1, 0, 2))

                    self.video_plot.setImage(frame)

                    self.current_frame = frame_num

            if self.behavior_start_time is not None:
                if len(self.behavior_items[self.selected_tail_angles][-1]) > 1:
                    behavior_rect_item = self.behavior_items[self.selected_tail_angles][-1][1]

                    behavior_rect_item.setRegion((self.behavior_start_time, x))

    def plot_clicked(self, event):
        # get x-y coordinates of where the user clicked
        items = self.graph_widget.scene().items(event.scenePos())
        if self.tail_plot in items:
            pos = self.tail_plot.vb.mapSceneToView(event.scenePos())

            x = pos.x()
            y = pos.y()

            if 0 <= x <= self.tail_angles[self.selected_tail_angles].shape[0]:
                if self.behavior_start_time is None:
                    if len(self.behavior_times[self.selected_tail_angles]) > 0:
                        behavior_clicked = np.any([ a[0] <= x <= a[1] for a in self.behavior_times[self.selected_tail_angles] ])
                    else:
                        behavior_clicked = False

                    if not behavior_clicked:
                        self.selected_behavior = None

                        behavior_index = 0

                        self.behavior_start_time = x

                        behavior_start_line_item = pg.InfiniteLine(pos=x, angle=90, pen=pg.mkPen(colors[behavior_index]), movable=True, hoverPen=pg.mkPen(color=colors[behavior_index], width=3))

                        behavior_rect_item = pg.LinearRegionItem(values=[x, x], orientation=pg.LinearRegionItem.Vertical, brush=pg.mkBrush(QColor(colors[behavior_index][0], colors[behavior_index][1], colors[behavior_index][2], 20)), movable=False)
                        self.tail_plot.vb.addItem(behavior_rect_item)

                        behavior_start_line_item.sigPositionChanged.connect(self.behavior_start_time_changed)
                        self.tail_plot.vb.addItem(behavior_start_line_item)
                        self.behavior_items[self.selected_tail_angles].append([behavior_start_line_item])
                        self.behavior_items[self.selected_tail_angles][-1].append(behavior_rect_item)
                    else:
                        # show the menu position to be under the mouse
                        position = self.main_widget.mapToGlobal(QPoint(0, 0)) + event.pos() + QPoint(self.video_viewbox.screenGeometry().width(), 0)
                        self.menu.move(QPoint(position.x(), position.y()))

                        # figure out which behavior was clicked
                        self.selected_behavior = [ a[0] <= x <= a[1] for a in self.behavior_times[self.selected_tail_angles] ].index(True)
                        behavior = self.behaviors[self.selected_tail_angles][self.selected_behavior]

                        # get the current identity of the behavior
                        identity_index = behaviors.index(behavior)

                        # set the menu actions accordingly
                        actions = self.menu.actions()
                        for i in range(len(actions)):
                            if i == identity_index:
                                actions[i].setChecked(True)
                            else:
                                actions[i].setChecked(False)

                        # show the menu
                        self.menu.show()
                else:
                    self.behavior_end_time = x

                    behavior_index = 0

                    behavior_end_line_item = pg.InfiniteLine(pos=x, angle=90, pen=pg.mkPen(color=colors[behavior_index]), movable=True, hoverPen=pg.mkPen(color=colors[behavior_index], width=3))
                    behavior_end_line_item.sigPositionChanged.connect(self.behavior_end_time_changed)
                    self.tail_plot.vb.addItem(behavior_end_line_item)
                    self.behavior_items[self.selected_tail_angles][-1].append(behavior_end_line_item)


                    text_item = pg.TextItem(behaviors[behavior_index], color=colors[behavior_index], anchor=[0.5, 0.5])
                    y = 0.9*np.nanmax(np.nanmean(self.tail_angles[self.selected_tail_angles][:, -3:], axis=1))
                    x = (self.behavior_end_time + self.behavior_start_time)/2.0
                    text_item.setPos(x, y)
                    self.tail_plot.vb.addItem(text_item)
                    self.behavior_items[self.selected_tail_angles][-1].append(text_item)
                    
                    print("Created text item at position ({}, {}).".format(x, y))

                    # flip start and end if end time is before start time
                    if self.behavior_end_time < self.behavior_start_time:
                        behavior_times = [self.behavior_end_time, self.behavior_start_time]
                        self.behavior_items[self.selected_tail_angles][-1] = [self.behavior_items[self.selected_tail_angles][-1][2], self.behavior_items[self.selected_tail_angles][-1][1], self.behavior_items[self.selected_tail_angles][-1][0], self.behavior_items[self.selected_tail_angles][-1][3]]
                        self.behavior_items[self.selected_tail_angles][-1][0].sigPositionChanged.disconnect()
                        self.behavior_items[self.selected_tail_angles][-1][0].sigPositionChanged.connect(self.behavior_start_time_changed)

                        self.behavior_items[self.selected_tail_angles][-1][2].sigPositionChanged.disconnect()
                        self.behavior_items[self.selected_tail_angles][-1][2].sigPositionChanged.connect(self.behavior_end_time_changed)
                    else:
                        behavior_times = [self.behavior_start_time, self.behavior_end_time]

                    self.behavior_times[self.selected_tail_angles].append(behavior_times)

                    self.behaviors[self.selected_tail_angles].append(behaviors[behavior_index])

                    self.behavior_start_time = None
                    self.behavior_end_time   = None

                    # show the menu position to be under the mouse
                    position = self.main_widget.mapToGlobal(QPoint(0, 0)) + event.pos() + QPoint(self.video_viewbox.screenGeometry().width(), 0)
                    self.menu.move(QPoint(position.x(), position.y()))

                    # figure out which behavior was clicked
                    booleans = [ a[0] <= x <= a[1] for a in self.behavior_times[self.selected_tail_angles] ]

                    if True in booleans:
                        self.selected_behavior = booleans.index(True)
                        behavior = self.behaviors[self.selected_tail_angles][self.selected_behavior]

                        # get the current identity of the behavior
                        identity_index = behaviors.index(behavior)

                        # set the menu actions accordingly
                        actions = self.menu.actions()
                        for i in range(len(actions)):
                            if i == identity_index:
                                actions[i].setChecked(True)
                            else:
                                actions[i].setChecked(False)

                        # show the menu
                        self.menu.show()

    def import_tail_angles(self):
        # let user pick tail angle files
        if pyqt_version == 4:
            tail_angle_paths = QFileDialog.getOpenFileNames(self, 'Select tail angle CSVs to process.', '', 'CSV Files (*.csv)')

            tail_angle_paths = [ str(path) for path in tail_angle_paths ]
        elif pyqt_version == 5:
            tail_angle_paths = QFileDialog.getOpenFileNames(self, 'Select tail angle CSVs to process.', '', 'CSV Files (*.csv)')[0]

        # import the tail angle files
        if tail_angle_paths is not None and len(tail_angle_paths) > 0:
            for tail_angle_path in tail_angle_paths:
                try:
                    tail_angles = np.genfromtxt(tail_angle_path, delimiter=",")[:, 1:]
                    self.tail_angles.append(tail_angles)
                    self.tail_angle_paths.append(tail_angle_path)
                    self.behavior_times.append([])
                    self.behavior_items.append([])
                    self.behaviors.append([])
                    self.video_paths.append(None)
                    self.videos.append(None)

                    item = QListWidgetItem(tail_angle_path)
                    item.setFlags(item.flags() & ~Qt.ItemIsDragEnabled)
                    self.tail_angles_list.addItem(item)
                except:
                    print("Error reading file '{}'.".format(tail_angle_path))

            self.tail_angles_list.setCurrentRow(self.selected_tail_angles)

            self.plot_selected_tail_angles()

    def import_tail_angles_from_folder(self):
        directory = str(QFileDialog.getExistingDirectory(self, "Select Directory"))

        tail_angle_paths = glob.glob(os.path.join(directory, '*.csv'))

        for tail_angle_path in tail_angle_paths:
            try:
                tail_angles = np.genfromtxt(tail_angle_path, delimiter=",")[:, 1:]
                self.tail_angles.append(tail_angles)
                self.tail_angle_paths.append(tail_angle_path)
                self.behavior_times.append([])
                self.behavior_items.append([])
                self.behaviors.append([])
                self.video_paths.append(None)
                self.videos.append(None)

                item = QListWidgetItem(tail_angle_path)
                item.setFlags(item.flags() & ~Qt.ItemIsDragEnabled)
                self.tail_angles_list.addItem(item)
            except:
                print("Error reading file '{}'.".format(tail_angle_path))

            self.tail_angles_list.setCurrentRow(self.selected_tail_angles)

        self.plot_selected_tail_angles()

    def import_video(self):
        # let user pick a video file
        if pyqt_version == 4:
            video_paths = QFileDialog.getOpenFileNames(self, 'Select video file to preview.', '', 'Video Files (*.avi)')

            video_paths = [ str(path) for path in video_paths ]
        elif pyqt_version == 5:
            video_paths = QFileDialog.getOpenFileNames(self, 'Select video file to preview.', '', 'Video Files (*.avi)')[0]

        # import the video file
        if video_paths is not None and len(video_paths) > 0:
            video_path = video_paths[0]

            self.video_paths[self.selected_tail_angles] = video_path
            capture = cv2.VideoCapture(video_path)

            capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            _, frame = capture.read()
            frame = frame.transpose((1, 0, 2))

            self.videos[self.selected_tail_angles] = capture

            self.video_plot.setImage(frame)

    def import_videos_from_folder(self):
        directory = str(QFileDialog.getExistingDirectory(self, "Select Directory"))

        for i in range(len(self.tail_angle_paths)):
            tail_angle_path = self.tail_angle_paths[i]

            if tail_angle_path.endswith("_tail_angles.csv"):

                base_name      = os.path.basename(tail_angle_path)
                name           = os.path.splitext(base_name)[0]
                video_name     = name.split("_tail_angles")[0] + ".avi"
                video_path     = os.path.join(directory, video_name)

                print(video_path)

                if os.path.exists(video_path):
                    self.video_paths[i] = video_path
                    capture = cv2.VideoCapture(video_path)

                    self.videos[i] = capture

                    if i == self.selected_tail_angles:
                        capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        _, frame = capture.read()
                        frame = frame.transpose((1, 0, 2))

                        self.video_plot.setImage(frame)

    def plot_selected_tail_angles(self):
        self.plot_tail_angles(self.tail_angles[self.selected_tail_angles])

    def behavior_start_time_changed(self, item):
        # get index of the behavior
        behavior_start_line_items = [ a[0] for a in self.behavior_items[self.selected_tail_angles] ]
        index = behavior_start_line_items.index(item)
        
        # update behavior start time
        self.behavior_times[self.selected_tail_angles][index][0] = item.value()

        behavior_rect_items = [ a[1] for a in self.behavior_items[self.selected_tail_angles] ]
        behavior_rect_item = behavior_rect_items[index]
        
        behavior_start_times = [ a[0] for a in self.behavior_times[self.selected_tail_angles] ]
        behavior_start_time = behavior_start_times[index]

        behavior_end_times = [ a[1] for a in self.behavior_times[self.selected_tail_angles] ]
        behavior_end_time = behavior_end_times[index]

        text_items = [ a[3] for a in self.behavior_items[self.selected_tail_angles] ]
        text_item = text_items[index]
        y = 0.9*np.amax(self.tail_angles[self.selected_tail_angles][:, -3:])
        x = (behavior_end_time + behavior_start_time)/2.0
        text_item.setPos(x, y)

        behavior_rect_item.setRegion((behavior_start_time, behavior_end_time))

    def behavior_end_time_changed(self, item):
        # get index of the behavior
        behavior_end_line_items = [ a[2] for a in self.behavior_items[self.selected_tail_angles] ]
        index = behavior_end_line_items.index(item)
        
        # update behavior end time
        self.behavior_times[self.selected_tail_angles][index][1] = item.value()

        behavior_rect_items = [ a[1] for a in self.behavior_items[self.selected_tail_angles] ]
        behavior_rect_item = behavior_rect_items[index]
        
        behavior_start_times = [ a[0] for a in self.behavior_times[self.selected_tail_angles] ]
        behavior_start_time = behavior_start_times[index]

        behavior_end_times = [ a[1] for a in self.behavior_times[self.selected_tail_angles] ]
        behavior_end_time = behavior_end_times[index]

        text_items = [ a[3] for a in self.behavior_items[self.selected_tail_angles] ]
        text_item = text_items[index]
        y = 0.9*np.amax(self.tail_angles[self.selected_tail_angles][:, -3:])
        x = (behavior_end_time + behavior_start_time)/2.0
        text_item.setPos(x, y)

        behavior_rect_item.setRegion((behavior_start_time, behavior_end_time))

    def item_selected(self, force_update=False):
        selected_items = self.tail_angles_list.selectedItems()

        if len(selected_items) > 0:

            index = self.tail_angle_paths.index(selected_items[0].text())

            if index != self.selected_tail_angles or force_update:
                self.clear_plot_items()

                self.selected_tail_angles = self.tail_angle_paths.index(selected_items[0].text())

                self.plot_selected_tail_angles()

                self.create_plot_items()

                if self.videos[index] is not None:
                    capture = self.videos[index]

                    capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    _, frame = capture.read()
                    frame = frame.transpose((1, 0, 2))

                    self.video_plot.setImage(frame)

            self.remove_tail_angles_button.setDisabled(False)
            self.add_video_button.setDisabled(False)
        else:
            self.remove_tail_angles_button.setDisabled(True)
            self.add_video_button.setDisabled(True)

    def delete_selected_tail_angles(self):
        self.clear_plot_items()

        print(self.selected_tail_angles)

        del self.tail_angles[self.selected_tail_angles]
        del self.tail_angle_paths[self.selected_tail_angles]
        del self.behavior_times[self.selected_tail_angles]
        del self.behavior_items[self.selected_tail_angles]
        del self.behaviors[self.selected_tail_angles]
        del self.video_paths[self.selected_tail_angles]
        del self.videos[self.selected_tail_angles]

        if self.selected_tail_angles >= len(self.tail_angles):
            self.selected_tail_angles -= 1

        selected_items = self.tail_angles_list.selectedItems()
        self.tail_angles_list.takeItem(self.tail_angles_list.row(selected_items[0]))

        # print(self.tail_angle_paths)

        print(self.selected_tail_angles)

        self.tail_angles_list.setCurrentRow(self.selected_tail_angles)

        self.item_selected(force_update=True)

    def delete_selected_behavior(self):
        print("Deleting behavior")
        if self.selected_behavior is not None:
            for item in self.behavior_items[self.selected_tail_angles][self.selected_behavior]:
                self.tail_plot.vb.removeItem(item)

            del self.behavior_times[self.selected_tail_angles][self.selected_behavior]
            del self.behavior_items[self.selected_tail_angles][self.selected_behavior]
            del self.behaviors[self.selected_tail_angles][self.selected_behavior]

            self.selected_behavior = None

    def clear_plot_items(self):
        for item_list in self.behavior_items[self.selected_tail_angles]:
            for i in range(len(item_list)):
                item = item_list[i]
                # item_2 = item
                self.tail_plot.vb.removeItem(item)
                # item_list[i] = item

    def create_plot_items(self):
        for item_list in self.behavior_items[self.selected_tail_angles]:
            for item in item_list:
                self.tail_plot.vb.addItem(item)

    def action_chosen(self, action):
        actions = self.menu.actions()
        index = actions.index(action)

        if index < len(actions)-1:
            self.behaviors[self.selected_tail_angles][self.selected_behavior] = behaviors[index]

            items = self.behavior_items[self.selected_tail_angles][self.selected_behavior]

            if len(items) > 0:
                items[0].setPen(pg.mkPen(color=colors[index]))
                items[0].setHoverPen(pg.mkPen(color=colors[index], width=3))
            if len(items) > 1:
                items[1].setBrush(pg.mkBrush(QColor(colors[index][0], colors[index][1], colors[index][2], 20)))
                items[1].update()
            if len(items) > 2:
                items[2].setPen(pg.mkPen(color=colors[index]))
                items[2].setHoverPen(pg.mkPen(color=colors[index], width=3))
            if len(items) > 3:
                items[3].setColor(colors[index])
                items[3].setText(behaviors[index])
        else:
            self.delete_selected_behavior()

    def save_results(self):
        directory = str(QFileDialog.getExistingDirectory(self, "Select Directory"))

        for i in range(len(self.tail_angles)):
            tail_angle_path = self.tail_angle_paths[i]

            base_name = os.path.basename(tail_angle_path)
            name      = os.path.splitext(base_name)[0]

            if tail_angle_path.endswith("_tail_angles.csv"):
                video_name = name.split("_tail_angles")[0]
            else:
                video_name = name

            with open(os.path.join(directory, '{}_behaviors.csv'.format(video_name)), mode='w') as file:
                writer = csv.writer(file, delimiter=',')
                writer.writerow(['Behavior', 'Start Time (s)', 'End Time (s)'])
                for j in range(len(self.behaviors[i])):
                    writer.writerow([self.behaviors[i][j], str(self.behavior_times[i][j][0]), str(self.behavior_times[i][j][1])])

    def create_round_icon(self, color):
        pixmap = QPixmap(40, 40)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.HighQualityAntialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.setBrush(pg.mkBrush(QColor(color[0], color[1], color[2], 255)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(4, 4, 32, 32)
        painter.end()

        icon = QIcon(pixmap)

        return icon

if __name__ == "__main__":
    app = QApplication(sys.argv)

    if pyqt_version == 5:
        # enable high DPI scaling
        app.setAttribute(Qt.AA_UseHighDpiPixmaps)
        app.setAttribute(Qt.AA_EnableHighDpiScaling)

    # create window
    window = Window()

    app.exec_()