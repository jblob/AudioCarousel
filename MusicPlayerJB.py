# Standard library imports
import sys
import os
import re
import subprocess
import glob
import random
import shutil
from subprocess import Popen, PIPE, STDOUT
from pathlib import Path
import sqlite3

# PyQt imports
from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import (
    QAction, QApplication, QLabel, QMainWindow, QMenu, QDialog, QFileDialog,
    QStatusBar, QPushButton, QGridLayout, QScrollArea, QWidget, QVBoxLayout,
    QDialogButtonBox, QMessageBox, QTableView, QTabWidget, 
	QComboBox, QWidgetAction, QCheckBox, QListWidget, QListWidgetItem, QHBoxLayout, QLineEdit
)
from PyQt5.QtCore import Qt, QUrl, QSortFilterProxyModel, QPoint
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent, QMediaPlaylist, QMediaMetaData
from PyQt5.QtCore import pyqtRemoveInputHook # see comment below
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtCore import QAbstractTableModel

# Third-party library imports
import mutagen
from mutagen.mp3 import MP3, MPEGInfo
from mutagen.mp4 import MP4
from mutagen.id3 import ID3, APIC
from mutagen.easyid3 import EasyID3

# Local imports
from functools import partial
# from typing import NamedTuple

bDebug = True
bDebugSQL = False
bDebugCfg = True
bRegenerateAlbumImages = True

class StdoutRedirector:
	def __init__(self, text_widget):
		self.text_widget = text_widget

	def write(self, text):
		self.text_widget.append(text) # Text am Ende einfügen

	def flush(self):
		pass # Eine flush-Methode ist für diese Verwendung nicht erforderlich, sollte aber vorhanden sein

class PlaylistGenerator:
	def __init__(self):
		pass
		
	def genCompletePlaylistFromDirectory(self, directory, outputfile, bRandom):
		files = glob.glob(directory + '/**/*.mp?', recursive=True)
		if bDebug:
			print('<genCompletePlaylistFromDirectory><directory>' + str(directory))
			print('<genCompletePlaylistFromDirectory><files>' + str(files))
		if bRandom:
			random.shuffle(files)
			
		text = ''
		for f in files:
			text += f + '\n'
			
		with open(outputfile, 'w') as fout:
			fout.write(text)
			fout.close()
			
class MP3Data:
	def __init__(self):
		self.mpgType = ''
		self.title = ''
		self.artist = ''
		self.album = ''
		self.albumartist = ''
		self.genre = ''
		self.duration = 0
		self.bCoverAvailable = False
		self.tracknumber = 0
		self.year = 0
		self.channels = 0
		self.bitrate_mode = ''
		self.bitrate = 0
		self.rating = 0
		self.fullpath = ''
		self.imagedirectory = 'images'
		if not os.path.exists(self.imagedirectory):
			os.makedirs(self.imagedirectory)

	def data(self, player):
		# this is only usable while playing, otherwise no QMediaMetaData is available :/
		info = {}
		info['artist'] = player.metaData(QMediaMetaData.AlbumArtist)
		info['album'] = player.metaData(QMediaMetaData.AlbumTitle)
		info['track'] = player.metaData(QMediaMetaData.Title)
		info['release'] = player.metaData(QMediaMetaData.Year)
		info['genre'] = player.metaData(QMediaMetaData.Genre)
		info['coverart'] = player.metaData(QMediaMetaData.CoverArtImage)
		info['coverart_th'] = player.metaData(QMediaMetaData.ThumbnailImage)
		if info['artist'] == None:
			info['artist'] = 'Unknown'
		if info['album'] == None:
			info['album'] = 'Unknown'
		if info['track'] == None:
			info['track'] = 'Unknown'
		if info['release'] == None:
			info['release'] = 'Unknown'
		if info['genre'] == None:
			info['genre'] = 'Unknown'
		if info['coverart'] == None:
			info['coverart'] = 'Unknown'
		if info['coverart_th'] == None:
			info['coverart_th'] = 'Unknown'
		# if bDebug:
			# metadatalist = player.availableMetaData()
			# print('<METADATALIST>' + str(metadatalist))
		return info
		
	def getTagsFromFile(self, file):
		if file.endswith('mp3'):
			self.mpgType = 'mp3'
		elif file.endswith('mp4'):
			self.mpgType = 'mp4'
		
		self.fullpath = file

		if self.mpgType == 'mp3':
			try:
				audio = MP3(file, ID3=EasyID3)
				tags = ID3(file)
				self.title = audio.get('title', ['-'])[0].replace('"', '')
				self.artist = audio.get('artist', ['-'])[0].replace('"', '')
				self.albumartist = audio.get('albumartist', ['-'])[0].replace('"', '')
				self.album = audio.get('album', ['-'])[0].replace('"', '')
				self.genre = audio.get('genre', ['-'])[0].replace('"', '')
				self.duration = audio.info.length
				self.bCoverAvailable = any(k.startswith('APIC') for k in tags.keys())
				self.tracknumber = audio.get('tracknumber', [0])[0]
				self.year = audio.get('date', ['0'])[0]
				self.channels = audio.info.channels
				self.bitrate_mode = str(audio.info.bitrate_mode)
				self.bitrate = audio.info.bitrate
			except Exception as e:
				if bDebug: 
					print(f"Error reading MP3 tags: {e}")
	###
			# print("ID3 tags included in this song ------------------")
			# print(tags.pprint())
			# print(tags.__dict__.keys())
			# if text in tags:
			# for t in tags:
				# print('<TAG>' + str(t))
			# if 'TALB' in tags:
				# print('<TALB>' + str(tags['TALB']))
			# else:
				# print('<TALB>n/a')
			# if 'APIC' in tags:
				# print('<APIC>' + str(tags['APIC']))
			# else:
				# print('<APIC>n/a')
			# if 'APIC:Cover' in tags:
				# print('<APIC:Cover>' + str(tags['APIC:Cover']))
			# else:
				# print('<APIC:Cover>n/a')
		elif self.mpgType == 'mp4':
			try:
				mp4 = MP4(file)
				self.title = mp4.tags.get('\xa9nam', [' '])[0] if mp4.tags else ' '
				self.artist = mp4.tags.get('\xa9ART', [' '])[0].replace('"', '') if mp4.tags else ' '
				self.albumartist = mp4.tags.get('aART', [' '])[0].replace('"', '') if mp4.tags else ' '
				self.album = mp4.tags.get('\xa9alb', [' '])[0].replace('"', '') if mp4.tags else ' '
				self.genre = mp4.tags.get('\xa9gen', [' '])[0].replace('"', '') if mp4.tags else ' '
				self.duration = mp4.info.length
				self.bCoverAvailable = False
				self.tracknumber = 0
				self.year = mp4.tags.get('\xa9day', ['0'])[0] if mp4.tags else '0'
				self.channels = mp4.info.channels
				self.bitrate_mode = 'BitrateMode.UNKNOWN'
				self.bitrate = mp4.info.bitrate
			except Exception as e:
				if bDebug: print(f"Error reading MP4 tags: {e}")
			self.rating = 0 ### TODO

			# metadata = \
			# {
				# 'Title': mp4.get('title', [''])[0],
				# 'Artist': mp4.get('artist', [''])[0],
				# 'Album': mp4.get('album', [''])[0],
				# 'Genre': mp4.get('genre', [''])[0],
				# 'Duration': mp4.info.length,
				# 'Bitrate': mp4.info.bitrate,
				# 'Sample Rate': mp4.info.sample_rate, ### !!!
				# 'Channels': mp4.info.channels
			# }
			# print(str(metadata))

		return [self.title, self.artist, self.albumartist, self.album, self.genre, self.duration, self.bCoverAvailable, self.tracknumber, self.year, self.channels, self.bitrate_mode, self.bitrate, self.rating, self.fullpath]
		
	def getImage(self, file):
		img_name = 'NoImage'
		if file.endswith('mp3'):
			self.mpgType = 'mp3'
		elif file.endswith('mp4'):
			self.mpgType = 'mp4'
		if self.mpgType == 'mp3':
			audio = MP3(file, ID3=ID3)
			audio2 = MP3(file, ID3=EasyID3)
			tags  = ID3(file)
			artist = audio2.get('artist', ['Unknown'])[0].replace('/', '_').replace('"', '')
			album = audio2.get('album', ['Unknown'])[0].replace('/', '_').replace('"', '')
				
			# Einheitliche Bereinigung des Dateinamens
			clean_filename = (artist + '_' + album + '.jpg').replace('?', '_').replace(':', '_').replace(' ', '')
			img_name = os.path.join(self.imagedirectory, clean_filename)
				
			if bDebug:
				print('<IMGNAME>' + img_name)
			# Check if the MP3 file contains an embedded image
			if audio.tags is not None:
				for tag in audio.tags.values():
					if isinstance(tag, APIC):  # Look for the APIC frame (Attached Picture)
						# Extract the image data
						image_data = tag.data
						# Save the image to a file - "artist_album.jpg"
						###img_name = audio['artist'][0] + '_' + audio['album'][0]
						# if bDebug:
							# print('<Embedded_image>' + img_name)
						with open(img_name, 'wb') as img_file:
							img_file.write(image_data)
							img_file.flush()
							os.fsync(img_file.fileno())
						# break
		return img_name
	
	def printData(self, file):
		print('---------------------------------------------------')
		print('<MP3DATA>')
		print('\t<MPGTYPE>' + self.mpgType)
		print('\t<TITLE>' + self.title)
		print('\t<ARTIST>' + self.artist)
		print('\t<ALBUMARTIST>' + self.albumartist)
		print('\t<ALBUM>' + self.album)
		print('\t<GENRE>' + self.genre)
		print('\t<DURATION>' + str(self.duration))
		print('\t<COVER_AVAIL>' + str(self.bCoverAvailable))
		print('\t<TRACKNUMBER>' + str(self.tracknumber))
		print('\t<YEAR>' + str(self.year))
		print('\t<CHANNELS>' + str(self.channels))
		print('\t<BITRATEMODE>' + str(self.bitrate_mode))
		print('\t<BITRATE>' + str(self.bitrate))
		print('\t<RATING>' + str(self.rating))
		print('\t<FULLPATH>' + self.fullpath)
		print('</MP3DATA>')
		print('---------------------------------------------------')
		
