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
		
class MainWindow(QtWidgets.QDialog):
	def __init__(self):
		super(MainWindow, self).__init__()
		uic.loadUi('MusicPlayerJB.ui', self)

		self.player = QMediaPlayer()
		self.playlist = QMediaPlaylist()
		
		self.randomplaylist    = 'playlist_random_cur.m3u'
		self.randomplaylistgen = 'playlist_random_gen.m3u' #TODO: these 2 should be the same file - only use different ones for testing

		# connect signals and slots
		self.pushButton_genrandomplaylist.clicked.connect(self.pushButton_genrandomplaylist_run)
		self.pushButton_playrandomplaylist.clicked.connect(self.pushButton_playrandomplaylist_run)
		self.pushButton_randomplayerstop.clicked.connect(self.pushButton_randomplayerstop_run)
		self.pushButton_randomplaypause.clicked.connect(self.pushButton_randomplaypause_run)
		self.pushButton_randomplayprev.clicked.connect(self.pushButton_randomplayprev_run)
		self.pushButton_randomplaynext.clicked.connect(self.pushButton_randomplaynext_run)

	def pushButton_genrandomplaylist_run(self):
		plgen = PlaylistGenerator()
		d = QFileDialog.getExistingDirectory(self, 'select Music Directory', '.', QFileDialog.Option.ShowDirsOnly)
		plgen.genCompletePlaylistFromDirectory(d, self.randomplaylistgen, True)
		
	def pushButton_playrandomplaylist_run(self):
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
				
			for _line in lines:
				line = os.path.join(os.getcwd(), _line.strip())
				self.playlist.addMedia(QMediaContent(self.url.fromLocalFile(line)))

			idx = self.getPlaylistState(self.randomplaylist)
			self.playlist.setCurrentIndex(idx) ### TODO: save/load index from config
			self.player.setPlaylist(self.playlist)
			self.player.setVolume(50)
			self.player.play()
		elif self.player.state() == QMediaPlayer.PausedState:
			self.player.play()

	def pushButton_randomplayerstop_run(self):
		if self.player.state() == QMediaPlayer.PlayingState:
			self.player.stop()
		elif self.player.state() == QMediaPlayer.StoppedState:
			print('not playing')
		elif self.player.state() == QMediaPlayer.PausedState:
			self.player.stop()
		self.savePlaylistState(self.playlist, self.randomplaylist)
		
	def pushButton_randomplaypause_run(self):
		if self.player.state() == QMediaPlayer.PlayingState:
			self.player.pause()
		elif self.player.state() == QMediaPlayer.StoppedState:
			print('not playing')
		elif self.player.state() == QMediaPlayer.PausedState:
			print('already paused')
			
	def pushButton_randomplayprev_run(self):
		if bDebug:
			print('<pushButton_randomplayprev_run>')
		if self.playlist.previousIndex() == -1:
			self.playlist.setCurrentIndex(self.playlist.mediaCount()-1)
		else:
			self.playlist.previous()
		  
	def pushButton_randomplaynext_run(self):
		if bDebug:
			print('<pushButton_randomplaynext_run>')
		self.playlist.next()
		if self.playlist.currentIndex() == -1:
			self.playlist.setCurrentIndex(0)
			self.player.play()
  
	def savePlaylistState(self, playlist, playlistname):
		if bDebug:
			print('<savePlaylistState>' + str(playlistname))
		idx = playlist.currentIndex()
		f = open(playlistname + '.index.txt', 'w')
		f.write(str(idx))
		f.close()

	def getPlaylistState(self, playlistname):
		if playlistname == '':
			return 0
		f = open(playlistname + '.index.txt', 'r')
		lines = f.readline()
		val = int(lines, 10)
		if bDebug:
			print('read index: ' + str(val))
		f.close()
		
		return val

	def closeEvent(self, event):
		# function for cleaning up/saving states etc.
		self.savePlaylistState(self.playlist, self.randomplaylist)
		if bDebug:
			print('Exiting ...')
		# close = QtWidgets.QMessageBox.question(self,
									 # "QUIT",
									 # "Are you sure want to stop process?",
									 # QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
		# if close == QtWidgets.QMessageBox.Yes:
			# event.accept()
		# else:
			# event.ignore()
				
if __name__ == '__main__':
	app = QtWidgets.QApplication(sys.argv)
	window = MainWindow()
	window.show()
	sys.exit(app.exec_())
