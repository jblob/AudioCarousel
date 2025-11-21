import sys
import os
import subprocess
import glob
import random
from subprocess import Popen, PIPE, STDOUT
from pathlib import Path
import sqlite3

from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import QAction, QApplication, QLabel, QMainWindow, QMenu, QDialog, QFileDialog, QStatusBar
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtMultimedia import (QMediaPlayer, QMediaContent, QMediaPlaylist, QMediaMetaData)
from PyQt5.QtCore import pyqtRemoveInputHook # see comment below
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QTableView, QTabWidget
from PyQt5.QtCore import QAbstractTableModel

import mutagen
from mutagen.mp3 import MP3, MPEGInfo
from mutagen.id3 import ID3
from mutagen.easyid3 import EasyID3

bDebug = True
bDebugSQL = False

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
		self.mpgType = None
		self.title = None
		self.artist = None
		self.album = None
		self.genre = None
		self.duration = 0
		self.bCoverAvailable = False
		self.tracknumber = None
		self.year = None
		self.channels = 0
		self.bitrate_mode = None
		self.bitrate = 0
		self.rating = 0
		self.fullpath = None

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
		audio = MP3(file, ID3=EasyID3)
		tags  = ID3(file)
		if file.endswith('mp3'):
			self.mpgType = 'mp3'
		elif file.endswith('mp4'):
			self.mpgType = 'mp4'
		try:
			self.title = audio['title'][0]
		except:
			pass
		try:
			self.artist = audio['artist'][0]
		except:
			pass
		try:
			self.album = audio['album'][0]
		except:
			pass
		try:
			self.genre = audio['genre'][0]
		except:
			pass
		try:
			self.duration = audio.info.length
		except:
			pass

		if 'APIC:Cover' in tags:
			self.bCoverAvailable = True
		else:
			self.bCoverAvailable = False
		try:
			self.tracknumber = audio['tracknumber'][0]
		except:
			pass
		try:
			self.year = audio['date'][0]
		except:
			pass
		try:
			self.channels = audio.info.channels
		except:
			pass
		try:
			self.bitrate_mode = audio.info.bitrate_mode
		except:
			pass
		try:
			self.bitrate = audio.info.bitrate
		except:
			pass
		try:
			self.rating = audio.info.rating
		except:
			pass
		self.fullpath = file
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
		return [self.title, self.artist, self.album, self.genre, self.duration, self.bCoverAvailable, self.tracknumber, self.year, self.channels, self.bitrate_mode, self.bitrate, self.rating, self.fullpath]
		
	def printData(self, file):
		print('---------------------------------------------------')
		print('<MP3DATA>')
		print('\t<MPGTYPE>' + self.mpgType)
		print('\t<TITLE>' + self.title)
		print('\t<ARTIST>' + self.artist)
		print('\t<ALBUM>' + self.album)
		print('\t<GENRE>' + self.genre)
		print('\t<DURATION>' + str(self.duration))
		print('\t<COVER_AVAIL>' + str(self.bCoverAvailable))
		print('\t<TRACKNUMBER>' + self.tracknumber)
		print('\t<YEAR>' + self.year)
		print('\t<CHANNELS>' + str(self.channels))
		print('\t<BITRATEMODE>' + str(self.bitrate_mode))
		print('\t<BITRATE>' + str(self.bitrate))
		print('\t<RATING>' + str(self.rating))
		print('\t<FULLPATH>' + self.fullpath)
		print('</MP3DATA>')
		print('---------------------------------------------------')
		