class TableModel(QAbstractTableModel):
	def __init__(self, data, headers):
		super().__init__()
		self._data = data
		self._headers = headers  # Column headers
		
	def data(self, index, role):
		if role == Qt.DisplayRole:
			# See below for the nested-list data structure.
			# .row() indexes into the outer list,
			# .column() indexes into the sub-list
			return self._data[index.row()][index.column()]

	def rowCount(self, index):
		# The length of the outer list.
		return len(self._data)

	def columnCount(self, index):
		# The following takes the first sub-list, and returns
		# the length (only works if all rows are an equal length)
		return len(self._headers)  # Number of columns

	def headerData(self, section, orientation, role=Qt.DisplayRole):
		if role == Qt.DisplayRole:
			if orientation == Qt.Horizontal:  # Column headers
				return self._headers[section]
			elif orientation == Qt.Vertical:  # Row numbers
				return str(section + 1)

class MainWindow(QtWidgets.QDialog):
	def __init__(self, configs, lConfigs, startconfig):
		super(MainWindow, self).__init__()
		self.COVER_SIZE = 150
		uic.loadUi('MusicPlayerJB.ui', self)
#?		self.setFixedSize(1400,810)
		self.label_cover.setFixedSize(self.COVER_SIZE, self.COVER_SIZE)
		
		self.configs = configs
		self.lConfigs = lConfigs
		
		self.curConfig      = startconfig
		self.db             = DB(self.configs.dCfgDbname[startconfig])
		self.randomplaylist = self.configs.dCfgRandomplaylist[startconfig]
		self.sounddir       = self.configs.dCfgSounddir[startconfig]
		
		self.player_mode = self.buttonGroup.checkedButton().text() ### 'AlbumPlayer' # TODO: read this from config ?
		self.bAlbumSelected = False
		self.bPlaylistChanged = False

		self.player = QMediaPlayer()
		self.playlist = QMediaPlaylist()
		pyqtRemoveInputHook() # otherwise no debugging with pdb possible :/
#		self.randomplayliststate = self.getPlaylistSavedState(self.randomplaylist)
		self.label_cover.setStyleSheet('background-color: white;')

		# connect signals and slots
		self.pushButton_randomplaylist_play.clicked.connect(self.pushButton_randomplaylist_play_run)
		self.pushButton_genrandomplaylist.clicked.connect(self.pushButton_genrandomplaylist_run)
		self.pushButton_randomplaylist_stop.clicked.connect(self.pushButton_randomplaylist_stop_run)
		self.pushButton_randomplaylist_pause.clicked.connect(self.pushButton_randomplaylist_pause_run)
		self.pushButton_randomplaylist_prev.clicked.connect(self.pushButton_randomplaylist_prev_run)
		self.pushButton_randomplaylist_next.clicked.connect(self.pushButton_randomplaylist_next_run)
		self.pushButton_database_updateDB.clicked.connect(self.pushButton_database_updateDB_run)
		self.pushButton_database_showDB.clicked.connect(self.pushButton_database_showDB_run)
		self.pushButton_testsqlquery.clicked.connect(self.pushButton_testsqlquery_run)
		self.pushButton_albumplayer_playalbum.clicked.connect(self.pushButton_albumplayer_playalbum_run)
		self.pushButton_config_editconfig.clicked.connect(self.pushButton_config_editconfig_run)
		self.pushButton_config_newconfig.clicked.connect(self.pushButton_config_newconfig_run)
		self.pushButton_config_deleteconfig.clicked.connect(self.pushButton_config_deleteconfig_run)
		self.pushButton_config_setasdefault.clicked.connect(self.pushButton_config_setasdefault_run)
		self.buttonGroup.buttonToggled.connect(self.slot_modechanged)

		self.player.metaDataChanged.connect(self.slotMetaDataChanged)
		self.playlist.currentIndexChanged.connect(self.slotIndexChanged)
		
		### TODO: this is in test only
		# self.player.setMedia(QMediaContent(QUrl.fromLocalFile('e:/000_2024/at_Urlaub/dSPACE_LearningConnectionRecording_MBD_1280x720_20210211-2_EN.mp4')))
