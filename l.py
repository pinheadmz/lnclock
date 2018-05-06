#!/usr/bin/sudo python

################
# dependencies #
################

import curses
import time
import hashlib
import atexit
import math
import rpc_pb2 as ln
import rpc_pb2_grpc as lnrpc
import grpc
import os
from PIL import Image, ImageDraw, ImageFont
from rgbmatrix import RGBMatrix, RGBMatrixOptions
import unicodedata

#############
# constants #
#############

EDGELEN = 15
PEERSIZE = 1
MEX = 15
MEY = 15
# LED grid graph display active channels or all channels
ACTIVE_ONLY = False
# refresh rate in seconds
REFRESH = 1

##############
# initialize #
##############

def cleanup():
	# debug, keep err msg on screen for a sec
	#time.sleep(1)
	# undo curses settings
	curses.nocbreak()
	curses.echo()
	curses.endwin()
	# clear LED grid
	matrix.Clear()
	print "..."
atexit.register(cleanup)

# init curses for text output and getch()
stdscr = curses.initscr()
curses.start_color()
curses.noecho()
curses.halfdelay(REFRESH * 10) # reset with nocbreak, blocking value is x 0.1 seconds
# store window dimensions
MAXYX = stdscr.getmaxyx()
# some terminals don't like invisible cursors
try:
	curses.curs_set(0)
	invisCursor = True
except curses.error:
	invisCursor = False

# color pairs for curses, keeping all colors < 8 for dumb terminals
COLOR_GOLD = 1
curses.init_pair(COLOR_GOLD, 3, 0)
COLOR_GREEN = 2
curses.init_pair(COLOR_GREEN, 2, 0)
COLOR_WHITE = 3
curses.init_pair(COLOR_WHITE, 7, 0)
COLOR_BLUE = 4
curses.init_pair(COLOR_BLUE, 4, 0)
COLOR_PINK = 5
curses.init_pair(COLOR_PINK, 5, 0)
COLOR_RED = 6
curses.init_pair(COLOR_RED, 1, 0)
COLOR_LTBLUE = 7
curses.init_pair(COLOR_LTBLUE, 6, 0)

# init LED grid, rows and chain length are both required parameters:
options = RGBMatrixOptions()
options.rows = 32
options.chain_length = 1
options.parallel = 1
options.hardware_mapping = 'adafruit-hat'  # If you have an Adafruit HAT: 'adafruit-hat'
matrix = RGBMatrix(options = options)
# fresh canvas
m = Image.new("RGB", (32,32), "black")
d = ImageDraw.Draw(m)


# LND RPC setup
os.environ["GRPC_SSL_CIPHER_SUITES"] = 'HIGH+ECDSA'
cert = open(os.path.expanduser('/home/pi/.lnd/tls.cert'), 'rb').read()
creds = grpc.ssl_channel_credentials(cert)
channel = grpc.secure_channel('localhost:10009', creds)
stub = lnrpc.LightningStub(channel)

#############
# functions #
#############

# stash cursor in the bottom right corner in case terminal won't invisiblize it
def hideCursor():
	stdscr.addstr(MAXYX[0]-1, MAXYX[1]-1, "")

# LND interface
def getinfo():
	return stub.GetInfo(ln.GetInfoRequest())
def listpeers():
	return stub.ListPeers(ln.ListPeersRequest())
def getnodeinfo(pk):
	return stub.GetNodeInfo(ln.NodeInfoRequest(pub_key=pk))
def listchannels():
	return stub.ListChannels(ln.ListChannelsRequest()).channels
def listactivechannels():
	ac = []
	chans = stub.ListChannels(ln.ListChannelsRequest()).channels
	for chan in chans:
		if chan.active:
			ac.append(chan)
	return ac

# debug terminal displays
def printpeers():
	peers = listpeers()
	for peer in peers.peers:
		pk = peer.pub_key
		ni = getnodeinfo(pk)
		print ni.node.alias, ni.node.addresses[0].addr
		print ni.node.pub_key
		print "--"
def printchans():
	chans = listchannels()
	print len(chans), "channels:"
	print '%-34.32s%-9.8s%-4.3s%-9.8s' %  ("Alias", "Chn Cap", "#ch", "Peer Cap")
	print "_______________________________________________________"
	for chan in chans:
		pk = chan.remote_pubkey
		peer = getnodeinfo(pk)
		print '%-34.32s%-9.8s%-4.3s%-9.8s' %  (peer.node.alias, chan.capacity, peer.num_channels, peer.total_capacity)
		#print chan.capacity, chan.local_balance, chan.remote_balance
def printimg(m):
	for x in range(32):
		for y in range(32):
			p = m.getpixel((x,y))
			q = sum(p)
			if q == 0:
				q = "   "
			print str(q).zfill(3),
		print
def printbig(m):
	for x in range(32):
		for y in range(32):
			p = m.getpixel((x,y))
			if p == (0,0,0):
				p = " "
			print '%-15.14s' % (str(p)),	# (234, 789, 234)
		print

# utility
def hextorgb(h):
	h = h.lstrip('#')
	return tuple( int(h[i:i+2], 16) for i in (0, 2, 4) )
def mycolor():
	me = getinfo()
	myinfo = getnodeinfo(me.identity_pubkey)
	return myinfo.node.color