class MainWindow(QtWidgets.QDialog):
	def __init__(self, db):
		super(MainWindow, self).__init__()
		self.COVER_SIZE = 150
		uic.loadUi('MusicPlayerJB.ui', self)
		self.setFixedSize(1400,810)
		self.label_cover.setFixedSize(self.COVER_SIZE, self.COVER_SIZE)
		
		self.db = db
		
		self.bPlaylistNeedsSaving = False
		self.player = QMediaPlayer()
		self.playlist = QMediaPlaylist()
		pyqtRemoveInputHook() # otherwise no debugging with pdb possible :/
		self.randomplaylist    = 'playlist_random_cur.m3u'
		self.randomplaylistgen = self.randomplaylist
		# self.randomplaylistgen = 'playlist_random_gen.m3u' #TODO: these 2 should be the same file - only use different ones for testing
		self.randomplayliststate = self.getPlaylistSavedState(self.randomplaylistgen)
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

		self.player.metaDataChanged.connect(self.slotMetaDataChanged)
		self.playlist.currentIndexChanged.connect(self.slotIndexChanged)
		
		### test
		# self.player.setMedia(QMediaContent(QUrl.fromLocalFile('e:/000_2024/at_Urlaub/dSPACE_LearningConnectionRecording_MBD_1280x720_20210211-2_EN.mp4')))
		self.player.setMedia(QMediaContent(QUrl.fromLocalFile('e:/at_home/3/Sound/_videos_unsorted/t_online_werbung.mp4')))
		self.player.setVideoOutput(self.widget_videooutput)
		# connect(mplayer, &QMediaPlayer::stateChanged, [vw](QMediaPlayer::State state){
							# if (state == QMediaPlayer::StoppedState)
								# vw->update(); });
		# vw.show();
		self.statusBar = QStatusBar()
		self.verticalLayout_statusbar.addWidget(self.statusBar)
		self.statusBar.showMessage('------------------------------------')
		
		# fill listviews from DB
		self.allgenres = self.db.getColValsFromDB('Albums', 'Genre')
		self.allartists = self.db.getColValsFromDB('Albums', 'Artist')
		self.comboBox_genre.addItems(self.allgenres)
		self.comboBox_artist.addItems(self.allartists)

	def pushButton_randomplaylist_play_run(self):
		if self.player.state() == QMediaPlayer.PlayingState:
			if bDebug:
				print(str(self.player.state()))
			print('already playing')
		elif self.player.state() == QMediaPlayer.StoppedState:
			if bDebug:
				print(str(self.player.state()))
			self.url = QUrl
			with open(self.randomplaylist, 'r') as fin:
				lines = fin.readlines()
				fin.close()
			
			self.listWidget_randomplaylist.clear()
			self.playlist.clear()
			for _line in lines:
				line = os.path.join(os.getcwd(), _line.strip())
				self.playlist.addMedia(QMediaContent(self.url.fromLocalFile(line)))
				self.listWidget_randomplaylist.addItem(line)

			self.playlist.setCurrentIndex(self.randomplayliststate)
			self.player.setPlaylist(self.playlist)
			self.player.setVolume(50)
			self.bPlaylistNeedsSaving = True
			self.player.play()
		elif self.player.state() == QMediaPlayer.PausedState:
			self.player.play()

	def pushButton_genrandomplaylist_run(self):
		plgen = PlaylistGenerator()
		d = QFileDialog.getExistingDirectory(self, 'select Music Directory', '.', QFileDialog.Option.ShowDirsOnly)
		plgen.genCompletePlaylistFromDirectory(d, self.randomplaylistgen, True)
		self.playlist.setCurrentIndex(0)
		self.bPlaylistNeedsSaving = True
		
	def pushButton_randomplaylist_stop_run(self):
		if self.player.state() == QMediaPlayer.PlayingState:
			self.player.stop()
		elif self.player.state() == QMediaPlayer.StoppedState:
			print('not playing')
		elif self.player.state() == QMediaPlayer.PausedState:
			self.player.stop()
		if self.bPlaylistNeedsSaving:
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
		  
	def pushButton_randomplaylist_next_run(self):
		# method for moving to next track
		self.playlist.next()
		if self.playlist.currentIndex() == -1:
			self.playlist.setCurrentIndex(0)
			self.player.play()

	def savePlaylistState(self, playlist, playlistfile):
		idx = playlist.currentIndex()
		if bDebug:
			print('<savePlaylistState>' + playlistfile + '<idx>' + str(idx))
		f = open(playlistfile + '.index.txt', 'w')
		f.write(str(idx))
		f.close()
		self.bPlaylistNeedsSaving = False

	def getPlaylistSavedState(self, playlist):
		if playlist == '':
			return
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
			data = self.player.metaData(QMediaMetaData.Title)
			mp3data = MP3Data().data(self.player)
			if bDebug:
				print('<slotMetaDataChanged>' + str(mp3data))
			self.label_artist_2.setText(mp3data['artist'])
			self.label_title_2.setText(mp3data['track'])
			self.label_album_2.setText(mp3data['album'])
			self.label_genre_2.setText(str(mp3data['genre'])) # genre is a list, TODO: better handling to display it ? genre[0] ?
			self.label_year_2.setText(str(mp3data['release']))

			pixmap = QPixmap(mp3data['coverart_th'])
			pixmap = pixmap.scaled(self.COVER_SIZE, self.COVER_SIZE)
			self.label_cover.setPixmap(pixmap)
			self.statusBar.showMessage('playing: ' + mp3data['track'] + ' - ' + mp3data['artist'])
		else:
			self.label_artist_2.setText('<unknown>')
			self.label_title_2.setText('<unknown>')
			self.label_album_2.setText('<unknown>')
			self.label_genre_2.setText('<unknown>')
			self.label_year_2.setText('<unknown>')

			# self.label_cover.setPixmap(pixmap) ### TODO: standard pixmap
			
	def slotIndexChanged(self):
		self.listWidget_randomplaylist.setCurrentRow(self.playlist.currentIndex())
		if bDebug:
			print('<setCurrentRow><slotIndexChanged>' + str(self.listWidget_randomplaylist.currentRow() + 1))
		if self.playlist.currentIndex() < 0:
			self.window.music_list.setCurrentRow(0)
			self.playlist.setCurrentIndex(0)

	def closeEvent(self, event):
		if self.bPlaylistNeedsSaving:
			self.savePlaylistState(self.playlist, self.randomplaylist)
		if bDebug:
			print('Exiting ...')
	
	def pushButton_database_updateDB_run(self):
		# Thread filling the DB