#		self.player.setMedia(QMediaContent(QUrl.fromLocalFile('e:/at_home/3/Sound/_videos_unsorted/t_online_werbung.mp4')))
#		self.player.setVideoOutput(self.widget_videooutput)
		# connect(mplayer, &QMediaPlayer::stateChanged, [vw](QMediaPlayer::State state){
							# if (state == QMediaPlayer::StoppedState)
								# vw->update(); });
		# vw.show();
		self.statusBar = QStatusBar()
		self.verticalLayout_statusbar.addWidget(self.statusBar)
		self.statusBar.showMessage('------------------------------------')
		
		self.updateListViews()
		
		# self.comboBox_selectconfig.currentIndexChanged.connect(self.comboBox_selectconfig_cfgchanged_i)
		self.comboBox_selectconfig.currentTextChanged.connect(self.comboBox_selectconfig_cfgchanged_t)
		
		# fill listview from config file
		self.comboBox_selectconfig.addItems(lConfigs)
		self.comboBox_selectconfig.setCurrentText(startconfig)
		
	def slot_modechanged(self, obj, checked):
		self.player_mode = obj.text()
		# if bDebug:
			# print('<slot_modechanged>setting player mode to ' + self.player_mode)
		# pass
		
	def updateListViews(self):
		# fill listviews from DB
		self.comboBox_genre.clear()
		self.comboBox_artist.clear()
		self.allgenres = self.db.getColValsFromDB('Albums', 'Genre')
		self.allartists = self.db.getColValsFromDB('Albums', 'Artist')
		self.comboBox_genre.addItem('--- All ---')
		self.comboBox_artist.addItem('--- All ---')
		self.comboBox_genre.addItems(self.allgenres)
		self.comboBox_artist.addItems(self.allartists)

	def pushButton_randomplaylist_play_run(self):
		# if self.player.state() == QMediaPlayer.PlayingState:
		# elif self.player.state() == QMediaPlayer.StoppedState:
		if self.player_mode == 'RandomPlayer':
			if self.player.state() == QMediaPlayer.PlayingState:
				print('already playing')
			elif self.player.state() == QMediaPlayer.StoppedState:
				# self.url = QUrl

				# load playlist only when it is empty or has been regenerated
				if self.playlist.mediaCount() == 0 or self.bPlaylistChanged:
					self.playlist.clear()
					self.playlist = Utils.load_playlist_from_file(self.randomplaylist)
					
					self.listWidget_randomplaylist.clear()
					if os.path.exists(self.randomplaylist):
						with open(self.randomplaylist, 'r') as fin:
							for line in fin:
								if line.strip():
									self.listWidget_randomplaylist.addItem(line.strip())
				
				# WICHTIG f. Neustart: Zuerst die Playlist an den Player binden...
				if self.player.playlist() != self.playlist:
					self.player.setPlaylist(self.playlist)

				# Index aus dem gespeicherten Zustand holen
				saved_idx = self.getPlaylistSavedState(self.randomplaylist)
				# Absicherung gegen -1 oder Out-of-Bounds
				if saved_idx >= self.playlist.mediaCount() or saved_idx < 0:
					saved_idx = 0
				
				# Erst der Playlist den Index zuweisen...
				self.playlist.setCurrentIndex(saved_idx)
					
				self.player.setVolume(50)
				self.player.play()
				self.bPlaylistChanged = False
			elif self.player.state() == QMediaPlayer.PausedState:
				self.player.play()
		elif self.player_mode == 'AlbumPlayer':
			if not self.bAlbumSelected:
				self.pushButton_albumplayer_playalbum_run()
			elif self.player.state() != QMediaPlayer.PlayingState:
				# self.player.setVolume(50)
				self.player.play()

	def pushButton_randomplaylist_play_2_run(self):
		if self.player.state() == QMediaPlayer.PlayingState:
			if self.player_mode == 'AlbumPlayer':
				self.player.stop()
				self.load_playlist_from_file(self.randomplaylist, self.playlist)
				# play playlist
				self.player.setPlaylist(self.playlist)
				self.player.play()
				# self.player_mode = 'RandomPlayer'
			elif self.player_mode == 'RandomPlayer':
				print('already playing')
		elif self.player.state() == QMediaPlayer.StoppedState:
			self.url = QUrl
			self.listWidget_randomplaylist.clear()

			# load playlist
			self.load_playlist_from_file(self.randomplaylist, self.playlist)
			with open(self.randomplaylist, 'r') as fin:
				lines = fin.readlines()
				fin.close()
				for _line in lines:
					line = os.path.join(os.getcwd(), _line.strip())
					self.listWidget_randomplaylist.addItem(line)

			self.playlist.setCurrentIndex(self.randomplayliststate)
			self.player.setPlaylist(self.playlist)
			self.player.setVolume(50)
			self.player.play()
		elif self.player.state() == QMediaPlayer.PausedState:
			self.player.play()

	def pushButton_genrandomplaylist_run(self):
		plgen = PlaylistGenerator()
		### old implementation with dialog -> now changed to read from config
		# d = QFileDialog.getExistingDirectory(self, 'select Music Directory', '.', QFileDialog.Option.ShowDirsOnly)
		# plgen.genCompletePlaylistFromDirectory(d, self.randomplaylist, True)
		plgen.genCompletePlaylistFromDirectory(self.sounddir, self.randomplaylist, True)
		self.playlist.setCurrentIndex(0)
		self.savePlaylistState(self.playlist, self.randomplaylist)
		self.bPlaylistChanged = True
		
	def pushButton_randomplaylist_stop_run(self):
		self.player.stop()
		self.savePlaylistState(self.playlist, self.randomplaylist)
		
	def pushButton_randomplaylist_pause_run(self):
		if self.player.state() == QMediaPlayer.PlayingState:
			self.player.pause()
		elif self.player.state() == QMediaPlayer.StoppedState:
			print('not playing')
		elif self.player.state() == QMediaPlayer.PausedState:
			print('already paused')
			
	def pushButton_randomplaylist_prev_run(self):
		# Method for going to previous track
		if self.playlist.previousIndex() == -1:
			self.playlist.setCurrentIndex(self.playlist.mediaCount()-1)
		else:
			self.playlist.previous()
		self.savePlaylistState(self.playlist, self.randomplaylist)
		  
	def pushButton_randomplaylist_next_run(self):
		# method for moving to next track
		self.playlist.next()
		if self.playlist.currentIndex() == -1:
			self.playlist.setCurrentIndex(0)
			self.player.play()
		self.savePlaylistState(self.playlist, self.randomplaylist)

	def savePlaylistState(self, playlist, playlistfile):
		if playlistfile == '': 
			return
		idx = playlist.currentIndex()
		# save only when idx valid (>=0)
		# this avoids overwriting the index in the STOPPED state
		if idx >= 0:
			if bDebug: 
				print('<I><savePlaylistState>' + playlistfile + '<idx>' + str(idx))
			try:
				f = open(playlistfile + '.index.txt', 'w')
				f.write(str(idx))
				f.close()
			except Exception as e:
				print('<E><savePlaylistState>Error saving playlist state: ' + e)

	def getPlaylistSavedState(self, playlist):
		if playlist == '':
			return 0
		filename = playlist + '.index.txt'
		if os.path.exists(filename):
			f = open(filename, 'r')
			lines = f.readline()
			val = int(lines, 10)
			f.close()
		else:
			val = 0
		if bDebug:
			print('<getPlaylistSavedState>' + str(val))
		return val

	def slotMetaDataChanged(self):
		if self.player.isMetaDataAvailable():
			# data = self.player.metaData(QMediaMetaData.Title)
			mp3data = MP3Data().data(self.player)
			if bDebug:
				print('<slotMetaDataChanged>' + str(mp3data))
			self.label_artist_2.setText(mp3data['artist'])
			self.label_title_2.setText(mp3data['track'])
			self.label_album_2.setText(mp3data['album'])
			self.label_genre_2.setText(str(mp3data['genre'])) # genre is a list, TODO: better handling to display it ? genre[0] ?
			self.label_year_2.setText(str(mp3data['release']))

			if mp3data['coverart_th'] and mp3data['coverart_th'] != 'Unknown':
				pixmap = QPixmap(mp3data['coverart_th'])
				pixmap = pixmap.scaled(self.COVER_SIZE, self.COVER_SIZE)
				self.label_cover.setPixmap(pixmap)
			else:
				self.label_cover.clear() ### TODO: standard pixmap
			self.statusBar.showMessage('playing: ' + mp3data['track'] + ' - ' + mp3data['artist'])
		else:
			self.label_artist_2.setText('<unknown>')
			self.label_title_2.setText('<unknown>')
			self.label_album_2.setText('<unknown>')
			self.label_genre_2.setText('<unknown>')
			self.label_year_2.setText('<unknown>')

			# self.label_cover.setPixmap(pixmap) ### TODO: standard pixmap
		self.savePlaylistState(self.playlist, self.randomplaylist)
			
	def slotIndexChanged(self):
		idx = self.playlist.currentIndex()
		if idx >= 0:
			self.listWidget_randomplaylist.setCurrentRow(idx)
			self.savePlaylistState(self.playlist, self.randomplaylist)

	def closeEvent(self, event):
		self.savePlaylistState(self.playlist, self.randomplaylist)
		self.db.conn.close()
	
	def pushButton_database_updateDB_run(self):
		# Thread filling the DB
		lAllAlbums = []
		files = glob.glob(self.sounddir + '/**/*.mp?', recursive=True) ### mp4 not supported by mutagen :( -> TODO: search for another lib
		nFilesToProceed = len(files) # for progress bar
		self.db.createTables()
		error_log = []
		if bDebug:
			print('=============================================================')
			print('[Updating DB] started')
			
		# Verwende enumerate, um den aktuellen Index (startend bei 1) mitzuzählen
		for idx, curfile in enumerate(files, 1):
			# Prozentwert berechnen
			percent = (idx / nFilesToProceed) * 100 if nFilesToProceed > 0 else 100
			
			if bDebug:
				# \r sorgt dafür, dass der Cursor an den Zeilenanfang springt und die Zeile überschreibt
				sys.stdout.write(f"\r\tProcessing: {percent:.1f}% ({idx}/{nFilesToProceed})")
				sys.stdout.flush()
				# if curfile.startswith('/home/blju/Sound/Clash/Videos/The'):
					# print('Here')
			
			# Fortschritt in der GUI-Statusleiste anzeigen
			self.statusBar.showMessage(f"Datenbank wird aktualisiert: {percent:.1f}% ({idx}/{nFilesToProceed})")
			# Verhindert, dass die GUI während der Schleife einfriert
			QApplication.processEvents()
			
			m = MP3Data()
			arrMp3Data = m.getTagsFromFile(curfile)
			self.db.addline_tablesongs(arrMp3Data)
			
			# --- Validierung der Tags laut Vorgabe ---
			title = arrMp3Data[0].strip()
			artist = arrMp3Data[1].strip()
			albumartist = arrMp3Data[2].strip()
			album = arrMp3Data[3].strip()
			genre = arrMp3Data[4].strip()
			cover_avail = arrMp3Data[6]
			
			is_sampler = "_Sampler" in os.path.split(curfile)[0] or "_Sampler" in curfile
			is_mp4 = curfile.lower().endswith('.mp4')
			
			# 1. TAG Title nicht enthalten
			if not title or title == '-':
				error_log.append(f"<E_MISSING_TITLE> {curfile}")
				
			# 2. TAG Artist nicht vorhanden UND kein „_Sampler“
			if (not artist or artist == '-') and not is_sampler:
				error_log.append(f"<E_MISSING_ARTIST_NOSAMPLER> {curfile}")
				
			# 3. TAG AlbumArtist nicht vorhanden UND Song ist nicht in einem Unterordner von „_Sampler“
			if (not albumartist or albumartist == '-') and is_sampler:
				error_log.append(f"<E_MISSING_ARTIST_SAMPLER> {curfile}")
				
			# 4. TAG AlbumArtist nicht vorhanden UND Song ist nicht in einem Unterordner von „_Sampler“
			if albumartist.lower() != 'various' and is_sampler:
				error_log.append(f"<E_ARTIST_WRONG_SAMPLER> {curfile}")
				
			# 5. TAG Album nicht enthalten und Dateiendung ungleich MP4
			if (not album or album == '-') and not is_mp4:
				error_log.append(f"<E_MISSING_ALBUM> {curfile}")
				
			# 6. TAG Genre nicht enthalten
			if not genre or genre == '-':
				error_log.append(f"<E_MISSING_GENRE> {curfile}")
				
			# 7. kein embedded cover und Dateiendung ungleich MP4
			if not cover_avail and not is_mp4:
				error_log.append(f"<E_MISSING_COVER> {curfile}")
			# ----------------------------------------

			artist_key = arrMp3Data[1] # Artist
			album_key = arrMp3Data[3]  # Album
			album_identifier = (artist_key, album_key)
			if not album_identifier in lAllAlbums:
				lAllAlbums.append(album_identifier)
				imagename = 'NoImage'
				if bRegenerateAlbumImages:
					imagename = m.getImage(curfile)
				self.db.addline_tablealbums(arrMp3Data, imagename)
				
		# Fehlerprotokoll in Datei schreiben
		try:
			with open("MusicErrors.txt", "w", encoding="utf-8") as error_file:
				if error_log:
					error_file.write("\n".join(error_log) + "\n")
				else:
					error_file.write("Keine Fehler gefunden.\n")
			if bDebug:
				print(f"[Updating DB] {len(error_log)} Warnungen in MusicErrors.txt geschrieben.")
		except Exception as e:
			print(f"Fehler beim Schreiben der MusicErrors.txt: {e}")

		if bDebug:
			print() # Erzeugt einen Zeilenumbruch nach den vielen \r Ausgaben
			print('[Updating DB] finished')
			print('=============================================================')

		self.statusBar.showMessage('Datenbank-Aktualisierung abgeschlossen.', 5000)

		with open('sql.log', 'w') as fout:
			fout.write(self.db.sqltext_dbg)
			fout.close()
			
	def pushButton_database_showDB_run(self):
		data1 = self.db.getTable('Songs')
		data2 = self.db.getTable('Albums')

		headers1 = ['Title', 'Artist', 'AlbumArtist', 'Album', 'Genre', 'Duration', 'CoverAvail', 'TrackNr', 'Year', 'Channels', 'BitrateMode', 'Bitrate', 'Rating', 'Fullpath']
		headers2 = ['Artist', 'AlbumArtist', 'Album', 'Genre', 'CoverPath', 'FullPath']

		# Create and show the TabWindow
		self.tab_window = TabWindow(headers1, data1, headers2, data2)
		self.tab_window.show()

	def pushButton_testsqlquery_run(self):
		cmd = self.lineEdit_testsqlquery.text()
		res = self.db.exec_sql(cmd, True, False, True)
		self.textBrowser_testsqlquery.setText(res)
		
	def pushButton_albumplayer_playalbum_run(self):
		self.apd = AlbumPlayerDlg(self)  # Pass MainWindow instance
		# self.apd.exec_() ### modal dialog
		self.apd.show() ### non-modal dialog
		self.bAlbumSelected = True
		
	# def comboBox_selectconfig_cfgchanged_i(self, value):
		# if bDebug:
			# print('<comboBox_selectconfig_cfgchanged_i>' + str(value))
		
	def comboBox_selectconfig_cfgchanged_t(self, value):
		if bDebug:
			print('<comboBox_selectconfig_cfgchanged_t>' + value)
		self.curConfig      = value
		self.db             = DB(self.configs.dCfgDbname[value])
		self.randomplaylist = self.configs.dCfgRandomplaylist[value]
		self.sounddir       = self.configs.dCfgSounddir[value]
		self.updateListViews()
		
	def pushButton_config_editconfig_run(self):
		self.dlg = QDialog(self)
		uic.loadUi('Dlg_editConfig.ui', self.dlg)
		self.dlg.lineEdit_configname.setReadOnly(True)
		self.dlg.buttonBox_okcancel.clicked.connect(self.buttonBox_okcancel_run)
		self.dlg.lineEdit_configname.setText(self.curConfig)
		self.dlg.lineEdit_database.setText(self.configs.dCfgDbname[self.curConfig])
		self.dlg.lineEdit_sounddir.setText(self.sounddir)
		self.dlg.lineEdit_randomplaylist.setText(self.randomplaylist)
		self.dlg.exec_()
		
	def pushButton_config_newconfig_run(self):
		self.dlg = QDialog(self)
		uic.loadUi('Dlg_editConfig.ui', self.dlg)
		self.dlg.buttonBox_okcancel.clicked.connect(self.buttonBox_okcancel2_run)
		self.dlg.lineEdit_configname.setText('enter config name')
		self.dlg.lineEdit_database.setText('enter path to DB')
		self.dlg.lineEdit_sounddir.setText('enter path to music library')
		self.dlg.lineEdit_randomplaylist.setText('enter name of playlist')
		self.dlg.exec_()
		
	def pushButton_config_deleteconfig_run(self):
		if len(self.lConfigs) < 2:
			msg = QMessageBox()
			msg.setIcon(QMessageBox.Icon.Warning)
			msg.setText('Cannot delete Config since no other config is available')
			msg.setWindowTitle('Warning')
			msg.setStandardButtons(QMessageBox.StandardButton.Ok)
			msg.exec()
		else:
			if self.curConfig == self.configs.defaultconfig:
				bChangeDefaultConfig = True
			else:
				bChangeDefaultConfig = False
			self.lConfigs.remove(self.curConfig)
			self.curConfig = self.lConfigs[0]
			self.comboBox_selectconfig.removeItem(self.comboBox_selectconfig.currentIndex())
			self.comboBox_selectconfig.setCurrentText(self.curConfig)
			if bChangeDefaultConfig:
				self.configs.defaultconfig = self.curConfig
			self.configs.saveConfigfile(True)
		
	def pushButton_config_setasdefault_run(self):
		self.configs.defaultconfig = self.comboBox_selectconfig.currentText()
		self.configs.saveConfigfile()
	
	def buttonBox_okcancel_run(self, button):
		role = self.dlg.buttonBox_okcancel.standardButton(button)
		if role == QDialogButtonBox.Ok:
			self.configs.dCfgDbname[self.curConfig] = self.dlg.lineEdit_database.text()
			self.configs.dCfgSounddir[self.curConfig] = self.dlg.lineEdit_sounddir.text()
			self.configs.dCfgRandomplaylist[self.curConfig] = self.dlg.lineEdit_randomplaylist.text()
			self.configs.saveConfigfile()
			#self.comboBox_selectconfig_cfgchanged_t(0)

	def buttonBox_okcancel2_run(self, button):
		role = self.dlg.buttonBox_okcancel.standardButton(button)
		if role == QDialogButtonBox.Ok:
			cur_config = self.dlg.lineEdit_configname.text()
			self.configs.dCfgDbname[cur_config] = self.dlg.lineEdit_database.text()
			self.configs.dCfgSounddir[cur_config] = self.dlg.lineEdit_sounddir.text()
			self.configs.dCfgRandomplaylist[cur_config] = self.dlg.lineEdit_randomplaylist.text()
			# TODO: check if values are plausible
			if cur_config in self.lConfigs:
				print('config already exists: ' + cur_config + ' -> skipped')
				return
			elif os.path.exists(self.configs.dCfgDbname[cur_config]):
				print('DB already exists: ' + self.configs.dCfgDbname[cur_config] + ' -> skipped')
				return
			elif not os.path.exists(self.configs.dCfgSounddir[cur_config]):
				print('Sound directory not found: ' + self.configs.dCfgSounddir[cur_config] + ' -> skipped')
				return
			elif os.path.exists(self.configs.dCfgRandomplaylist[cur_config]):
				print('Playlist already exists: ' + self.configs.dCfgRandomplaylist[cur_config] + ' -> skipped')
				return
			else:
				self.lConfigs.append(cur_config)
				self.configs.saveConfigfile()
				if bDebug:
					print ('<config created>' + cur_config)

