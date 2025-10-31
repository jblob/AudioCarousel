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
		self.pushButton_playrandomplaylist.clicked.connect(self.pushButton_playrandomplaylist_run)
		self.pushButton_genrandomplaylist.clicked.connect(self.pushButton_genrandomplaylist_run)

	def pushButton_playrandomplaylist_run(self):
		
		if self.player.state() != QMediaPlayer.PlayingState:
			if bDebug:
				print(str(self.player.state()))
			self.url = QUrl
			with open(self.randomplaylist, 'r') as fin:
				lines = fin.readlines()
				fin.close()
				
			for _line in lines:
				line = os.path.join(os.getcwd(), _line.strip())
				self.playlist.addMedia(QMediaContent(self.url.fromLocalFile(line)))

			self.playlist.setCurrentIndex(0) ### TODO: save/load index from config
			self.player.setPlaylist(self.playlist)
			self.player.setVolume(50)
			self.player.play()
		else:
			if bDebug:
				print(str(self.player.state()))
			print('already playing')

	def pushButton_genrandomplaylist_run(self):
		plgen = PlaylistGenerator()
		d = QFileDialog.getExistingDirectory(self, 'select Music Directory', '.', QFileDialog.Option.ShowDirsOnly)
		plgen.genCompletePlaylistFromDirectory(d, self.randomplaylistgen, True)

if __name__ == '__main__':
	app = QtWidgets.QApplication(sys.argv)
	window = MainWindow()
	window.show()
	sys.exit(app.exec_())
