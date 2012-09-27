#!/usr/bin/env python
# encoding: utf-8

import logging
import ConfigParser
from vlcrc import VLCRemote
import movie_info
import TraktClient
import sys
import time
import re
import os
import getopt
from xbmc import XbmcClient

VERSION = "0.1"
VLC_VERSION = VLC_DATE = ""
TIMER_INTERVAL = 120

class TraktForVLC(object):

  def __init__(self, datadir, configfile, logfile):
    logging.basicConfig(format="%(asctime)s::%(name)s::%(levelname)s::%(message)s",
                            level=logging.INFO,
                            filename=logfile,
                            stream=sys.stdout)

    self.log = logging.getLogger("TraktForVLC")
    self.log.info("Initialized Trakt for VLC.")
        
    if not os.path.isfile(configfile):
      self.log.error("Config file " + configfile + " not found, exiting.")
      exit()

    self.config = ConfigParser.RawConfigParser()
    self.config.read(configfile)

    self.vlc_ip = self.config.get("VLC", "IP")
    self.vlc_port = self.config.getint("VLC", "Port")

    trakt_api = "128ecd4886c86eabe4ef13675ad10495c916381a"
    trakt_username = self.config.get("Trakt", "Username")
    trakt_password = self.config.get("Trakt", "Password")

    self.trakt_client = TraktClient.TraktClient(trakt_api,
                                                trakt_username,
                                                trakt_password)
    self.trakt_buffer = self.config.get("TraktForVLC", "bufferfile")

    self.xbmc_host = self.config.get("XBMC", "host")	
    self.xbmc_user = self.config.get("XBMC", "username")
    self.xbmc_pass = self.config.get("XBMC", "password")
    self.xbmc_db = self.config.get("XBMC", "db")
    self.xbmc_buffer = self.config.get("XBMC", "bufferfile")
    self.last_xbmc_status = ""
    #self.xbmc_client = XbmcClient(self.xbmc_host,self.xbmc_user,self.xbmc_pass,self.xbmc_db)

    self.scrobbled = False
    self.watching = False
    self.watching_now = ""
    self.timer = 0

  def run(self):
    while (True):
      self.timer += TIMER_INTERVAL
      try:
          self.main()
      except Exception, e:
          self.log.warning("An unknown error occurred.")
      time.sleep(TIMER_INTERVAL)
    
  def main(self):
    try:
      vlc = VLCRemote(self.vlc_ip, self.vlc_port)
    except:
      self.log.debug('Could not find VLC running at ' + str(self.vlc_ip) + ':'+ str(self.vlc_port))
      self.scrobbled = False
      self.watching = False
      return

    # Try to connect to xbmc
    self.xbmc_client = XbmcClient(self.xbmc_host,self.xbmc_user,self.xbmc_pass,self.xbmc_db,self.xbmc_buffer)
    if self.last_xbmc_status is not self.xbmc_client.is_alive:
	if self.xbmc_client.is_alive is True:
		self.log.info("XBMC is reacheable") 
	else:
		self.log.info("XBMC is unreacheable. Disabling it.") 
    self.last_xbmc_status = self.xbmc_client.is_alive
		
      
    vlcStatus = vlc.get_status()
    if vlcStatus:
      video = self.get_TV(vlc)
      if video is None:
        video = self.get_Movie(vlc)
	if video is None:
		return

      if (video["percentage"] >= 90
          and not self.scrobbled):
              self.log.info("Scrobbling to Trakt")
              
              try:
                  self.trakt_client.update_media_status(video["title"],
                                                        video["year"],
                                                        video["duration"],
                                                        video["percentage"],
                                                        VERSION,
                                                        VLC_VERSION,
                                                        VLC_DATE,
                                                        tv=video["tv"],
                                                        scrobble=True,
                                                        season=video["season"],
                                                        episode=video["episode"])
                  self.scrobbled = True
              except TraktClient.TraktError, (e):
                  self.log.error("An error occurred while trying to scrobble: " + e.msg)
                  if ("scrobbled" in e.msg and "already" in e.msg):
                      self.log.info("Seems we've already scrobbled this episode recently, aborting scrobble attempt.")
                      self.scrobbled = True
              try:
              	self.xbmc_client.mark_as_seen(video["idFile"])
              except:
              	self.log.error("An error occurred while trying to mark as seen in xbmc")
              
      elif (video["percentage"] < 90
            and not self.scrobbled
            and not self.watching
            and self.timer >= 300):
          self.log.info("Watching on Trakt")
          self.timer = 0
      
          try:
              self.trakt_client.update_media_status(video["title"],
                                                    video["year"],
                                                    video["duration"],
                                                    video["percentage"],
                                                    VERSION,
                                                    VLC_VERSION,
                                                    VLC_DATE,
                                                    tv=video["tv"],
                                                    season=video["season"],
                                                    episode=video["episode"])
              self.watching = True
              
          except TraktClient.TraktError, (e):
              self.timer = 870
              self.log.error("An error occurred while trying to mark watching: " + e.msg)
          
      self.log.debug("Timer: " + str(self.timer))

  def get_TV(self, vlc):
    try:
      now_playing = vlc.get_title("^(?!status change:)(?P<SeriesName>.+?)(?:[[(]?(?P<Year>[0-9]{4})[])]?.*)? *S?(?P<SeasonNumber>[0-9]+)(?:[ .XE]?(?P<EpisodeNumber>[0-9]{1,3})).*\.[a-z]{2,4}")
      fn = now_playing.group(0)    
      filename = fn.lstrip('> ')
      self.log.debug('Playing: %s'%filename)
      if self.xbmc_client.is_alive:
      	tv_show = self.xbmc_client.get_tv_show_info(filename)
      else:
	self.xbmc_client.add_2_buffer(filename)

      if tv_show:
      	self.log.debug('SeriesName: %s'%tv_show['seriesName'])
      	duration = int(vlc.get_length())
        time = int(vlc.get_time())
        percentage = time*100/duration
        return self.set_video(True, 
        	tv_show['seriesName'], 
        	tv_show['seriesYear'], 
        	duration, 
        	percentage, 
        	tv_show['seasonNumber'], 
        	tv_show['episodeNumber'], 
        	tv_show['idFile'])             	
      elif self.xbmc_client.is_alive:
      	self.log.debug('No matching TV Show file in XBMC')
    except:
    	return 

  def get_Movie(self, vlc):
    try:
      now_playing = vlc.get_title("^(?!status change:)(?P<Title>.+?) ?(?:[[(]?(?P<Year>[0-9]{4})[])]?.*)? *\.[a-z]{2,4}")
      fn = now_playing.group(0)    
      filename = fn.lstrip('> ')
      self.log.debug('Playing: %s'%filename)
      if self.xbmc_client.is_alive:
      	movie = self.xbmc_client.get_movie_info(filename)
      else:
	self.xbmc_client.add_2_buffer(filename)
      
      if movie:
      	duration = int(vlc.get_length())
      	playtime = int(vlc.get_time())
      	percentage = playtime*100/duration
      	return self.set_video(False, 
      			movie['title'], 
      			movie['year'], 
      			duration, 
      			percentage, -1, -1, movie['idFile'])
      elif self.xbmc_client.is_alive:
      	self.log.debug("No matching movie found for video playing in XBMC")
      	
    except:
      self.log.debug("No matching movie found for video playing")
      return 
      
     
  def set_video(self, tv, title, year, duration, percentage, season, episode,idFile):
    video = {}
    video["tv"] = tv
    video["title"] = title 
    video["year"] = year
    video["duration"] = duration
    video["percentage"] = percentage
    video["season"] = season
    video["episode"] = episode
    video["idFile"] = idFile
    return video