class AlbumPlayerDlg(QDialog):
	def __init__(self, main_window):
		super(AlbumPlayerDlg, self).__init__()
		self.main_window = main_window  # Reference to MainWindow
		
		self.setWindowTitle('Select Album')
		self.COVER_SIZE_ABP = 150
		self.PADDING = 15 # Puffer für Abstände zwischen den Buttons
		
		# Basis-Layout initialisieren
		self.scroll = QScrollArea(self)
		self.scroll.setWidgetResizable(True)
		self.content_widget = QWidget()
		self.grid = QGridLayout(self.content_widget)
		self.scroll.setWidget(self.content_widget)
		
		layout = QVBoxLayout(self)
		layout.addWidget(self.scroll)
		self.setLayout(layout)

		self.pbArray = [] # Liste, um die erstellten Buttons zu referenzieren
		
###		d_imagpaths = {}
		cmd = 'SELECT * FROM ALBUMS ORDER BY ARTIST ASC, ALBUM ASC;'
		try:
			conn = sqlite3.connect(self.main_window.db.dbname)
			self.cursor = conn.cursor()
			print('<SQL>' + cmd)
			self.cursor.execute(cmd)
###			conn.commit()
			album_table = self.cursor.fetchall() ### list of tuples !
			conn.close()
			nr_albums = len(album_table)
		except sqlite3.Error as e:
			ret_text += str(e)
			print(e)
			# sys.exit(-1)
			return
			
		if bDebug:
			print('<NR_ALBUMS> found '+ str(nr_albums) + ' albums')

		for i in range(0, nr_albums):
			pb = QPushButton()
			im = album_table[i][4]  # cover path
			album_name = album_table[i][2].replace('/', '_').replace('"','')  # album name
			artist_name = album_table[i][0].replace('/', '_').replace('"','')  # artist
			album_path = album_table[i][5] # fullpath

			pixmap = QPixmap()
			if os.path.exists(im):
				pixmap.load(im)
				
			if not pixmap.isNull():
				pixmap = pixmap.scaled(self.COVER_SIZE_ABP, self.COVER_SIZE_ABP, Qt.KeepAspectRatio, Qt.SmoothTransformation)
				ButtonIcon = QIcon(pixmap)
				pb.setIconSize(pixmap.rect().size())
				pb.setIcon(ButtonIcon)
			else:
				if bDebug:
					print('<E_IMAGE_NOT_FOUND>' + album_path + ' [maybe you should update the database]')