def stringtocolor(s):
	hex = hashlib.sha256(str(s)).hexdigest()
	return tuple( int(hex[i:i+2], 16) for i in (0, 2, 4) )


# LED grid
def drawgraph(o):
	# clear
	d.rectangle([0, 0, 31, 31], fill=(0,0,0), outline=(0,0,0))
	# get channels info
	if ACTIVE_ONLY:
		chans = listactivechannels()
	else:
		chans = listchannels()
	numchans = len(chans)
	angle = 0
	# draw grpah rotated by offset
	for chan in chans:
		# get info for this peer
		pk = chan.remote_pubkey
		peer = getnodeinfo(pk)
		# locate peer
		tox = round(math.sin(math.radians(angle + o)) * EDGELEN)
		toy = round(math.cos(math.radians(angle + o)) * EDGELEN)
		# locate halfway point in line to peer
		halftox = round(math.sin(math.radians(angle + o)) * (EDGELEN/2))
		halftoy = round(math.cos(math.radians(angle + o)) * (EDGELEN/2))
		
		# don't draw lines if amount is zero
		# draw line to peer with THEIR (remote) channel balance
		if chan.remote_balance != 0:
			fullColor = (0,0,0) if chan.remote_balance == 0 else stringtocolor(chan.remote_balance)
			d.line([MEX+halftox, MEY+halftoy, MEX+tox, MEY+toy], fill=fullColor, width=1)
		
		# draw half line to peer with OUR (local) channel balance
		if chan.local_balance != 0:
			halfColor = (0,0,0) if chan.local_balance == 0 else stringtocolor(chan.local_balance)
			d.line([MEX, MEY, MEX+halftox, MEY+halftoy], fill=halfColor, width=1)
		
		# inc angle for next peer
		angle += (360/numchans)
		# draw peer on top
		d.rectangle([MEX+tox, MEY+toy, MEX+tox+PEERSIZE, MEY+toy+PEERSIZE], fill=None, outline=hextorgb(peer.node.color))

	# add me in the center on top, big!
	#d.rectangle([MEX-PEERSIZE, MEY-PEERSIZE, MEX+PEERSIZE, MEY+PEERSIZE], fill=None, outline=hextorgb(mycolor()))
	# not big
	#d.point([MEX, MEY], hextorgb(mycolor()))
	# circle?
	d.ellipse([MEX-PEERSIZE, MEY-PEERSIZE, MEX+PEERSIZE, MEY+PEERSIZE], fill=hextorgb(mycolor()), outline=hextorgb(mycolor()))

# terminal curses display
def printinfo():
	# console is 94x28

	# get lnd channel list
	chans = listchannels()

	# clear and print titles
	stdscr.erase()
	stdscr.addstr(0, 0, "Total Channels: " + str(len(chans)))
	t = '%-34.32s%-9.8s%-9.8s%-9.8s%-6.5s%-4.3s%-9.8s' %  ("Alias", "Capacity", "Local", "Remote", "Peer:", "#Ch", "Capacity")
	stdscr.addstr(1, 0, t)
	# stdscr.addstr(2, 0, "_______________________________________________________________________________")

	# print channels
	line = 1
	tCap, tLoc, tRem, tNum, tPeercap = (0, 0, 0, 0, 0)
	for chan in chans:
		line +=1

		# get peerinfo for each channel
		pk = chan.remote_pubkey
		peer = getnodeinfo(pk)

		# line color depends on channel activity
		color = curses.color_pair(COLOR_LTBLUE) if chan.active else curses.color_pair(COLOR_RED)

		# print channel info line
		alias = unicodedata.normalize('NFKD', peer.node.alias).encode('ascii','ignore')
		s = '%-34.32s%-9.8s%-9.8s%-9.8s%-6.5s%-4.3s%-9.8s' % (alias, chan.capacity, chan.local_balance, chan.remote_balance, "", peer.num_channels, peer.total_capacity)
		stdscr.addstr(line, 0, s, color)

		# update totals
		tCap += chan.capacity
		tLoc += chan.local_balance
		tRem += chan.remote_balance
		tNum += peer.num_channels
		tPeercap += peer.total_capacity

	# print totals
	line += 1
	s = '%-34.32s%-9.8s%-9.8s%-9.8s%-6.5s%-4.3s%-9.8s' % ("TOTALS:", tCap, tLoc, tRem, "", tNum, tPeercap)
	stdscr.addstr(line, 0, s, curses.color_pair(COLOR_GREEN))


	# print menu on bottom
	menu = "[Q]uit"
	stdscr.addstr(MAXYX[0]-1, 0, menu)

	# stash cursor
	hideCursor()

# check for keyboard input -- also serves as the pause between REFRESH cycles
def checkKeyIn():
	keyNum = stdscr.getch()
	if keyNum == -1:
		return False
	else:
		key = chr(keyNum)

	if key in ("q", "Q"):
		sys.exit()

# debug print index to terminal
#os.system('clear')
#printchans()

# loop!
o = 0
while True:
	# create and rotate final image
	drawgraph(o)

	# draw to terminal
	#os.system('clear')
	#printimg(m)
	#printbig(m)
	printinfo()

	# draw to LED matrix
	matrix.Clear()
	matrix.SetImage(m, 0, 0)

	# incremenet rotate and wait
	o = (o+3) % 360
	checkKeyIn()
