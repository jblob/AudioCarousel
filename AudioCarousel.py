# Standard library imports
import glob
import os
import random
import re
import shutil
import sqlite3
import subprocess
import sys
from subprocess import Popen, PIPE, STDOUT
from functools import partial
from pathlib import Path
from dataclasses import dataclass
from pprint import pprint
# from typing import NamedTuple

# PyQt imports
from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import (
	Qt, QUrl, QSortFilterProxyModel, QPoint, QAbstractTableModel,
	pyqtRemoveInputHook # see comment below
)
from PyQt5.QtWidgets import (
	QAction, QApplication, QLabel, QMainWindow, QMenu, QDialog, QFileDialog,
	QStatusBar, QPushButton, QGridLayout, QScrollArea, QWidget, QVBoxLayout,
	QDialogButtonBox, QMessageBox, QTableView, QTabWidget, QStackedWidget,
	QComboBox, QWidgetAction, QCheckBox, QListWidget, QListWidgetItem, QHBoxLayout, QLineEdit
)
from PyQt5.QtMultimedia import (
	QMediaPlayer, QMediaContent, QMediaPlaylist, QMediaMetaData
)
from PyQt5.QtGui import (
	QPixmap, QIcon
)

# Third-party library imports
import mutagen
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC
from mutagen.mp3 import MP3, MPEGInfo
from mutagen.mp4 import MP4

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
			
	def genPlaylistFromDatabase(self, directory, outputfile, bRandom, db_path):
		"""
		Generiert eine Playlist basierend auf den in der Datenbank (Songs-Tabelle)
		gespeicherten Pfaden, gefiltert nach einem bestimmten Basis-Verzeichnis.
		"""
		# SQL-Query: Holt alle FULLPATHs aus Songs, die im gesuchten Verzeichnis liegen
		# Wir nutzen 'LIKE', um Unterverzeichnisse analog zu glob recursive zu erfassen
		cmd = "SELECT FULLPATH FROM Songs WHERE FULLPATH LIKE ? ORDER BY ARTIST ASC, TITLE ASC;"
		files = []
		
		try:
			conn = sqlite3.connect(db_path)
			cursor = conn.cursor()
			# Das % Zeichen dient als Wildcard für alle folgenden Zeichen (Unterordner/Dateien)
			cursor.execute(cmd, (directory + '%',))
			rows = cursor.fetchall()
			conn.close()
			
			# Tupel-Ergebnisse in eine flache Liste von Pfaden umwandeln
			files = [row[0] for row in rows]
		except sqlite3.Error as e:
			print(f"<genPlaylistFromDatabase> SQL-Fehler: {e}")
			return

		if bDebug:
			print('<genPlaylistFromDatabase><directory>' + str(directory))
			print('<genPlaylistFromDatabase><db_path>' + str(db_path))
			print('<genPlaylistFromDatabase><files_count>' + str(len(files)))
		
		# Falls bRandom aktiv ist, wird die Liste gemischt
		if bRandom:
			random.shuffle(files)
			
		text = ''
		for f in files:
			text += f + '\n'
			
		with open(outputfile, 'w', encoding='utf-8') as fout:
			fout.write(text)
			
		if bDebug:
			print(f'<genPlaylistFromDatabase> Playlist erfolgreich geschrieben: {outputfile}')
			
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
		self._headers = headers	 # Column headers
		
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
	def __init__(self):
		super(MainWindow, self).__init__()
		self.COVER_SIZE = 150
		uic.loadUi('MusicPlayerJB.ui', self)
#?		self.setFixedSize(1400,810)
		self.label_cover.setFixedSize(self.COVER_SIZE, self.COVER_SIZE)
		
		self.config = ConfigManager('configs.cfg')
		
		self.db				= None
		
		self.player_mode = self.buttonGroup.checkedButton().text() ### 'AlbumPlayer' # TODO: read this from config ?
		self.bAlbumSelected = False
		self.bPlaylistChanged = False

		self.player = QMediaPlayer()
		self.playlist = QMediaPlaylist()
		self.player.setVideoOutput(self.widget_videooutput)
		self.stackedWidget.setCurrentIndex(0)
		if bDebug:
			print('<MainWindow><Init>self.stackedWidget.setCurrentIndex(0)')
		

		pyqtRemoveInputHook() # otherwise no debugging with pdb possible :/
