#!/usr/bin/env python3
# encoding: utf-8
"""
portforwarder.py

Created by Sandro Gauci on 2014-03-18.
Modified by Q5Ca on 2019-11-27
"""

import sys
import os
import asyncio
import argparse
import json
from pprint import pprint
import time
import re

config = None

class Filter:
	@staticmethod
	def filter_request(data, id):
		rules = config['filter_request']
		regex_rules = rules['regex']
		hex_rules = rules['hex']
		string_rules = rules['string']
		for re_rule in regex_rules:
			try:
				if re.search(re_rule['sign'], data.decode()):
					Filter.log('[WARNING] regex %s in request %s\r\n' % (re_rule['sign'], id))
					if re_rule['action'] != 0:
						return re_rule['action']
			except:
				Filter.log('[WARNING] Cant search regex request %s\r\n' % (id))
				# pass
		for hex_rule in hex_rules:
			if bytes.fromhex(hex_rule['sign']) in data:
				Filter.log('[WARNING] hex %s in request %s\r\n' % (hex_rule['sign'], id))
				if hex_rule['action'] != 0:
					return hex_rule['action']
		for string_rule in string_rules:
			if string_rule['sign'] in str(data):
				Filter.log('[WARNING] string %s in request %s\r\n' % (string_rule['sign'], id))
				if string_rule['action'] != 0:
					return string_rule['action']
		return 0

	@staticmethod
	def filter_response(data, id):
		if 'SVATTT' in str(data):
			Filter.log('[WARNING] SVATTT in response %s\r\n' % (id))
			# return 1

		rules = config['filter_response']
		regex_rules = rules['regex']
		hex_rules = rules['hex']
		string_rules = rules['string']
		for re_rule in regex_rules:
			try:
				if re.search(re_rule['sign'], data.decode()):
					Filter.log('[WARNING] regex %s in response %s\r\n' % (re_rule['sign'], id))
					if re_rule['action'] != 0:
						return re_rule['action']
			except:
				Filter.log('[WARNING] Cant search regex response %s\r\n' % (id))
				# pass
		for hex_rule in hex_rules:
			if bytes.fromhex(hex_rule['sign']) in data:
				Filter.log('[WARNING] hex %s in request %s\r\n' % (hex_rule['sign'], id))
				if hex_rule['action'] != 0:
					return hex_rule['action']
		for string_rule in string_rules:
			if string_rule['sign'] in str(data):
				Filter.log('[WARNING] string %s in response %s\r\n' % (string_rule['sign'], id))
				if string_rule['action'] != 0:
					return string_rule['action']
		return 0

	@staticmethod
	def log(mess):
		with open(config['log_filter'], 'a') as f:
			f.write(mess)

# starts the connection with the real server
class ForwardedConnection(asyncio.Protocol):
	
	def __init__(self, peer):
		self.peer = peer
		self.transport = None
		self.buff = list()
		self.id = None

	# when a connection is made, we check if there's anything that was sent 
	# previously and stored in a buffer, and we send it immediately
	def connection_made(self, transport):
		self.transport = transport
		if len(self.buff) > 0:
			self.transport.writelines(self.buff)
			self.buff = list()
	
	def data_received(self,data):
		with open(config['log_access'], 'a') as f:
			f.write('\r\n[INFO] Response [id: %s] \r\n' % self.id)
			try:
				f.write(data.decode())
			except:
				f.write(str(data))
		
		action = Filter.filter_response(data, self.id)
		if action == 0:
			self.peer.write(data)
		elif action == 1:
			self.peer.close()
		else:
			self.peer.write(action.encode())
			self.peer.close()
	
	def connection_lost(self, exc):
		self.peer.close()

# an instance of PortForwarder will be created for each client connection.
class PortForwarder(asyncio.Protocol):
	def __init__(self, dsthost, dstport):
		self.dsthost = dsthost 
		self.dstport = dstport
		
	def connection_made(self, transport):
		self.transport = transport
		loop = asyncio.get_event_loop()
		self.fcon = ForwardedConnection(self.transport)
		asyncio.ensure_future(loop.create_connection(lambda: self.fcon, self.dsthost, self.dstport))
		

	def data_received(self, data):
		id = time.time()
		with open(config['log_access'], 'a') as f:
			f.write('\r\n[INFO] Request from %s:%s [id: %s]\r\n'% (self.transport.get_extra_info('socket').getpeername()[0], self.transport.get_extra_info('socket').getpeername()[1], id))
			try:
				f.write(data.decode())
			except:
				f.write(str(data))

		action = Filter.filter_request(data, id)
		if action == 0:
			self.fcon.id = id
			if self.fcon.transport is None:
				self.fcon.buff.append(data)
			else:
				self.fcon.transport.write(data)
		elif action == 1:
			self.transport.close()
		else:
			self.transport.write(action.encode())
			self.transport.close()


	def connection_lost(self, exc):
		if not self.fcon.transport is None:
			self.fcon.transport.close()


def parse_config():
	parser = argparse.ArgumentParser(description="forward a local port to a remote host")
	parser.add_argument('file', help='config file')
	global config
	config = json.load(open(parser.parse_args().file))
	config['log_access'] = config['id'] + '_access.log'
	config['log_filter'] = config['id'] + '_filter.log'
	pprint(config)

def main():
	parse_config()
	loop = asyncio.get_event_loop()
	server = loop.run_until_complete(loop.create_server(lambda: PortForwarder(config['remote_host'], config['remote_port']), '0.0.0.0', config['local_port']))
	print('Forwarding localhost:%s <-> %s:%s ...' % (config['local_port'], config['remote_host'],  config['remote_port']))
	try:
		loop.run_until_complete(server.wait_closed())
	except KeyboardInterrupt:
		sys.stderr.flush()
		print('\nStopped\n')

if __name__ == '__main__':
	main()


