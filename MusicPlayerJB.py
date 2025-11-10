import sys
import os
import subprocess
import glob
import random
from subprocess import Popen, PIPE, STDOUT

from PyQt5 import QtWidgets, uic
from PyQt5.QtWidgets import QAction, QApplication, QLabel, QMainWindow, QMenu, QDialog, QFileDialog
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtMultimedia import (QMediaPlayer, QMediaContent, QMediaPlaylist, QMediaMetaData)
from PyQt5.QtCore import pyqtRemoveInputHook # see comment below
from PyQt5.QtGui import QPixmap


bDebug = True

class StdoutRedirector:
	def __init__(self, text_widget):
		self.text_widget = text_widget

	def write(self, text):
		self.text_widget.append(text) # Text am Ende einfügen
		###self.text_widget.see(tk.END) # Zum Ende scrollen, um den neuesten Text anzuzeigen

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
		pass

	def data(self, player):
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
		return info
		
class MainWindow(QtWidgets.QDialog):
	def __init__(self):
		super(MainWindow, self).__init__()
		uic.loadUi('MusicPlayerJB.ui', self)
		self.bPlaylistNeedsSaving = False
		self.player = QMediaPlayer()
		self.playlist = QMediaPlaylist()
		pyqtRemoveInputHook() # otherwise no debugging with pdb possible :/
		self.randomplaylist    = 'playlist_random_cur.m3u'
		self.randomplaylistgen = 'playlist_random_gen.m3u' #TODO: these 2 should be the same file - only use different ones for testing
		self.randomplayliststate = self.getPlaylistSavedState(self.randomplaylistgen)
		self.label_cover.setStyleSheet('background-color: white;')

		# connect signals and slots
		self.pushButton_randomplaylist_play.clicked.connect(self.pushButton_randomplaylist_play_run)
		self.pushButton_genrandomplaylist.clicked.connect(self.pushButton_genrandomplaylist_run)
		self.pushButton_randomplaylist_stop.clicked.connect(self.pushButton_randomplaylist_stop_run)
		self.pushButton_randomplaylist_pause.clicked.connect(self.pushButton_randomplaylist_pause_run)
		self.pushButton_randomplaylist_prev.clicked.connect(self.pushButton_randomplaylist_prev_run)
		self.pushButton_randomplaylist_next.clicked.connect(self.pushButton_randomplaylist_next_run)

		self.player.metaDataChanged.connect(self.slotMetaDataChanged)
		
		### test
		# self.player.setMedia(QMediaContent(QUrl.fromLocalFile('e:/000_2024/at_Urlaub/dSPACE_LearningConnectionRecording_MBD_1280x720_20210211-2_EN.mp4')))
		self.player.setMedia(QMediaContent(QUrl.fromLocalFile('e:/at_home/3/Sound/_videos_unsorted/t_online_werbung.mp4')))
		self.player.setVideoOutput(self.widget_videooutput)
		# connect(mplayer, &QMediaPlayer::stateChanged, [vw](QMediaPlayer::State state){
							# if (state == QMediaPlayer::StoppedState)
								# vw->update(); });
		# vw.show();

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
			for _line in lines:
				line = os.path.join(os.getcwd(), _line.strip())
				self.playlist.addMedia(QMediaContent(self.url.fromLocalFile(line)))
				self.listWidget_randomplaylist.addItem(line)
			self.listWidget_randomplaylist.setCurrentRow(self.randomplayliststate)

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
			self.listWidget_randomplaylist.setCurrentRow(self.playlist.mediaCount()-1)
		else:
			self.playlist.previous()
			self.listWidget_randomplaylist.setCurrentRow(self.listWidget_randomplaylist.currentRow() - 1)
		  
	def pushButton_randomplaylist_next_run(self):
		# method for moving to next track
		self.playlist.next()
		self.listWidget_randomplaylist.setCurrentRow(self.listWidget_randomplaylist.currentRow() + 1)
		if self.playlist.currentIndex() == -1:
			self.playlist.setCurrentIndex(0)
			self.listWidget_randomplaylist.setCurrentRow(0)
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
			if bDebug:
				print('<slotMetaDataChanged>' + str(data))
			mp3data = MP3Data().data(self.player)
			if bDebug:
				print('<slotMetaDataChanged>' + str(mp3data))
				print('<slotMetaDataChanged>' + str(mp3data['artist']))
			self.label_artist_2.setText(mp3data['artist'])
			self.label_title_2.setText(mp3data['track'])
			self.label_album_2.setText(mp3data['album'])
			self.label_genre_2.setText(str(mp3data['genre'])) # genre is a list, TODO: better handling to display it ?
			self.label_year_2.setText(str(mp3data['release']))

			pixmap = QPixmap(mp3data['coverart_th'])
			pixmap = pixmap.scaled(500,500)
			self.label_cover.setPixmap(pixmap)
	
	def closeEvent(self, event):
		if self.bPlaylistNeedsSaving:
			self.savePlaylistState(self.playlist, self.randomplaylist)
		if bDebug:
			print('Exiting ...')
				
if __name__ == '__main__':
	app = QtWidgets.QApplication(sys.argv)
	window = MainWindow()
	window.show()
	sys.exit(app.exec_())
