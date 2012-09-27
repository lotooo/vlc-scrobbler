import MySQLdb
import time
import datetime
import logging


class XbmcClient(object):
	def __init__(self,host,username,password,db_name,bufferfile):
		self.host = host
		self.username = username
		self.password = password
		self.db_name = db_name
		self.bufferfile = bufferfile
		self.log = logging.getLogger('XbmcClient')
		try:
			db=MySQLdb.connect(self.host,self.username,self.password,self.db_name,use_unicode=True)
			self.is_alive = True
		except:
			self.is_alive = False
			
		
	def mysql_select_one(self,query):
		try:
			db=MySQLdb.connect(self.host,self.username,self.password,self.db_name,use_unicode=True)
			c = db.cursor(MySQLdb.cursors.DictCursor)
			c.execute(query)
			result = c.fetchone()
		except MySQLdb.Error, e:
			print "Error %d: %s" % (e.args[0],e.args[1])
			sys.exit(1)
		db.close()
		return result
		
	def mysql_update(self,query):
		try:
			db=MySQLdb.connect(self.host,self.username,self.password,self.db_name)
			c = db.cursor(MySQLdb.cursors.DictCursor)
			c.execute(query)
		except MySQLdb.Error, e:
			print "Error %d: %s" % (e.args[0],e.args[1])
			sys.exit(1)
		db.close()
		return
		
	def get_tv_show_info(self, filename):
		filename = filename.replace("'","%")
		word = ""
		for l in filename:
			ascii_code = ord(l)
			if ascii_code > 127:
				word = word + '%'
			else:
				word = '%s%c' % (word, chr(ascii_code))
		filename = word
		query = """SELECT \
				s.c00 seriesName, \
				e.idFile idFile, \
				e.c12 seasonNumber, \
				e.c13 episodeNumber, \
				YEAR(e.premiered) seriesYear \
			FROM episodeview e JOIN tvshow s ON e.idShow = s.idShow \
			WHERE strFileName LIKE '%%%s%%';""" % filename
		query=query.replace('\t','')
		self.log.debug(query)
		tv_show = self.mysql_select_one(query)
		return tv_show
		
	def get_movie_info(self, filename):
		filename = filename.replace("'","\\'")
		word = ""
		for l in filename:
			ascii_code = ord(l)
			if ascii_code > 127:
				word = word + '%'
			else:
				word = '%s%c' % (word, chr(ascii_code))
		filename = word
		query = "SELECT \
				m.c00 title, \
				m.idFile idFile, \
				m.c07 year \
			FROM movieview m \
			WHERE strFileName LIKE '%%%s%%';" % filename
		query=query.replace('\t','')
		self.log.debug(query)
		movie = self.mysql_select_one(query)
		return movie
	
	def mark_as_seen(self, idFile):
		d = time.strftime("%Y-%m-%d %H:%M:%S")
		query = "UPDATE files SET playCount = playCount + 1,lastPlayed = '" + str(d) + "' WHERE idFile = '" + str(idFile) + "';"
		self.log.debug(query)
		self.mysql_update(query)
		return
	
	def add_2_buffer(self, filename):
		# Ouverture du fichier en lecture pour verifier que le buffer n'a pas deja cet info:
		f = open(self.bufferfile, "r")
		content=f.read()
		f.close()
		if filename not in content:
			self.log.info("Adding %s to XBMC buffer (%s)" % (filename,self.bufferfile))
			# Ouverture d'un fichier en *ajout*:
			f = open(self.bufferfile, "a")
			f.write("%s\n" % filename)
			f.close()
		return