def ifnull(var, val):
  return val if var is None else var

def daemonize(pidfile=""):
    """
    Forks the process off to run as a daemon. Most of this code is from the
    sickbeard project.
    """
    
    if (pidfile):
        if os.path.exists(pidfile):
            sys.exit("The pidfile " + pidfile + " already exists, Trakt for VLC may still be running.")
        try:
            file(pidfile, 'w').write("pid\n")
        except IOError, e:
            sys.exit("Unable to write PID file: %s [%d]" % (e.strerror, e.errno))
            
    # Make a non-session-leader child process
    try:
        pid = os.fork() #@UndefinedVariable - only available in UNIX
        if pid != 0:
            sys.exit(0)
    except OSError, e:
        raise RuntimeError("1st fork failed: %s [%d]" %
                   (e.strerror, e.errno))

    os.setsid() #@UndefinedVariable - only available in UNIX

    # Make sure I can read my own files and shut out others
    prev = os.umask(0)
    os.umask(prev and int('077', 8))

    # Make the child a session-leader by detaching from the terminal
    try:
        pid = os.fork() #@UndefinedVariable - only available in UNIX
        if pid != 0:
            sys.exit(0)
    except OSError, e:
        raise RuntimeError("2nd fork failed: %s [%d]" %
                   (e.strerror, e.errno))

    dev_null = file('/dev/null', 'r')
    os.dup2(dev_null.fileno(), sys.stdin.fileno())
    
    if (pidfile):
        file(pidfile, "w").write("%s\n" % str(os.getpid()))

if __name__ == '__main__':
  should_pair = should_daemon = False
  pidfile = ""
  datadir = sys.path[0]
  logfile = ""
  config = ""
  
  try:
    opts, args = getopt.getopt(sys.argv[1:], "dp", ['daemon', 'pidfile=', 'datadir=', 'config=', 'log=']) #@UnusedVariable
  except getopt.GetoptError:
    print "Available options: --daemon, --pidfile, --datadir, --config"
    sys.exit()

  for o, a in opts:
    # Run as a daemon
    if o in ('-d', '--daemon'):
      if sys.platform == 'win32':
        print "Daemonize not supported under Windows, starting normally"
      else:
        should_daemon = True
                
    # Create pid file
    if o in ('--pidfile',):
      pidfile = str(a)
        
    # Determine location of datadir
    if o in ('--datadir',):
      datadir = str(a)
            
    # Determine location of config file
    if o in ('--config',):
      config = str(a)
      
    if o in ('--log',):
      logfile = str(a)      

  if should_daemon:
    daemonize(pidfile)
  elif (pidfile):
    print "Pidilfe isn't useful when not running as a daemon, ignoring pidfile."
    
  if config == "":
    config = sys.path[0]
  configfile = config + "/config.ini"

  client = TraktForVLC(datadir, configfile, logfile)
  client.run()

  

