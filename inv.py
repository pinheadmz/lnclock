#!/usr/bin/sudo python

################
# dependencies #
################

import time
import math
import rpc_pb2 as ln
import rpc_pb2_grpc as lnrpc
import grpc
import os
import unicodedata


# LND RPC setup
os.environ["GRPC_SSL_CIPHER_SUITES"] = 'HIGH+ECDSA'
cert = open(os.path.expanduser('/home/pi/.lnd/tls.cert'), 'rb').read()
creds = grpc.ssl_channel_credentials(cert)
channel = grpc.secure_channel('localhost:10009', creds)
stub = lnrpc.LightningStub(channel)

#############
# functions #
#############


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
def subtrans():
	res = stub.SubscribeTransactions(ln.GetTransactionsRequest())
	for r in res:
		print r
def subinvs():
	res = stub.SubscribeInvoices(ln.InvoiceSubscription())
	for r in res:
		print r


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