#		sounddir = QFileDialog.getExistingDirectory(self, 'select Music Directory', '.', QFileDialog.Option.ShowDirsOnly)
		sounddir = os.path.join('E:\\', '000_2025', 'MusicManager_sync_workspaces', 'MusicMgr', 'Sound')
		files = glob.glob(sounddir + '/**/*.mp3', recursive=True)
		lAllAbums = []
		# mp4files = glob.glob(sounddir + '/**/*.mp4', recursive=True)
		# files = glob.glob(sounddir + '/**/*.mp?', recursive=True) ### mp4 not supported by mutagen :( -> TODO: search for another lib
		# files = list(Path(sounddir).rglob("*.[mM][pP][34]"))
		# if bDebug:
			# print(str(files))
		nFilesToProceed = len(files) # for progress bar
		self.db.createTables()
		if bDebug:
			print('=============================================================')
			print('[Updating DB] started')
		for curfile in files:
			if bDebug:
				print('\tprocessing: ' + curfile)
			m = MP3Data()
			arrMp3Data = m.getTagsFromFile(curfile)
			# if bDebug:
				# m.printData(curfile)
			db.addline_tablesongs(arrMp3Data)
			if not arrMp3Data[2] in lAllAbums:
				lAllAbums.append(arrMp3Data[2])
				db.addline_tablealbums(arrMp3Data)
		if bDebug:
			print('[Updating DB] finished')
			print('=============================================================')

		with open('sql.log', 'w') as fout:
			fout.write(db.sqltext_dbg)
			fout.close()
			
	def pushButton_database_showDB_run(self):
		data1 = db.getTable('Songs')
		data2 = db.getTable('Albums')

		headers1 = ['Title', 'Artist', 'Album', 'Genre', 'Duration', 'CoverAvail', 'TrackNr', 'Year', 'Channels', 'BitrateMode', 'Bitrate', 'Rating', 'Fullpath']
		headers2 = ['Artist', 'Album', 'Genre', 'FullPath']

		# Create and show the TabWindow
		self.tab_window = TabWindow(headers1, data1, headers2, data2)
		self.tab_window.show()

	def pushButton_testsqlquery_run(self):
		cmd = self.lineEdit_testsqlquery.text()
		res = db.exec_sql(cmd, True, False, True)
		self.textBrowser_testsqlquery.setText(res)
		

