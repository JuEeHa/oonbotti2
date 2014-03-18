#!/usr/bin/python
import threading
import time
import socket
import sys

import botcmd

class Channel:
	def __init__(self):
		self.lock=threading.Lock()
		self.msg=[]
	def send(self,msg):
		self.lock.acquire()
		self.msg.append(msg)
		self.lock.release()
	def recv(self,wait=True):
		while True:
			self.lock.acquire()
			if len(self.msg)>0:
				msg=self.msg.pop(0)
				self.lock.release()
				return msg
			if not wait:
				self.lock.release()
				return None
			self.lock.release()
			time.sleep(0.1)

class Connhandler(threading.Thread):
	def __init__(self,server,port,chan,nick,botname,inpc,logc):
		threading.Thread.__init__(self)
		self.server=server
		self.port=port
		self.nick=nick
		self.name=botname
		self.chan=chan
		self.inpc=inpc
		self.logc=logc
	def send(self,s):
		self.sock.send(s+'\r\n')
		if s.split(' ')[0]!='PONG':
			self.logc.send(s+'\n')
	def check(self,line):
		if line.split(' ')[0]=='PING':
			self.send('PONG :hjdicks')
		else:
			self.logc.send(line+'\n')
			Threadwrapper(botcmd.parse,(line,self.inpc)).start()
	def run(self):
		self.sock=None
		for af, socktype, proto, canonname, sa in socket.getaddrinfo(self.server,self.port,socket.AF_UNSPEC,socket.SOCK_STREAM):
			try:
				self.sock=socket.socket(af, socktype, proto)
			except socket.error:
				self.sock=None
				conntinue
			try:
				self.sock.connect(sa)
			except socket.error:
				self.sock.close()
				self.sock=None
				continue
			break
		if self.sock is None:
			self.logc.send('QUIT');
			sys.exit(1);
		self.sock.settimeout(0.1)
		
		self.send('NICK %s'%self.nick)
		self.send('USER %s a a :%s'%(self.nick,self.name))
		f=open('startcmd.txt','r')
		for i in f:
			if i[-1]=='\n': i=i[:-1]
			self.send(i)
		f.close()
		for i in self.chan.split(' '):
			self.send('JOIN %s'%(i))
		
		buf=''
		while True:
			while True:
				try:
					data=self.sock.recv(4096)
					break
				except:
					pass
				cmd=self.inpc.recv(wait=False)
				if cmd=='QUIT':
					data=None
					self.logc.send('QUIT')
					break
				elif cmd:
					self.send(cmd)
				time.sleep(0.1)
			if not data: break
			buf+=data
			buf=buf.split('\n')
			for line in buf[:-1]:
				if line[-1]=='\r': line=line[:-1]
				self.check(line)
			buf=buf[-1]
		self.sock.close()

class Keyhandler(threading.Thread):
	def __init__(self,outc):
		self.outc=outc
		threading.Thread.__init__(self)
	def run(self):
		while True:
			line=raw_input()
			c=line.split(' ')
			if c[0] in botcmd.concmd:
				botcmd.execcmd(c)
			if c[0]=='/j' and len(c)==2:
				self.outc.send('JOIN '+c[1])
			elif c[0]=='/m' and len(c)>2:
				self.outc.send('PRIVMSG %s :%s'%(c[1],' '.join(c[2:])))
			elif c[0]=='/q' and len(c)==1:
				self.outc.send('QUIT')
				break
			elif c[0][0]=='/' and c[0] not in botcmd.concmd:
				self.outc.send(c[0][1:].upper()+' '+' '.join(c[1:]))

class Loghandler(threading.Thread):
	def __init__(self,inpc):
		self.inpc=inpc
		threading.Thread.__init__(self)
	def run(self):
		while True:
			s=self.inpc.recv()
			if s=='QUIT': break
			sys.stdout.write(''.join([i if ord(i)>=32 or i=='\n' else '^'+chr(ord(i)+64) for i in s]))

class Threadwrapper(threading.Thread):
	def __init__(self,func,arg):
		self.func=func
		self.arg=arg
		threading.Thread.__init__(self)
	def run(self):
		self.func(self.arg)

if len(sys.argv)!=5:
	print 'Usage: '+sys.argv[0]+' server port channel nick'
else:
	keych=Channel()
	logch=Channel()
	Keyhandler(keych).start()
	Loghandler(logch).start()
	Connhandler(sys.argv[1],int(sys.argv[2]),sys.argv[3],sys.argv[4],sys.argv[4],keych,logch).start()