#		self.randomplayliststate = self.getPlaylistSavedState(self.config.active_profile.randomplaylist)
		self.label_cover.setStyleSheet('background-color: white;')

		# connect signals and slots
		self.connectSignalsAndSlots()
		
		self.statusBar = QStatusBar()
		self.verticalLayout_statusbar.addWidget(self.statusBar)
		self.statusBar.showMessage('------------------------------------')
		
		self.comboBox_selectconfig.blockSignals(True)
		self.comboBox_selectconfig.clear()
		self.comboBox_selectconfig.addItems(list(self.config.profiles.keys()))
		self.comboBox_selectconfig.setCurrentText(self.config.defaultconfig)
		self.comboBox_selectconfig.blockSignals(False)
		
		# load start config
		self.on_config_changed(self.config.defaultconfig)
		
	def connectSignalsAndSlots(self):
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
		self.player.error.connect(lambda err: print(f"<E> Player Error: {self.player.errorString()} (Code: {err})"))
		self.playlist.currentIndexChanged.connect(self.slotIndexChanged)
		self.playlist.currentMediaChanged.connect(self.slotMetaDataChanged)
		self.comboBox_selectconfig.currentTextChanged.connect(self.on_config_changed) # change config "on the fly"
		
	def on_config_changed(self, profile_name):
		"""Wird aufgerufen, sobald der Benutzer in der ComboBox ein anderes Profil wählt."""
		if not profile_name or profile_name not in self.config.profiles:
			return

		# 1. Aktive config im ConfigManager setzen
		self.config.activeProfile = profile_name
		prof = self.config.active_profile

		# 2. Alte DB-Verbindung sicher schließen (falls vorhanden)
		if hasattr(self, 'db') and self.db and hasattr(self.db, 'conn') and self.db.conn:
			try:
				self.db.conn.close()
			except Exception:
				pass

		# 3. Neue DB mit den Pfaden des neuen Profils öffnen
		self.db = DB(prof.dbname)

		# 4. GUI-Listen/Auswahlfelder (Genres, Artists) neu aus der neuen DB befüllen
		self.updateListViews()

		if bDebug:
			print(f'<MainWindow> Config erfolgreich auf "{prof.name}" gewechselt.')
			print(f'			 DB: {prof.dbname} | SoundDir: {prof.sounddir}')

	def slot_modechanged(self, obj, checked):
		# 'checked' ist True für den neu aktivierten Button
		if not checked:
			return

		self.player_mode = obj.text()
		if bDebug:
			print('<slot_modechanged>mode changed to: ' + self.player_mode)

		if self.player_mode == 'RandomPlayer':
			# 1. Aktuelles Album / Player stoppen
			self.player.stop()

			# 2. Random-Playlist neu aus Datei laden & Signal-Verbindung erhalten
			self.playlist.clear()
			random_pl = Utils.load_playlist_from_file(self.config.active_profile.randomplaylist)
			for i in range(random_pl.mediaCount()):
				self.playlist.addMedia(random_pl.media(i))

			# 3. Sicherstellen, dass die Playlist am Player zugewiesen ist
			if self.player.playlist() != self.playlist:
				self.player.setPlaylist(self.playlist)

			# 4. Gespeicherten Index abrufen und starten
			saved_idx = self.getPlaylistSavedState(self.config.active_profile.randomplaylist)
			if saved_idx >= self.playlist.mediaCount() or saved_idx < 0:
				saved_idx = 0

			self.playlist.setCurrentIndex(saved_idx)
			self.player.play()
		
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
					self.playlist = Utils.load_playlist_from_file(self.config.active_profile.randomplaylist)
					
					self.listWidget_randomplaylist.clear()
					if os.path.exists(self.config.active_profile.randomplaylist):
						with open(self.config.active_profile.randomplaylist, 'r') as fin:
							for line in fin:
								if line.strip():
									self.listWidget_randomplaylist.addItem(line.strip())
				
				# WICHTIG f. Neustart: Zuerst die Playlist an den Player binden...
				if self.player.playlist() != self.playlist:
					self.player.setPlaylist(self.playlist)

				# Index aus dem gespeicherten Zustand holen
				saved_idx = self.getPlaylistSavedState(self.config.active_profile.randomplaylist)
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
				self.load_playlist_from_file(self.config.active_profile.randomplaylist, self.playlist)
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
			self.load_playlist_from_file(self.config.active_profile.randomplaylist, self.playlist)
			with open(self.config.active_profile.randomplaylist, 'r') as fin:
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
		# plgen.genCompletePlaylistFromDirectory(d, self.config.active_profile.randomplaylist, True)

		#plgen.genCompletePlaylistFromDirectory(self.config.active_profile, self.config.active_profile.randomplaylist, True)

		plgen.genPlaylistFromDatabase(self.config.active_profile.sounddir, self.config.active_profile.randomplaylist, True, self.db.dbname)

		self.playlist.setCurrentIndex(0)
		self.savePlaylistState(self.playlist, self.config.active_profile.randomplaylist)
		self.bPlaylistChanged = True
		
	def pushButton_randomplaylist_stop_run(self):
		self.player.stop()
		self.savePlaylistState(self.playlist, self.config.active_profile.randomplaylist)
		
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
		self.savePlaylistState(self.playlist, self.config.active_profile.randomplaylist)
		  
	def pushButton_randomplaylist_next_run(self):
		# method for moving to next track
		self.playlist.next()
		if self.playlist.currentIndex() == -1:
			self.playlist.setCurrentIndex(0)
			self.player.play()
		self.savePlaylistState(self.playlist, self.config.active_profile.randomplaylist)

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
		
		if bDebug:
			print('<slotMetaDataChanged>slotMetaDataChanged called')

		current_media = self.player.currentMedia()
		current_file = current_media.canonicalUrl().toLocalFile()
		
		if not current_file or not os.path.exists(current_file):
			return

		# 1. MP4 / Video-Handling
		if current_file.lower().endswith('.mp4'):
			# Videoausgabe auf das Video-Widget leiten
			self.player.setVideoOutput(self.widget_videooutput)
			# Auf Video-Seite im StackedWidget umschalten (Index 1)
			self.stackedWidget.setCurrentIndex(1)
			self.statusBar.showMessage(f"playing video: {os.path.basename(current_file)}")
			self.savePlaylistState(self.playlist, self.config.active_profile.randomplaylist)
			return

		# 2. Standard MP3-Handling
		# Videoausgabe wieder lösen / zurück zur Cover-Ansicht (Index 0)
		self.stackedWidget.setCurrentIndex(0)
		
		try:
			# Metadaten direkt & zuverlässig per Mutagen laden
			m = MP3Data()
			tags = m.getTagsFromFile(current_file)
			
			# Labels setzen
			self.label_artist_2.setText(m.artist or '<unknown>')
			self.label_title_2.setText(m.title or '<unknown>')
			self.label_album_2.setText(m.album or '<unknown>')
			self.label_genre_2.setText(str(m.genre) or '<unknown>')
			self.label_year_2.setText(str(m.year) or '<unknown>')
			self.statusBar.showMessage(f"playing: {m.title} - {m.artist}")

			# Embedded Cover per Mutagen auslesen
			audio = MP3(current_file, ID3=ID3)
			cover_found = False
			
			if audio.tags is not None:
				for tag in audio.tags.values():
					if isinstance(tag, APIC):  # Embedded Picture
						pixmap = QPixmap()
						if pixmap.loadFromData(tag.data):
							pixmap = pixmap.scaled(self.COVER_SIZE, self.COVER_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
							self.label_cover.setPixmap(pixmap)
							cover_found = True
							break

			if not cover_found:
				self.label_cover.clear()

		except Exception as e:
			print(f"<E> Fehler beim Laden des Covers: {e}")
			self.label_cover.clear()
			
		self.savePlaylistState(self.playlist, self.config.active_profile.randomplaylist)
	
	def slotIndexChanged(self):
		idx = self.playlist.currentIndex()
		if idx >= 0:
			self.listWidget_randomplaylist.setCurrentRow(idx)
			self.savePlaylistState(self.playlist, self.config.active_profile.randomplaylist)

	def closeEvent(self, event):
		self.savePlaylistState(self.playlist, self.config.active_profile.randomplaylist)
		self.db.conn.close()
	
	def pushButton_database_updateDB_run(self):
		# Thread filling the DB
		lAllAlbums = []
		files = glob.glob(self.config.active_profile.sounddir + '/**/*.mp?', recursive=True) ### mp4 not supported by mutagen :( -> TODO: search for another lib
		nFilesToProceed = len(files) # for progress bar
		self.db.createTables()
		error_log = []
		if bDebug:
			print('=============================================================')
			print('[Updating DB] started')
			
		# Verbindung explizit VOR der Schleife öffnen und Transaktion starten ---
		self.db.conn = sqlite3.connect(self.db.dbname)
		self.db.cursor = self.db.conn.cursor()
		self.db.cursor.execute("BEGIN TRANSACTION;") # Beschleunigt SQLite massiv

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
			
			# Trägt die Zeile in den Speicher ein, schreibt aber noch nicht auf die Disk
			self.db.addline_tablesongs(arrMp3Data)
			
			# --- Validierung der Tags laut Vorgabe ---
			title = arrMp3Data[0].strip()
			artist = arrMp3Data[1].strip()
			albumartist = arrMp3Data[2].strip()
			album = arrMp3Data[3].strip()
			genre = arrMp3Data[4].strip()
			cover_avail = arrMp3Data[6]
			
			is_sampler = albumartist.lower() == "various" or "_sampler" in os.path.split(curfile)[0].lower() or "_sampler" in curfile.lower()
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

			# WICHTIG: MP4-Dateien komplett für den Album Button Player ignorieren
			if is_mp4:
				continue

			# Bestimmung des eindeutigen Alben-Schlüssels (album_identifier)
			clean_album = album.strip()
			clean_artist = artist.strip()
			clean_albumartist = albumartist.strip()

			if clean_albumartist.lower() == "various":
				# Für Sampler nehmen wir immer "Various" + Albumname als Schlüssel
				album_identifier = ("Various", clean_album)
			else:
				# Für Nicht-Sampler nehmen wir den echten Artist + Albumname (da AlbumArtist selten gesetzt ist)
				album_identifier = (clean_artist, clean_album)
				
			if not album_identifier in lAllAlbums:
				lAllAlbums.append(album_identifier)
				imagename = 'NoImage'
				if bRegenerateAlbumImages:
					imagename = m.getImage(curfile)
				self.db.addline_tablealbums(arrMp3Data, imagename)
				
		# --- NEU: Nach der Schleife ALLES auf einmal speichern und Verbindung schließen ---
		self.db.conn.commit()
		self.db.conn.close()
		self.db.conn = None # Zurücksetzen
		# ---------------------------------------------------------------------------------

		# Fehlerprotokoll in Datei schreiben (Ihr bestehender Code)
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
		self.tab_window = TabWindow(headers1, data1, headers2, data2, self.db.dbname)
		self.tab_window.show()

	def pushButton_testsqlquery_run(self):
		cmd = self.lineEdit_testsqlquery.text()
		res = self.db.exec_sql(cmd, True, False, True)
		self.textBrowser_testsqlquery.setText(res)
		
	def pushButton_albumplayer_playalbum_run(self):
		self.apd = AlbumPlayerDlg(self)	 # Pass MainWindow instance
		# self.apd.exec_() ### modal dialog
		self.apd.show() ### non-modal dialog
		self.bAlbumSelected = True
		
	def pushButton_config_editconfig_run(self):
		self.dlg = QDialog(self)
		uic.loadUi('Dlg_editConfig.ui', self.dlg)
		self.dlg.lineEdit_configname.setReadOnly(True)
		self.dlg.buttonBox_okcancel.clicked.connect(self.buttonBox_okcancel_run)
		self.dlg.lineEdit_configname.setText(self.config.active_profile.name)
		self.dlg.lineEdit_database.setText(self.config.active_profile.dbname)
		self.dlg.lineEdit_sounddir.setText(self.config.active_profile.sounddir)
		self.dlg.lineEdit_randomplaylist.setText(self.config.active_profile.randomplaylist)
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
		if len(self.config.profiles) < 2:
			msg = QMessageBox()
			msg.setIcon(QMessageBox.Icon.Warning)
			msg.setText('Cannot delete Config since no other config is available')
			msg.setWindowTitle('Warning')
			msg.setStandardButtons(QMessageBox.StandardButton.Ok)
			msg.exec()
		else:
			self.config.delete_profile(self.config.active_profile.name)
			self.comboBox_selectconfig.removeItem(self.comboBox_selectconfig.currentIndex())

			self.comboBox_selectconfig.setCurrentText(self.config.active_profile)
			# self.configs.saveConfigfile(True)
		
	def pushButton_config_setasdefault_run(self):
		self.config.defaultconfig = self.config.active_profile
		self.config.saveConfigfile()
	
	def buttonBox_okcancel_run(self, button):
		role = self.dlg.buttonBox_okcancel.standardButton(button)
		if role == QDialogButtonBox.Ok:
			prof = self.config.active_profile
			prof.dbname = self.dlg.lineEdit_database.text()
			prof.sounddir = self.dlg.lineEdit_sounddir.text()
			prof.randomplaylist = self.dlg.lineEdit_randomplaylist.text()
			self.config.saveConfigfile()
			self.on_config_changed(prof.name)

	def buttonBox_okcancel2_run(self, button):
		role = self.dlg.buttonBox_okcancel.standardButton(button)
		if role == QDialogButtonBox.Ok:
			new_name = self.dlg.lineEdit_configname.text().strip()
			if new_name in self.config.profiles:
				print(f'Config {new_name} already exists')
				return
				
			new_profile = Config(
				name=new_name,
				dbname=self.dlg.lineEdit_database.text(),
				sounddir=self.dlg.lineEdit_sounddir.text(),
				randomplaylist=self.dlg.lineEdit_randomplaylist.text()
			)
			
			self.config.add_or_update_profile(new_profile)
			self.comboBox_selectconfig.addItem(new_name)
			self.comboBox_selectconfig.setCurrentText(new_name) # triggers on_config_changed !
			
			if bDebug:
				print ('<config created>' + new_name)

class AlbumPlayerDlg(QDialog):
	def __init__(self, main_window):
		super(AlbumPlayerDlg, self).__init__()
		self.main_window = main_window
		
		self.setWindowTitle('CD Alben & Karussell')
		self.resize(900, 450) # Dimensionen leicht angepasst
		self.COVER_SIZE_ACTIVE = 200
		self.COVER_SIZE_SMALL = 130
		self.GRID_COVER_SIZE = 140 # Feste Größe für die Grid-Ansicht
		self.PADDING = 15
		
		# --- Hauptlayout ---
		self.main_layout = QVBoxLayout(self)
		
		# --- 1. Steuerungszeile oben (Suche + Ansichts-Umschalter) ---
		self.top_bar_layout = QHBoxLayout()
		
		self.search_le = QLineEdit(self)
		self.search_le.setPlaceholderText("Nach Künstler, Album oder Genre filtern...")
		self.search_le.setStyleSheet("QLineEdit { padding: 8px; font-size: 14px; border-radius: 4px; }")
		self.search_le.textChanged.connect(self.on_search_changed)
		self.top_bar_layout.addWidget(self.search_le)
		
		# Der Umschalt-Button
		self.view_toggle_btn = QPushButton("≡ Grid-Ansicht", self)
		self.view_toggle_btn.setStyleSheet("QPushButton { padding: 8px 12px; font-weight: bold; }")
		self.view_toggle_btn.clicked.connect(self.toggle_view)
		self.top_bar_layout.addWidget(self.view_toggle_btn)
		
		self.main_layout.addLayout(self.top_bar_layout)
		
		# --- 2. Das QStackedWidget als Container für beide Ansichten ---
		self.stacked_widget = QStackedWidget(self)
		self.main_layout.addWidget(self.stacked_widget)
		
		# --- ANSICHT 1: Das Karussell (Index 0) ---
		self.carousel_scroll = QScrollArea(self)
		self.carousel_scroll.setWidgetResizable(True)
		self.carousel_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
		self.carousel_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
		self.carousel_scroll.horizontalScrollBar().valueChanged.connect(self.update_carousel_effects)
		
		self.carousel_content = QWidget()
		self.carousel_layout = QHBoxLayout(self.carousel_content)
		self.carousel_layout.setAlignment(Qt.AlignCenter)
		self.carousel_layout.addStretch(1) # Rechter Spacer für Zentrierung
		
		self.carousel_scroll.setWidget(self.carousel_content)
		self.stacked_widget.addWidget(self.carousel_scroll) # Hinzufügen zum Stack
		
		# --- ANSICHT 2: Das klassische Grid (Index 1) ---
		self.grid_scroll = QScrollArea(self)
		self.grid_scroll.setWidgetResizable(True)
		self.grid_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
		self.grid_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
		
		self.grid_content = QWidget()
		self.grid_layout = QGridLayout(self.grid_content)
		self.grid_layout.setSpacing(10)
		
		self.grid_scroll.setWidget(self.grid_content)
		self.stacked_widget.addWidget(self.grid_scroll) # Hinzufügen zum Stack
		
		# Datenstrukturen
		self.all_albums_data = []
		self.load_data_from_db()
		
		# Standardmäßig starten wir im Karussell-Modus
		self.stacked_widget.setCurrentIndex(0)
		self.update_carousel_effects()
		
	def load_data_from_db(self):
		cmd = 'SELECT ARTIST, ALBUM, GENRE, COVER_PATH, FULLPATH FROM ALBUMS ORDER BY ARTIST ASC, ALBUM ASC;'
		try:
			conn = sqlite3.connect(self.main_window.db.dbname)
			cursor = conn.cursor()
			cursor.execute(cmd)
			album_table = cursor.fetchall()
			conn.close()
		except sqlite3.Error as e:
			print(f"SQL-Fehler im Karussell: {e}")
			return
			
		for row in album_table:
			artist_name = row[0].replace('/', '_').replace('"','')
			album_name = row[1].replace('/', '_').replace('"','')
			genre_name = row[2] if row[2] else ""
			im_path = row[3]
			album_path = row[4]
			
			# Wir erstellen für jedes Album ZWEI Buttons – einen fürs Karussell, einen fürs Grid
			pixmap = QPixmap()
			if os.path.exists(im_path):
				pixmap.load(im_path)
			
			fallback_text = f"{artist_name}\n\n{album_name}"
			click_callback = partial(self.on_album_button_clicked, album_name, artist_name, album_path)
			
			# 1. Karussell-Button vorbereiten
			pb_carousel = QPushButton()
			pb_carousel.setFixedSize(self.COVER_SIZE_ACTIVE, self.COVER_SIZE_ACTIVE)
			pb_carousel.original_pixmap = pixmap if not pixmap.isNull() else None
			pb_carousel.fallback_text = fallback_text
			pb_carousel.clicked.connect(click_callback)
			
			# 2. Grid-Button vorbereiten (bisheriger Ansatz)
			pb_grid = QPushButton()
			pb_grid.setFixedSize(self.GRID_COVER_SIZE, self.GRID_COVER_SIZE)
			if not pixmap.isNull():
				scaled_grid = pixmap.scaled(self.GRID_COVER_SIZE, self.GRID_COVER_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
				pb_grid.setIcon(QIcon(scaled_grid))
				pb_grid.setIconSize(scaled_grid.rect().size())
				pb_grid.setStyleSheet("QPushButton { border: 1px solid #555; background: #000; } QPushButton:hover { border-color: #fff; }")
			else:
				pb_grid.setText(fallback_text)
				pb_grid.setStyleSheet("QPushButton { background-color: #333; color: white; font-size: 10px; }")
			pb_grid.clicked.connect(click_callback)
			
			# In zentraler Liste erfassen
			self.all_albums_data.append({
				'artist': artist_name,
				'album': album_name,
				'genre': genre_name,
				'path': album_path,
				'widget_carousel': pb_carousel,
				'widget_grid': pb_grid
			})
			
		# Initiales Rendern beider Ansichten
		self.render_views()

	def render_views(self):
		"""Baut das HTML/Widget-Layout für beide Ansichten basierend auf den gefilterten Daten auf."""
		# 1. Layouts leeren (Spacer und Widgets entfernen)
		while self.carousel_layout.count() > 1: # Behalte den letzten Stretch
			widget = self.carousel_layout.takeAt(0).widget()
			if widget: widget.setParent(None)
			
		while self.grid_layout.count() > 0:
			widget = self.grid_layout.takeAt(0).widget()
			if widget: widget.setParent(None)
			
		# 2. Widgets neu einfügen (nur sichtbare Treffer)
		grid_column = 0
		grid_row = 0
		max_columns = 5 # Wie viele Alben nebeneinander im Grid?
		
		search_term = self.search_le.text().lower().strip()
		
		for album in self.all_albums_data:
			# Filter-Logik
			match = (search_term in album['artist'].lower() or 
					 search_term in album['album'].lower() or 
					 search_term in album['genre'].lower())
			
			if match:
				# Ins Karussell einfügen
				self.carousel_layout.insertWidget(self.carousel_layout.count() - 1, album['widget_carousel'])
				album['widget_carousel'].show()
				
				# Ins Grid einfügen
				self.grid_layout.addWidget(album['widget_grid'], grid_row, grid_column)
				album['widget_grid'].show()
				
				grid_column += 1
				if grid_column >= max_columns:
					grid_column = 0
					grid_row += 1
			else:
				album['widget_carousel'].hide()
				album['widget_grid'].hide()
				
		self.update_carousel_effects()

	def toggle_view(self):
		"""Wechselt zwischen Karussell (0) und Grid (1) hin und her."""
		if self.stacked_widget.currentIndex() == 0:
			self.stacked_widget.setCurrentIndex(1)
			self.view_toggle_btn.setText("🎠 Karussell-Ansicht")
		else:
			self.stacked_widget.setCurrentIndex(0)
			self.view_toggle_btn.setText("≡ Grid-Ansicht")
			self.update_carousel_effects() # Effekte neu berechnen beim Zurückwechseln

	def update_carousel_effects(self):
		"""Berechnet Karussell-Effekte (nur aktiv im Karussell-Modus)."""
		if self.stacked_widget.currentIndex() != 0:
			return
			
		view_width = self.carousel_scroll.viewport().width()
		center_x = view_width / 2
		
		for album in self.all_albums_data:
			widget = album['widget_carousel']
			if not widget.isVisible() or widget.parent() is None:
				continue
				
			widget_pos = widget.mapTo(self.carousel_scroll.viewport(), QPoint(0, 0))
			widget_center_x = widget_pos.x() + (widget.width() / 2)
			
			distance = abs(center_x - widget_center_x)
			max_distance = 250.0
			factor = max(0.0, min(1.0, distance / max_distance))
			
			current_size = int(self.COVER_SIZE_ACTIVE - (factor * (self.COVER_SIZE_ACTIVE - self.COVER_SIZE_SMALL)))
			widget.setFixedSize(current_size, current_size)
			
			if widget.original_pixmap:
				scaled_pixmap = widget.original_pixmap.scaled(current_size - 10, current_size - 10, Qt.KeepAspectRatio, Qt.SmoothTransformation)
				widget.setIcon(QIcon(scaled_pixmap))
				widget.setIconSize(scaled_pixmap.rect().size())
				
				if factor < 0.3:
					widget.setStyleSheet("QPushButton { border: 3px solid #ffffff; background: #000; }")
				else:
					widget.setStyleSheet("QPushButton { border: 2px solid #444444; background: #000; }")
			else:
				widget.setText(widget.fallback_text if current_size > 140 else "...")
				widget.setStyleSheet(f"QPushButton { background-color: #222; color: #888; font-size: {max(8, int(10 - factor*2))}px; }")

	def on_search_changed(self, text):
		# Beim Tippen bauen wir einfach beide Ansichten gefiltert neu auf
		self.render_views()

	def resizeEvent(self, event):
		super(AlbumPlayerDlg, self).resizeEvent(event)
		self.update_carousel_effects()

	def on_album_button_clicked(self, album_name, artist_name, album_path):
		print('<on_album_button_clicked> Spiele Album: ' + album_path)
		plgen = PlaylistGenerator()
		playlistfile = artist_name + '_' + album_name + '.m3u'

		# plgen.genCompletePlaylistFromDirectory(album_path, playlistfile, False)
		plgen.genPlaylistFromDatabase(album_path, playlistfile, False, self.main_window.db.dbname)

		new_playlist = Utils.load_playlist_from_file(playlistfile)
		self.main_window.playlist.clear()
		
		for i in range(new_playlist.mediaCount()):
			self.main_window.playlist.addMedia(new_playlist.media(i))
			
		if self.main_window.player.playlist() != self.main_window.playlist:
			self.main_window.player.setPlaylist(self.main_window.playlist)
			
		self.main_window.playlist.setCurrentIndex(0)
			
		self.main_window.player.play()
		self.accept()

class ExcelFilterHeader(QtWidgets.QHeaderView):
	"""Erweiterter Tabellenkopf, der bei Klick das Excel-Filtermenü öffnet."""
	def __init__(self, orientation, dbname, parent=None):
		super().__init__(orientation, parent)
		self.setSectionsClickable(True)
		self.sectionClicked.connect(self.show_filter_menu)
		self.active_filters = {} # Speichert die ausgewählten Werte pro Spalte: {col_idx: {set_of_allowed_values}}
		self.dbname = dbname

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
			conn = sqlite3.connect(self.dbname)
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
		# NEU: Wir speichern hier direkt das Tupel (Checkbox, Item) für den Blitz-Zugriff
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
			checkbox_map[val] = (cb, item)	# <-- Hier das Item mitspeichern!

		# Suchfeld-Logik: Liste beim Tippen live filtern (Jetzt in O(N) statt O(N²))
		def filter_list_items(text):
			text_lower = text.lower().strip()
			
			# Blockiert GUI-Updates während des Filterns für zusätzliche Performance
			list_widget.setUpdatesEnabled(False)
			try:
				for val, (cb, item) in checkbox_map.items():
					# Direktes Verstecken des Listenelements ohne verschachtelte Schleife
					item.setHidden(text_lower not in val.lower())
			finally:
				list_widget.setUpdatesEnabled(True)

		search_le.textChanged.connect(filter_list_items)

		# "Alle"-Checkbox steuert alle Unter-Checkboxen
		def toggle_all(state):
			for cb, item in checkbox_map.values():
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
			for val, (cb, item) in checkbox_map.items():
				if cb.isChecked():
					allowed.add(val)

			# --- KORREKTUR: Layout-Änderung signalisieren ---
			proxy_model.layoutAboutToBeChanged.emit()

			if len(allowed) == len(sorted_values):
				# Alles ausgewählt -> Filter für diese Spalte entfernen
				self.active_filters.pop(logical_index, None)
			else:
				# Filter setzen
				self.active_filters[logical_index] = allowed

			# Zwingt das Proxy-Modell, den Filter neu auszuwerten
			proxy_model.invalidateFilter()
			
			# --- KORREKTUR: Ansicht zum Refresh zwingen ---
			proxy_model.layoutChanged.emit()
			
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
	def __init__(self, headers1, data1, headers2, data2, dbname):
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
		header1 = ExcelFilterHeader(Qt.Horizontal, dbname, table_view1)
		table_view1.setHorizontalHeader(header1) # Setze den custom Excel-Header!
		header1.header_view = header1			 # Zirkelbezug herstellen
		self.proxy_model1.header_view = header1	 # Verbindung zum FilterModell herstellen
		
		table_view1.setModel(self.proxy_model1)
		table_view1.verticalHeader().hide()

		# ----------------------------------------------------
		# TAB 2: ALBUMS
		# ----------------------------------------------------
		model2 = TableModel(data2, headers2)
		self.proxy_model2 = CustomFilterProxyModel()
		self.proxy_model2.setSourceModel(model2)

		table_view2 = QTableView()
		header2 = ExcelFilterHeader(Qt.Horizontal, dbname, table_view2)
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
		
	def exec_sql(self, cmd, bCloseConn=True, bExitOnError = True, bSQLTest = False, bCommit=True):
		ret_text = ''
		try:
			# Nur verbinden, wenn nicht bereits eine Verbindung offen ist
			if not hasattr(self, 'conn') or self.conn is None or bCloseConn:
				self.conn = sqlite3.connect(self.dbname)
				# Cursor-Objekt (zum Zugriff auf die Datenbank)
				self.cursor = self.conn.cursor()
				
			if bDebugSQL:
				print('<SQL>' + cmd)
			self.sqltext_dbg += cmd + '\n'
			self.cursor.execute(cmd)
			
			# Commit nur ausführen, wenn gewünscht (wichtig für Transaktionen!)
			if bCommit:
				self.conn.commit()
				
			if cmd.upper().startswith('SELECT') and bSQLTest:
				rows = self.cursor.fetchall()
				for r in rows:
					ret_text += str(r) + '\n'
					
			if bCloseConn:
				self.conn.close()
				self.conn = None
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
		sql = 'INSERT INTO Songs VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);'
		
		# Hilfsfunktion, um Strings wie '12/01' oder korrupte Werte sicher in int zu wandeln
		def safe_int(val):
			try:
				if isinstance(val, str) and '/' in val:
					val = val.split('/')[0] # Schneidet alles nach dem / ab
				return int(val)
			except (ValueError, TypeError):
				return 0 # Fallback, falls der Tag leer oder unlesbar ist

		# Sichere Konvertierung der Felder 5, 6, 7, 9, 11 und 12
		val_5  = safe_int(data[5])
		val_6  = safe_int(data[6])
		val_7  = safe_int(data[7])
		val_9  = safe_int(data[9])
		val_11 = safe_int(data[11])
		val_12 = safe_int(data[12])

		try:
			self.cursor.execute(sql, (
				data[0], data[1], data[2], data[3], data[4], 
				val_5, val_6, val_7, str(data[8]), 
				val_9, str(data[10]), val_11, val_12, data[13]
			))
		except sqlite3.Error as e:
			print(f"Fehler bei Songs-Insert ({data[0]}): {e}")
			
	def addline_tablealbums(self, data, coverpath):
		# Verwende ? Platzhalter für alle 6 Felder
		sql = 'INSERT INTO Albums VALUES(?, ?, ?, ?, ?, ?);'
		
		# data[13] ist der Fullpath der Spieldatei, os.path.dirname holt den Ordnerpfad
		folder_path = os.path.dirname(data[13])
		
		try:
			self.cursor.execute(sql, (
				data[1],	   # artist
				data[2],	   # albumartist
				data[3],	   # album
				data[4],	   # genre
				coverpath,	   # path to coverart
				folder_path	   # fullpath
			))
		except sqlite3.Error as e:
			print(f"Fehler bei Album-Insert ({data[3]}): {e}")
			
	def getTable(self, table):
		rows = []
		
		try:
			# Abfrage je nach Tabelle anpassen, um die Sortierung zu erzwingen
			if table.upper() == 'SONGS':
				sql = 'SELECT * FROM Songs ORDER BY ARTIST ASC, TITLE ASC;'
			elif table.upper() == 'ALBUMS':
				sql = 'SELECT * FROM Albums ORDER BY ARTIST ASC, ALBUM ASC;'
			else:
				sql = 'SELECT * FROM ' + table + ';'

			# --- ÄNDERUNG: Lokale Verbindung öffnen statt globaler Instanzvariablen ---
			# Nutzt das 'with'-Statement von sqlite3, das die Verbindung garantiert schließt
			with sqlite3.connect(self.dbname) as conn:
				local_cursor = conn.cursor()
				local_cursor.execute(sql)
				rows = local_cursor.fetchall()
				
		except sqlite3.Error as e: # Besser als ein nacktes except, um echte SQL-Fehler zu sehen
			if bDebug:
				print(f'<getTable> Error reading table {table}: {e}')
		
		return rows
		
	def getColValsFromDB(self, table, colname):
		retval = []
		sql = f"SELECT DISTINCT {colname} FROM {table} WHERE {colname} IS NOT NULL AND {colname} != '' ORDER BY {colname} ASC;"
		
		try:
			# Nutzung eines Kontext-Managers (with), damit die Verbindung/der Cursor sauber verwaltet wird
			with sqlite3.connect(self.dbname) as conn:
				cursor = conn.cursor()
				cursor.execute(sql)
				rows = cursor.fetchall()
				# Flache Liste aus den Ergebnissen erstellen
				retval = [r[0] for r in rows if r[0]]
		except sqlite3.Error as e:
			if bDebug:
				print(f'<getColValsFromDB> Fehler bei Tabelle {table}, Spalte {colname}: {e}')
				
		if bDebug:
			print(f'<getColValsFromDB> {table}.{colname} -> {len(retval)} Einträge geladen.')
			
		return retval
	
@dataclass
class Config:
	name: str
	dbname: str
	sounddir: str
	randomplaylist: str
	
class ConfigManager:
	def __init__(self, configfile='configs.cfg'):
		# default values for test
		# if os.name == 'posix':
			# self.dbname		  = 'sound.linux.db'
			# self.config.active_profile.sounddir		= os.path.join('home', 'blju', 'Sound')
			# self.config.active_profile.randomplaylist = 'playlist_random_cur_linux.m3u' 
		# else:
			# self.dbname		  = 'sound.windows.db'
			# self.config.active_profile.sounddir		= os.path.join('E:\\', '000_2025', 'MusicManager_sync_workspaces', 'MusicMgr', 'Sound')
			# self.config.active_profile.randomplaylist = 'playlist_random_cur_windows.m3u'
		self.configfile = configfile
		self.profiles = {}	# Dict im Format: {"Profilname": Config(...)}
		self.defaultConfig = ''
		self.activeProfile = ''
		self.readConfigfile()
		
	@property
	def active_profile(self) -> Config:
		return self.profiles.get(self.activeProfile)
		
	def readConfigfile(self):
		self.profiles.clear()
		
		if not os.path.exists(self.configfile):
			return
			
		with open(self.configfile, 'r') as fin:
			lines = fin.readlines()
			fin.close()
			
		for l in lines:
			match0 = re.search(r'<defaultconfig>\s*(.+)\s*</defaultconfig>', l)
			# match1 = re.search(r'<config>', l)
			match2 = re.search(r'<name>\s*(.+)\s*</name>', l)
			match3 = re.search(r'<dbname>\s*(.+)\s*</dbname>', l)
			match4 = re.search(r'<sounddir>\s*(.+)\s*</sounddir>', l)
			match5 = re.search(r'<randomplaylist>\s*(.+)\s*</randomplaylist>', l)
			match6 = re.search(r'</config>', l)
			if match0:
				self.defaultconfig = match0.group(1)
			elif match2:
				cur_config = match2.group(1)
			elif match3:
				m_dbname = match3.group(1)
			elif match4:
				m_sounddir = match4.group(1)
			elif match5:
				m_randomplaylist = match5.group(1)
			elif match6:
				if cur_config:
					self.profiles[cur_config] = Config(cur_config, m_dbname, m_sounddir, m_randomplaylist)
			
			# Falls kein aktives Profil gewählt wurde, nimm das Standardprofil
			if not self.activeProfile:
				self.activeProfile = self.defaultconfig
				
	def saveConfigfile(self, bWithBackup = False):
		if bWithBackup:
			os.makedirs('bkup', exist_ok=True)
			backupfile = os.path.join('bkup', self.configfile + '.bkup')
			shutil.copyfile(self.configfile, backupfile)
			
		text = f'<defaultconfig>{self.defaultconfig}</defaultconfig>\n\n'
		for name, prof in self.profiles.items():
			text += '<config>\n'
			text += f'<name>{prof.name}</name>\n'
			text += f'<dbname>{prof.dbname}</dbname>\n'
			text += f'<sounddir>{prof.sounddir}</sounddir>\n'
			text += f'<randomplaylist>{prof.randomplaylist}</randomplaylist>\n'
			text += '</config>\n\n'
		
		fout = open(self.configfile, 'w')
		fout.write(text)
		fout.close()

	def add_or_update_profile(self, profile: Config):
		self.profiles[profile.name] = profile
		self.saveConfigfile()

	def delete_profile(self, profile_name: str):
		if profile_name in self.profiles:
			del self.profiles[profile_name]
			# if we delete the default config, set another one as default
			if self.defaultconfig == profile_name and self.profiles:
				self.defaultconfig = next(iter(self.profiles.keys()))
			self.saveConfigfile(bWithBackup=True)
			
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
		with open(playlistfile, 'r', encoding='utf-8') as fin:
			lines = fin.readlines()
			fin.close()
			for line in lines:
				path_str = line.strip()
				if path_str:
					abs_path = os.path.abspath(path_str)
					playlist.addMedia(QMediaContent(QUrl.fromLocalFile(abs_path)))
		return playlist

if __name__ == '__main__':
	app = QtWidgets.QApplication(sys.argv)
	window = MainWindow()
	window.show()
	sys.exit(app.exec_())

### use a global QMediaPlayer and QMediaPlaylist for MainWindow and AlbumPlayerDlg ?