#				sys.exit(-1) # TODO: do not exit, but use a standard image instead .. or try to extract it from the songs of the album ... or write only the album/artist name on the button ...
				pb.setText(artist_name + '\n' + album_name)
				
			pb.setFixedSize(self.COVER_SIZE_ABP, self.COVER_SIZE_ABP)
			pb.clicked.connect(partial(self.on_album_button_clicked, album_name, artist_name, album_path))
			
			self.pbArray.append(pb)

		# Initiales Anordnen der Buttons ausführen
		self.rearrange_buttons()

	def resizeEvent(self, event):
		"""Wird automatisch von Qt aufgerufen, sobald das Fenster vergrößert/verkleinert wird."""
		super(AlbumPlayerDlg, self).resizeEvent(event)
		self.rearrange_buttons()

	def rearrange_buttons(self):
		"""Berechnet die Spaltenanzahl basierend auf der aktuellen Breite neu."""
		if not self.pbArray:
			return

		# Verfügbare Breite des Scroll-Inhalts abrufen (Abzug für die Scrollbar einplanen)
		available_width = self.scroll.viewport().width()
		
		# Berechnen, wie viele Buttons inklusive Puffer nebeneinander passen (mindestens 1)
		buttons_per_row = max(1, available_width // (self.COVER_SIZE_ABP + self.PADDING))

		# Alle Buttons aus dem Grid entfernen (ohne sie zu löschen)
		for i in reversed(range(self.grid.count())): 
			widget = self.grid.itemAt(i).widget()
			if widget is not None:
				self.grid.removeWidget(widget)

		# Buttons basierend auf der neuen Spaltenanzahl im Raster verteilen
		cur_x = 0
		cur_y = 0
		for pb in self.pbArray:
			self.grid.addWidget(pb, cur_x, cur_y)
			cur_y += 1
			if cur_y >= buttons_per_row:
				cur_y = 0
				cur_x += 1
				
	def on_album_button_clicked(self, album_name, artist_name, album_path):
		# print(f"Album clicked: {album_name} by {artist_name}")
		print('<on_album_button_clicked>Now playing album: ' + album_path)
		
		# TODO:
		# create playlist
		plgen = PlaylistGenerator()
		playlistfile = artist_name + '_' + album_name + '.m3u'
		plgen.genCompletePlaylistFromDirectory(album_path, playlistfile, False)

		# Set the playlist in MainWindow
		self.main_window.playlist = Utils.load_playlist_from_file(playlistfile)
		self.main_window.player.setPlaylist(self.main_window.playlist)
		self.main_window.player.play()

	# def load_playlist_from_file(self, playlistfile, playlist):
		# playlist.clear()
		# with open(playlistfile, 'r') as fin:
			# lines = fin.readlines()
			# fin.close()
			# for line in lines:
				# playlist.addMedia(QMediaContent(QUrl.fromLocalFile(line.strip())))

class ExcelFilterHeader(QtWidgets.QHeaderView):
	"""Erweiterter Tabellenkopf, der bei Klick das Excel-Filtermenü öffnet."""
	def __init__(self, orientation, parent=None):
		super().__init__(orientation, parent)
		self.setSectionsClickable(True)
		self.sectionClicked.connect(self.show_filter_menu)
		self.active_filters = {} # Speichert die ausgewählten Werte pro Spalte: {col_idx: {set_of_allowed_values}}

	def show_filter_menu(self, logical_index):
		# Das Proxy-Modell und das originale Modell holen
		proxy_model = self.parent().model()
		source_model = proxy_model.sourceModel()
		
		# Den Namen der angeklickten Spalte herausfinden (z.B. "Artist")
		col_name = source_model._headers[logical_index]
		
		# Den Namen der SQL-Tabelle herausfinden, indem wir prüfen, welches Modell aktiv ist
		# (Wir schauen, ob die Header-Länge zur Songs- oder Albums-Tabelle passt)
		if len(source_model._headers) > 6:
			db_table = "Songs"
		else:
			db_table = "Albums"
			
		# 1. OPTIMIERT: Eindeutige Werte blitzschnell direkt aus der Datenbank holen
		unique_values = set()
		try:
			import sqlite3
			# Verbindung zur DB des Hauptfensters aufbauen
			conn = sqlite3.connect(self.parent().parent().main_window.db.dbname)
			cursor = conn.cursor()
			
			# DISTINCT holt jeden Wert nur ein einziges Mal. ORDER BY sortiert es direkt.
			cmd = f"SELECT DISTINCT {col_name} FROM {db_table} ORDER BY {col_name} ASC;"
			cursor.execute(cmd)
			rows = cursor.fetchall()
			conn.close()
			
			for r in rows:
				val = str(r[0])
				unique_values.add(val if val.strip() else "(leer)")
		except Exception as e:
			print(f"Fehler beim schnellen DB-Filter-Laden: {e}")
			# Fallback: Falls SQL fehlschlägt, nutzen wir die alte Methode aus der Tabelle
			for row in range(source_model.rowCount(None)):
				val = str(source_model.index(row, logical_index).data())
				unique_values.add(val if val.strip() else "(leer)")
		
		sorted_values = sorted(list(unique_values))

		# 2. Das Popup-Menü erstellen
		menu = QMenu(self)
		menu.setStyleSheet("QMenu { background-color: #f0f0f0; border: 1px solid #999; }")

		# --- Sektion A: Sortierung ---
		act_asc = menu.addAction("▲ Aufsteigend sortieren")
		act_desc = menu.addAction("▼ Absteigend sortieren")
		menu.addSeparator()

		# --- Sektion B: Das Live-Suchfeld im Popup ---
		search_widget = QWidget()
		search_layout = QVBoxLayout(search_widget)
		search_le = QLineEdit()
		search_le.setPlaceholderText("Elemente suchen...")
		search_layout.addWidget(search_le)

		# --- Sektion C: Die Checkliste (QListWidget mit Checkboxes) ---
		list_widget = QListWidget()
		list_widget.setMaximumHeight(200)
		search_layout.addWidget(list_widget)

		# "Alle auswählen"-Checkbox voranstellen
		item_all = QListWidgetItem(list_widget)
		cb_all = QCheckBox(" Alle")
		cb_all.setChecked(logical_index not in self.active_filters)
		list_widget.setItemWidget(item_all, cb_all)

		# Die einzelnen Werte als Checkboxen hinzufügen
		checkbox_map = {}
		for val in sorted_values:
			item = QListWidgetItem(list_widget)
			cb = QCheckBox(f" {val}")
			
			# Zustand wiederherstellen (falls schon mal gefiltert wurde)
			if logical_index in self.active_filters:
				cb.setChecked(val in self.active_filters[logical_index])
			else:
				cb.setChecked(True)
				
			list_widget.setItemWidget(item, cb)
			checkbox_map[val] = cb

		# Suchfeld-Logik: Liste beim Tippen live filtern
		def filter_list_items(text):
			for val, cb in checkbox_map.items():
				# Suchtreffer anzeigen, den Rest verstecken
				for idx in range(list_widget.count()):
					it = list_widget.item(idx)
					w = list_widget.itemWidget(it)
					if w != cb_all:
						it.setHidden(text.lower() not in w.text().lower())

		search_le.textChanged.connect(filter_list_items)

		# "Alle"-Checkbox steuert alle Unter-Checkboxen
		def toggle_all(state):
			for cb in checkbox_map.values():
				cb.setChecked(state == Qt.Checked)
		cb_all.stateChanged.connect(toggle_all)

		# Das Layout in eine WidgetAction packen, damit es ins QMenu passt
		action_layout = QWidgetAction(menu)
		action_layout.setDefaultWidget(search_widget)
		menu.addAction(action_layout)

		# --- Sektion D: Die OK / Abbrechen Buttons ---
		btn_widget = QWidget()
		btn_layout = QHBoxLayout(btn_widget)
		btn_ok = QPushButton("OK")
		btn_cancel = QPushButton("Abbrechen")
		btn_layout.addWidget(btn_cancel)
		btn_layout.addWidget(btn_ok)
		
		action_btns = QWidgetAction(menu)
		action_btns.setDefaultWidget(btn_widget)
		menu.addAction(action_btns)

		# Button-Aktionen definieren
		btn_cancel.clicked.connect(menu.close)
		
		# Variable zur Speicherung des Klick-Ergebnisses
		self.menu_result = "cancel"
		def on_ok():
			self.menu_result = "ok"
			menu.close()
		btn_ok.clicked.connect(on_ok)

		# Menü exakt unter der angeklickten Spalte anzeigen
		header_pos = self.mapToGlobal(self.pos())
		section_pos = self.sectionPosition(logical_index)
		
		# Zeigt das Menü an und wartet, welche Action ausgelöst wurde
		selected_action = menu.exec_(header_pos + QPoint(section_pos, self.height()))

		# 3. Auswertung NACHDEM das Menü geschlossen wurde
		if selected_action == act_asc:
			proxy_model.sort(logical_index, Qt.AscendingOrder)
		elif selected_action == act_desc:
			proxy_model.sort(logical_index, Qt.DescendingOrder)
		elif self.menu_result == "ok":
			# Erlaubte Werte aus den Checkboxen sammeln
			allowed = set()
			for val, cb in checkbox_map.items():
				if cb.isChecked():
					allowed.add(val)

			if len(allowed) == len(sorted_values):
				# Alles ausgewählt -> Filter für diese Spalte entfernen
				self.active_filters.pop(logical_index, None)
			else:
				# Filter setzen
				self.active_filters[logical_index] = allowed

			# Zwingt das Proxy-Modell, die Tabelle JETZT live neu zu filtern
			proxy_model.invalidateFilter()

class CustomFilterProxyModel(QSortFilterProxyModel):
	"""Erweitertes Proxy-Modell, das komplexe Multi-Checkbox-Filter auswertet."""
	def __init__(self, parent=None):
		super().__init__(parent)
		self.header_view = None

	def filterAcceptsRow(self, source_row, source_parent):
		if not self.header_view or not self.header_view.active_filters:
			return True # Kein Filter aktiv -> Zeile anzeigen

		source_model = self.sourceModel()
		
		# Jede Spalte prüfen, ob ein Filter vorliegt
		for col_idx, allowed_values in self.header_view.active_filters.items():
			index = source_model.index(source_row, col_idx, source_parent)
			val = str(source_model.data(index, Qt.DisplayRole))
			if not val.strip():
				val = "(leer)"
				
			# Wenn der Wert der Zelle NICHT in den erlaubten Checkbox-Werten ist -> Zeile ausblenden
			if val not in allowed_values:
				return False
				
		return True

class TabWindow(QMainWindow):
	def __init__(self, headers1, data1, headers2, data2):
		super(TabWindow, self).__init__()
		self.setWindowTitle('My music Collection (Excel Autofilter Mode)')
		self.resize(1000, 700)

		tab_widget = QTabWidget(self)
		self.setCentralWidget(tab_widget)

		# ----------------------------------------------------
		# TAB 1: SONGS
		# ----------------------------------------------------
		model1 = TableModel(data1, headers1)
		self.proxy_model1 = CustomFilterProxyModel()
		self.proxy_model1.setSourceModel(model1)

		table_view1 = QTableView()
		header1 = ExcelFilterHeader(Qt.Horizontal, table_view1)
		table_view1.setHorizontalHeader(header1) # Setze den custom Excel-Header!
		header1.header_view = header1            # Zirkelbezug herstellen
		self.proxy_model1.header_view = header1  # Verbindung zum FilterModell herstellen
		
		table_view1.setModel(self.proxy_model1)
		table_view1.verticalHeader().hide()

		# ----------------------------------------------------
		# TAB 2: ALBUMS
		# ----------------------------------------------------
		model2 = TableModel(data2, headers2)
		self.proxy_model2 = CustomFilterProxyModel()
		self.proxy_model2.setSourceModel(model2)

		table_view2 = QTableView()
		header2 = ExcelFilterHeader(Qt.Horizontal, table_view2)
		table_view2.setHorizontalHeader(header2)
		self.proxy_model2.header_view = header2
		
		table_view2.setModel(self.proxy_model2)
		table_view2.verticalHeader().hide()

		# Tabs hinzufügen
		tab_widget.addTab(table_view1, 'Songs')
		tab_widget.addTab(table_view2, 'Albums')
		
class DB:		
	def __init__(self, dbname):
		self.dbname = dbname
		# Verbindung zur Datenbank herstellen
		self.conn = sqlite3.connect(self.dbname)
		# Cursor-Objekt (zum Zugriff auf die Datenbank)
		self.cursor = self.conn.cursor()
		self.conn.close()
		self.sqltext_dbg = ''
		
	def exec_sql(self, cmd, bCloseConn=True, bExitOnError = True, bSQLTest = False):
		ret_text = ''
		try:
			# Verbindung zur Datenbank herstellen
			self.conn = sqlite3.connect(self.dbname)
			# Cursor-Objekt (zum Zugriff auf die Datenbank)
			self.cursor = self.conn.cursor()
			if bDebugSQL:
				print('<SQL>' + cmd)
			self.sqltext_dbg += cmd + '\n'
			self.cursor.execute(cmd)
			self.conn.commit()
			if cmd.upper().startswith('SELECT') and bSQLTest:
				rows = self.cursor.fetchall()
				for r in rows:
					ret_text += str(r) + '\n'
			if bCloseConn:
				self.conn.close()
		except sqlite3.Error as e:
			ret_text += str(e)
			print(e)
			if bExitOnError:
				sys.exit(-1)
		return ret_text

	def createTables(self):
		sql = """DROP TABLE IF EXISTS Songs;"""
		self.exec_sql(sql)

		sql = """
		CREATE TABLE Songs 
		(
		TITLE VARCHAR(255), 
		ARTIST VARCHAR(255),
		ALBUMARTIST VARCHAR(255),
		ALBUM VARCHAR(255), 
		GENRE VARCHAR(255), 
		DURATION INTEGER,
		COVER_AVAIL INTEGER,
		TRACKNUMBER INTEGER,
		MYEAR INTEGER,
		CHANNELS INTEGER,
		BITRATEMODE VARCHAR(255),
		BITRATE INTEGER,
		RATING INTEGER,
		FULLPATH VARCHAR(2048)
		);"""
		
		self.exec_sql(sql)

		sql = """DROP TABLE IF EXISTS Albums;"""
		self.exec_sql(sql)

		sql = """
		CREATE TABLE Albums
		(
		ARTIST VARCHAR(255),
		ALBUM VARCHAR(255), 
		ALBUMARTIST VARCHAR(255), 
		GENRE VARCHAR(255), 
		COVER_PATH VARCHAR(1024),
		FULLPATH VARCHAR(2048)
		);"""

		self.exec_sql(sql)

		
	# def addline_tablesongs(self, title, artist, album, genre, duration, bCoverAvailable, tracknumber, year, channels, bitrate_mode, bitrate, rating, fullpath)
	def addline_tablesongs(self, data):
		sql  = 'INSERT INTO Songs VALUES(' ###+ data 
		# sql += '0, '  ### primary key !!!
		sql += '"' + data[0] + '", '   #title
		sql += '"' + data[1] + '", '   #artist
		sql += '"' + data[2] + '", '   #albumartist
		sql += '"' + data[3] + '", '   #album
		sql += '"' + data[4] + '", '   #genre
		sql += str(data[5])  + ', '    #duration
		sql += str(data[6])  + ', '    #bCoverAvailable
		sql += str(data[7])  + ', '    #tracknumber
		sql += str(data[8])  + ', '    #year
		sql += str(data[9])  + ', '    #channels
		sql += '"' + str(data[10])  + '", '    #bitrate_mode
		sql += str(data[11])  + ', '   #bitrate
		sql += str(data[12])  + ', '   #rating
		sql += '"' + data[13] + '"); ' #fullpath

		self.exec_sql(sql)
		
	def addline_tablealbums(self, data, coverpath):
		sql  = 'INSERT INTO Albums VALUES('
		# sql += '0, '  ### primary key !!!
		sql += '"' + data[1] + '", '   #artist
		sql += '"' + data[2] + '", '   #albumartist
		sql += '"' + data[3] + '", '   #album
		sql += '"' + data[4] + '", '   #genre
#		sql += str(data[5])  + ', '    #duration -> later
#		sql += str(data[6])  + ', '    #bCoverAvailable -> later
#		sql += str(data[8])  + ', '    #year -> later
#		sql += str(bIsSampler)  + ', '    #bIsSampler -> later ### how to detect ? special directory ? Artist<->Album Artist ?
		sql += '"' + coverpath + '", ' #path to coverart
		sql += '"' + os.path.dirname(data[13]) + '"); ' #fullpath
		# TODO: path to multi-CDs not possible in this way for AlbumButtonPlayer

		self.exec_sql(sql)
		
	def getTable(self, table):
		rows = []
		
		try:
			# Abfrage je nach Tabelle anpassen, um die Sortierung zu erzwingen
			if table.upper() == 'SONGS':
				# Sortiert die Song-Tabelle zuerst nach ARTIST, dann nach TITLE
				sql = 'SELECT * FROM Songs ORDER BY ARTIST ASC, TITLE ASC;'
			elif table.upper() == 'ALBUMS':
				# Sortiert die Album-Tabelle zuerst nach ARTIST, dann nach ALBUM
				sql = 'SELECT * FROM Albums ORDER BY ARTIST ASC, ALBUM ASC;'
			else:
				# Fallback für eventuelle andere Tabellen
				sql = 'SELECT * FROM ' + table + ';'

			self.exec_sql(sql, False)

			rows = self.cursor.fetchall()
			self.conn.close()
		except:
			if bDebug:
				print('<getTable>Error: ' + table + 'not found')
		
		return rows
		
	def getColValsFromDB(self, table, colname):
		retval = []
		try:
			sql = 'SELECT ' + colname + ' FROM ' + table
			self.exec_sql(sql, False)
			rows = self.cursor.fetchall()
			for r in rows:
				if not r[0] in retval:
					retval.append(r[0])
			self.conn.close()
		except:
			if bDebug:
				print('<getColValsFromDB>Error: ' + table + 'not found')
		
		if bDebug:
			print('<getColValsFromDB>' + str(retval))
			
		return retval
		
class Config:
	def __init__(self):
		# default values for test
		# if os.name == 'posix':
			# self.dbname         = 'sound.linux.db'
			# self.sounddir       = os.path.join('home', 'blju', 'Sound')
			# self.randomplaylist = 'playlist_random_cur_linux.m3u' 
		# else:
			# self.dbname         = 'sound.windows.db'
			# self.sounddir       = os.path.join('E:\\', '000_2025', 'MusicManager_sync_workspaces', 'MusicMgr', 'Sound')
			# self.randomplaylist = 'playlist_random_cur_windows.m3u'
		self.configfile = 'configs.cfg'
		self.lConfigs = []
		self.dCfgDbname = {}
		self.dCfgSounddir = {}
		self.dCfgRandomplaylist = {}
		self.defaultconfig = ''
		
	def readConfigfile(self):
		
		with open(self.configfile, 'r') as fin:
			lines = fin.readlines()
			fin.close()
		for l in lines:
			match0 = re.search(r'<defaultconfig>\s*(.+)\s*</defaultconfig>', l)
			match1 = re.search(r'<config>', l)
			match2 = re.search(r'<name>\s*(.+)\s*</name>', l)
			match3 = re.search(r'<dbname>\s*(.+)\s*</dbname>', l)
			match4 = re.search(r'<sounddir>\s*(.+)\s*</sounddir>', l)
			match5 = re.search(r'<randomplaylist>\s*(.+)\s*</randomplaylist>', l)
			match6 = re.search(r'</config>', l)
			if match0:
				self.defaultconfig = match0.group(1)
			elif match1:
				bConfigSectionActive = True
			elif match2:
				cur_config = match2.group(1)
				self.lConfigs.append(cur_config)
			elif match3:
				self.dCfgDbname[cur_config] = match3.group(1)
			elif match4:
				self.dCfgSounddir[cur_config] = match4.group(1)
			elif match5:
				self.dCfgRandomplaylist[cur_config] = match5.group(1)
			elif match6:
				bConfigSectionActive = False
				# config = ConfigItem(cur_config, cfg_dbname, cfg_sounddir, cfg_randomplaylist)
				# dConfigs.append(config)
		return self.lConfigs, self.defaultconfig
		
	def saveConfigfile(self, bWithBackup = False):
	# def saveConfigfile(self, defaultconfig, lConfigs):
		if bWithBackup:
			backupfile = os.path.join('bkup', self.configfile + '.bkup')
			shutil.copyfile(self.configfile, backupfile)
		text = ''
		text += '<defaultconfig>' + self.defaultconfig + '</defaultconfig>\n\n'
		for cfg in self.lConfigs:
			text += '<config>\n'
			text += '<name>' + cfg + '</name>\n'
			text += '<dbname>' + self.dCfgDbname[cfg] + '</dbname>\n'
			text += '<sounddir>' + self.dCfgSounddir[cfg] + '</sounddir>\n'
			text += '<randomplaylist>' + self.dCfgRandomplaylist[cfg] + '</randomplaylist>\n'
			text += '</config>\n\n'
		
		fout = open(self.configfile, 'w')
		fout.write(text)
		fout.close()

class Utils:
	def __init__(self):
		pass

	##############################################################################
	# helper function
	##############################################################################
	@staticmethod
	def load_playlist_from_file(playlistfile):
		playlist = QMediaPlaylist()
		# playlist.clear()
		with open(playlistfile, 'r') as fin:
			lines = fin.readlines()
			fin.close()
			for line in lines:
				playlist.addMedia(QMediaContent(QUrl.fromLocalFile(line.strip())))
		return playlist

if __name__ == '__main__':
	app = QtWidgets.QApplication(sys.argv)
	conf = Config()
	lConfigs, defaultconfig = conf.readConfigfile()
	window = MainWindow(conf, lConfigs, defaultconfig)
	window.show()
	sys.exit(app.exec_())

### use a global QMediaPlayer and QMediaPlaylist for MainWindow and AlbumPlayerDlg ?