class TabWindow(QMainWindow):
	def __init__(self, headers1, data1, headers2, data2):
		super(TabWindow, self).__init__()
		self.setWindowTitle("Tab Window")
		self.resize(600, 400)

		# Create the QTabWidget
		tab_widget = QTabWidget(self)
		self.setCentralWidget(tab_widget)


		# Create the first table
		model1 = TableModel(data1, headers1)
		table_view1 = QTableView()
		table_view1.setModel(model1)
		table_view1.verticalHeader().hide();

		# Create the second table
		model2 = TableModel(data2, headers2)
		table_view2 = QTableView()
		table_view2.setModel(model2)
		table_view2.verticalHeader().hide();

		# Add the tables to the tabs
		tab_widget.addTab(table_view1, 'Songs')
		tab_widget.addTab(table_view2, 'Albums')
		

class DB:		
	def __init__(self):
		# Verbindung zur Datenbank herstellen
		self.conn = sqlite3.connect('sound.db')
		# Cursor-Objekt (zum Zugriff auf die Datenbank)
		self.cursor = self.conn.cursor()
		self.conn.close()
		self.sqltext_dbg = ''
		
	def exec_sql(self, cmd, bCloseConn=True, bExitOnError = True, bSQLTest = False):
		ret_text = ''
		try:
			# Verbindung zur Datenbank herstellen
			self.conn = sqlite3.connect('sound.db')
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
		GENRE VARCHAR(255), 
		FULLPATH VARCHAR(2048)
		);"""

		self.exec_sql(sql)

		
	# def addline_tablesongs(self, title, artist, album, genre, duration, bCoverAvailable, tracknumber, year, channels, bitrate_mode, bitrate, rating, fullpath)
	def addline_tablesongs(self, data):
		sql  = 'INSERT INTO Songs VALUES(' ###+ data 
		# sql += '0, '  ### primary key !!!
		sql += '"' + data[0] + '", '   #title
		sql += '"' + data[1] + '", '   #artist
		sql += '"' + data[2] + '", '   #album
		sql += '"' + data[3] + '", '   #genre
		sql += str(data[4])  + ', '    #duration
		sql += str(data[5])  + ', '    #bCoverAvailable
		sql += str(data[6])  + ', '    #tracknumber
		sql += str(data[7])  + ', '    #year
		sql += str(data[8])  + ', '    #channels
		sql += '"' + str(data[9])  + '", '    #bitrate_mode
		sql += str(data[10])  + ', '   #bitrate
		sql += str(data[11])  + ', '   #rating
		sql += '"' + data[12] + '"); ' #fullpath

		self.exec_sql(sql)
		
	def addline_tablealbums(self, data):
		sql  = 'INSERT INTO Albums VALUES('
		# sql += '0, '  ### primary key !!!
		sql += '"' + data[1] + '", '   #artist
		sql += '"' + data[2] + '", '   #album
		sql += '"' + data[3] + '", '   #genre
#		sql += str(data[4])  + ', '    #duration -> later
#		sql += str(data[5])  + ', '    #bCoverAvailable -> later
#		sql += str(data[7])  + ', '    #year -> later
		sql += '"' + data[12] + '"); ' #fullpath

		self.exec_sql(sql)
		
	def getTable(self, table):
		sql = 'SELECT * FROM ' + table + ';'
		self.exec_sql(sql, False)

		rows = self.cursor.fetchall()
		self.conn.close()
		
		return rows
		
	def getColValsFromDB(self, table, colname):
		retval = []
		sql = 'SELECT ' + colname + ' FROM ' + table
		self.exec_sql(sql, False)
		rows = self.cursor.fetchall()
		for r in rows:
			if not r[0] in retval:
				retval.append(r[0])
		self.conn.close()
		
		if bDebug:
			print('<getGenresFromDB>' + str(retval))
			
		return retval
		
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

if __name__ == '__main__':
	app = QtWidgets.QApplication(sys.argv)
	db = DB()
	window = MainWindow(db)
	window.show()
	sys.exit(app.exec_())
