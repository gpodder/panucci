# -*- coding: utf-8 -*-
#
# This file is part of Panucci.
# Copyright (c) 2008-2011 The Panucci Project
#
# Panucci is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Panucci is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Panucci.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import absolute_import

import logging
import sys
import os
import time
import cgi
import dbus

from PySide  import QtCore
from PySide import QtGui

from panucci import platform
from panucci import util

##################################################
# PlaylistTab
##################################################
class PlaylistTab():
    def __init__(self, main, player):
        self.__log = logging.getLogger('panucci.panucci.BookmarksWindow')
        self.__gui_root = main
        self.player = player
        self.player.playlist.register( 'file_queued', lambda x,y,z: self.update_model() )
        self.player.playlist.register( 'bookmark_added', self.on_bookmark_added )

        self.main_window = QtGui.QMainWindow(main.main_window)
        self.main_window.setWindowTitle(_("Playlist"))
        widget = QtGui.QWidget()
        layout = QtGui.QVBoxLayout()
        widget.setLayout(layout)
        self.main_window.setCentralWidget(widget)
        layout.setSpacing(5)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tree = QtGui.QTreeView()
        layout.addWidget(self.tree, 3)
        # (name, position, bid)
        self.__model = QtGui.QStandardItemModel(0, 3)
        self.tree.setModel(self.__model)
        item = QtGui.QStandardItem(_("Name"))
        self.__model.setHorizontalHeaderItem(0, item)
        item = QtGui.QStandardItem(_("Position"))
        #item.setTextAlignment(QtCore.Qt.AlignRight)
        self.__model.setHorizontalHeaderItem(1, item)
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setResizeMode(0, QtGui.QHeaderView.Stretch)
        self.tree.hideColumn(2)

        hlayout = QtGui.QHBoxLayout()
        layout.addLayout(hlayout)
        hlayout.setSpacing(0)

        self.button_file = QtGui.QPushButton(QtGui.QIcon(util.find_data_file('')), _("Add File"))
        self.button_file.clicked.connect(self.button_file_callback)
        #self.button_rrewind.setFixedHeight(settings.config.getint("options", "button_height"))
        self.button_dir = QtGui.QPushButton(QtGui.QIcon(util.find_data_file('')), _("Add Folder"))
        self.button_dir.clicked.connect(self.button_dir_callback)
        #self.button_dir.setFixedHeight(settings.config.getint("options", "button_height"))
        self.button_remove = QtGui.QPushButton(QtGui.QIcon(util.find_data_file('')), _("Remove"))
        self.button_remove.clicked.connect(self.button_remove_callback)
        #self.button_remove.setFixedHeight(settings.config.getint("options", "button_height"))
        self.button_jump = QtGui.QPushButton(QtGui.QIcon(util.find_data_file('')), _("Jump to"))
        self.button_jump.clicked.connect(self.button_jump_callback)
        #self.button_jump.setFixedHeight(settings.config.getint("options", "button_height"))
        self.button_info = QtGui.QPushButton(QtGui.QIcon(util.find_data_file('')), _("Info"))
        self.button_info.clicked.connect(self.button_info_callback)
        #self.button_info.setFixedHeight(settings.config.getint("options", "button_height"))
        self.button_clear = QtGui.QPushButton(QtGui.QIcon(util.find_data_file('')), _("Clear"))
        self.button_clear.clicked.connect(self.button_clear_callback)
        #self.button_clear.setFixedHeight(settings.config.getint("options", "button_height"))

        hlayout.addWidget(self.button_file)
        hlayout.addWidget(self.button_dir)
        hlayout.addWidget(self.button_remove)
        hlayout.addWidget(self.button_jump)
        hlayout.addWidget(self.button_info)
        hlayout.addWidget(self.button_clear)

    def button_file_callback(self):
        self.__gui_root.add_file_callback()

    def button_dir_callback(self):
        self.__gui_root.add_folder_callback()

    def button_remove_callback(self):
        selection, item, bkmk, item_id, bkmk_id, parent = self.get_current_selection()
        if selection:
            if parent:
                parent.removeRow(selection[0].row())
            else:
                self.__model.removeRow(selection[0].row())
            self.player.playlist.remove_bookmark( item_id, bkmk_id )

    def button_jump_callback(self):
        selection, item, bkmk, item_id, bkmk_id, parent = self.get_current_selection()
        if selection:
            self.player.playlist.load_from_bookmark_id(item_id, bkmk_id)

    def get_current_selection(self):
        selection = self.tree.selectedIndexes()
        if selection:
            item = self.__model.itemFromIndex(selection[0])
            parent = item.parent()
            if parent:
                bkmk = parent.child(selection[0].row(), 2)
                bkmk_id = bkmk.data(QtCore.Qt.DisplayRole)
                item = self.__model.item(parent.row(), 2)
            else:
                 bkmk, bkmk_id = None, None
                 item = self.__model.item(item.row(), 2)
            item_id = item.data(QtCore.Qt.DisplayRole)
        else:
            item, bkmk, item_id, bkmk_id, parent = None, None, None, None, None

        return selection, item, bkmk, item_id, bkmk_id, parent

    def button_info_callback(self):
        pass

    def button_clear_callback(self):
        self.__gui_root.clear_playlist_callback()

    def update_model(self):
        plist = self.player.playlist
        #path_info = self.treeview.get_path_at_pos(0,0)
        #path = path_info[0] if path_info is not None else None
        self.clear_model()

        for item, data in plist.get_playlist_item_ids():
            parent = QtGui.QStandardItem(data.get('title'))
            self.__model.appendRow((parent, None, QtGui.QStandardItem(item)))

            for bid, bname, bpos in plist.get_bookmarks_from_item_id( item ):
                parent.appendRow((QtGui.QStandardItem(bname), QtGui.QStandardItem(util.convert_ns(bpos)),
                                  QtGui.QStandardItem(bid)))

        self.tree.expandAll()
        #if path is not None:
        #    self.treeview.scroll_to_cell(path)

    def clear_model(self):
        self.__model.removeRows(0, self.__model.rowCount())

    def on_bookmark_added(self, parent_id, bookmark_name, position):
        #self.__gui_root.notify(_('Bookmark added: %s') % bookmark_name)
        self.update_model()
