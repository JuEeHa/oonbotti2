import eliza
import threading
import random
import re
import time

concmd=['/q','/lt','/st','/lg']

blacklist=['bslsk05']

doctor=eliza.eliza()
trusted=[]
trustedlock=threading.Lock()
gods=[]
godslock=threading.Lock()
msgs={}
msglock=threading.Lock()
authcheck={}
authchecklock=threading.Lock()

die_expr=re.compile("#[0-9]*d([0-9]+|%)")

class Cron(threading.Thread):
	def __init__(self):
		self.timedjobs=[]
		self.timedjobslock=threading.Lock()
		self.cronctrl=[]
		self.cronctrllock=threading.Lock()
		threading.Thread.__init__(self)
	def queuejob(self, time, fn):
		self.timedjobslock.acquire()
		self.timedjobs.append((time, fn))
		self.timedjobslock.release()
	def ctrl(self, cmd):
		self.cronctrllock.acquire()
		self.cronctrl.append(cmd)
		self.cronctrllock.release()
	def run(self):
		run=True
		while run:
			time.sleep(1) # Accuracy doesn't need to be high
			
			self.cronctrllock.acquire()
			for cmd in self.cronctrl:
				if cmd=='QUIT':
					run=False
			self.cronctrl=[]
			self.cronctrllock.release()
			
			self.timedjobslock.acquire()
			self.timedjobs=map((lambda (time,fn): (time-1,fn)), self.timedjobs)
			torun=map((lambda (time,fn): fn), filter((lambda (time,fn): time<=0), self.timedjobs))
			self.timedjobs=filter((lambda (time,fn): time>0), self.timedjobs)
			self.timedjobslock.release()
			
			for fn in torun:
				fn()

msglock.acquire()
f=open('msgs.txt','r')
for line in f:
	while len(line)>0 and line[-1]=='\n': line=line[:-1]
	if len(line)>0:
		receiver,sender,msg=line.split('\t')
		if receiver not in msgs:
			msgs[receiver]=[]
		msgs[receiver].append((sender,msg))
f.close()
msglock.release()

cron=Cron()
cron.start()

def addtrusted(nick):
	trustedlock.acquire()
	if nick not in trusted:
		trusted.append(nick)
	trustedlock.release()

def rmtrusted(nick):
	trustedlock.acquire()
	if nick in trusted:
		trusted.remove(nick)
	trustedlock.release()

def loadtrusted():
	trustedlock.acquire()
	while len(trusted)>0: trusted.pop() #I'm really sorry but trusted=[] created trusted as local variable
	trustedlock.release()
	f=open('trusted.txt','r')
	for line in f:
		while len(line)>0 and line[-1]=='\n': line=line[:-1]
		if len(line)>0:
			addtrusted(line)
	f.close()

def loadgods():
	godslock.acquire()
	while len(gods)>0: gods.pop() #See above
	f=open('gods.txt','r')
	for line in f:
		while len(line)>0 and line[-1]=='\n': line=line[:-1]
		if len(line)>0:
			gods.append(line)
			addtrusted(line)
	f.close()
	godslock.release()

def savetrusted():
	trustedlock.acquire()
	f=open('trusted.txt','w')
	for i in trusted:
		f.write(i+'\n')
	f.close
	trustedlock.release()
	
loadtrusted()
loadgods()

def chmode(irc,chan,nick,mode,args):
	if len(args)==0:
		if isauthorized(irc, nick):
			irc.send('MODE %s %s %s'%(chan,mode,nick))
	else:
		for name in args:
			if isauthorized(irc, nick):
				irc.send('MODE %s %s %s'%(chan,mode,name))

def istrusted(nick):
	trustedlock.acquire()
	if nick in trusted:
		trustedlock.release()
		return True
	else:
		trustedlock.release()
		return False

def initauthcheck(nick):
	global authcheck, authchecklock
	authchecklock.acquire()
	authcheck[nick]=None
	authchecklock.release()

def setauthcheckstate(nick, state):
	global authcheck, authchecklock
	authchecklock.acquire()
	if nick in authcheck:
		authcheck[nick]=state
	authchecklock.release()

def getauthcheckstate(nick):
	global authcheck, authchecklock
	authchecklock.acquire()
	if nick in authcheck:
		state=authcheck[nick]
	authchecklock.release()
	return state

def removeauthcheck(nick):
	global authcheck, authchecklock
	authchecklock.acquire()
	if nick in authcheck:
		del authcheck[nick]
	authchecklock.release()

def isauthorized(irc, nick):
	if not istrusted(nick):
		return False
	
	initauthcheck(nick)
	irc.msg('NickServ', 'acc '+nick)
	cron.queuejob(5, (lambda : setauthcheckstate(nick, False)))
	
	state=None
	while state==None:
		state=getauthcheckstate(nick)
		time.sleep(0.1)
	removeauthcheck(nick)
	
	return state

def parse((line,irc)):
	line=line.split(' ')
	nick=line[0].split('!')[0][1:]
	chan=line[2] if line[2][0]=='#' else nick
	
	if nick in blacklist:
		return
	elif len(line) >= 4 and len(line[3]) >= 4 and line[3][:4] == ':\xe2\x80\x8b': # If line begins with ZWSP
		return
	
	if line[1]=='PRIVMSG':
		if line[3]==':#echo':
			irc.msg(chan, '\xe2\x80\x8b'+' '.join(line[4:]))
		elif line[3]==':#op':
			chmode(irc,chan,nick,'+o',line[4:])
		elif line[3]==':#deop':
			chmode(irc,chan,nick,'-o',line[4:])
		elif line[3]==':#voice':
			chmode(irc,chan,nick,'+v',line[4:])
		elif line[3]==':#devoice':
			chmode(irc,chan,nick,'-v',line[4:])
		elif line[3]==':#kick':
			if len(line)>4:
				if line[4].lower()==irc.nick:
					irc.send('KICK %s %s :Fuck you'%(chan,nick))
				elif random.randint(0,9)==0 and len(line)==5:
					irc.send('KICK %s %s :Bam'%(chan,nick))
				else:
					if isauthorized(irc, nick):
						irc.send('KICK %s %s :%s'%(chan,line[4],' '.join(line[5:])))
			else:
				irc.msg(chan, 'Usage #kick nick reason')
		elif line[3]==':#src':
			irc.msg(chan, 'https://github.com/JuEeHa/oonbotti2')
		elif line[3]==':#prefix' and chan=='#osdev-offtopic':
			irc.msg(chan, 'gopher://smar.fi:7070/0/hash-prefix')
		elif line[3]==':#msg':
			if len(line)>5:
				msglock.acquire()
				if line[4] not in msgs:
					msgs[line[4]]=[]
				msgs[line[4]].append((nick,' '.join(line[5:])))
				msglock.release()
			else:
				irc.msg(chan, 'Usage: #msg nick message')
		elif line[3]==':#trusted?':
			trustnick=None
			if len(line)==5:
				trustnick=line[4]
			elif len(line)==4:
				trustnick=nick
			else:
				irc.msg(chan, 'Usage #trusted? [nick]')
			if istrusted(nick):
				irc.msg(chan, '%s is trusted')
			else:
				irc.msg(chan, '%s is not trusted')
		elif line[3]==':#trust':
			if len(line)==5:
				if isauthorized(irc, nick):
					addtrusted(line[4])
			else:
				irc.msg(chan, 'Usage #trust nick')
		elif line[3]==':#untrust':
			if len(line)==5:
				godslock.acquire()
				if line[4] not in gods:
					if isauthorized(irc, nick):
						rmtrusted(line[4])
				godslock.release()
			else:
				irc.msg(chan, 'Usage #untrust nick')
		elif line[3]==':#ls-trusted':
			trustedlock.acquire()
			irc.msg(nick, ', '.join(trusted))
			trustedlock.release()
		elif line[3]==':#invite':
			if len(line)==5:
				if authorized(irc, nick):
					irc.send('INVITE %s %s' % (line[4], chan))
			else:
				irc.msg(chan, 'Usage #invite nick')
		elif line[3]==':#help':
			helptext=help(' '.join(line[4:]))
			if helptext:
				irc.msg(chan, helptext)
		elif line[3]==':#esoteric' and chan=='#esoteric':
			irc.msg(chan, 'Nothing here')
		elif line[3][1:] in [irc.nick, irc.nick+',', irc.nick+':']:
			irc.msg(chan, '%s: %s' % (nick, doctor.respond(' '.join(line[4:]))))
		elif die_expr.match(line[3][1:]):
			die=line[3][2:].split('d')
			times=int(die[0]) if die[0] else 1
			die='%' if die[1]=='%' else int(die[1])
			if die=='%':
				if times!=1:
					irc.msg(chan, 'Not supported')
				else:
					irc.msg(chan, '%s%s' % (random.randint(0,9), random.randint(0,9)))
			elif die<2:
				irc.msg(chan, 'This die is not available in your space-time region.')
			elif times<1:
				irc.msg(chan, 'What exactly do you want me to do?')
			elif times>128:
				irc.msg(chan, 'Sorry, I don\'t have that many. Can I borrow yours?')
			else:
				rolls=[random.randint(1, die) for i in xrange(times)]
				result=reduce((lambda x,y:x+y), rolls)
				if times>1:
					irc.msg(chan, '%s (%s)' % (str(result), ', '.join([str(i) for i in rolls])))
				else:
					irc.msg(chan, str(result))
	elif line[1]=='NOTICE' and line[0].split('!')[0]==':NickServ' and  line[4]=='ACC':
		if line[5]=='3' or line[5]=='2':
			setauthcheckstate(line[3][1:], True)
		else:
			setauthcheckstate(line[3][1:], False)
			if line[5]=='0':
				irc.msg(line[3][1:], 'Register account with NickServ')
			elif line[5]=='1':
				irc.msg(line[3][1:], 'PRIVMSG %s :Identify with NickServ')
			else:
				irc.msg(line[3][1:], 'WTF, NickServ returned %s'+line[5])
	elif line[1]=='INVITE' and line[2]==irc.nick and line[3][1:] in irc.chan.split(' '):
		if isauthorized(irc, nick):
			irc.send('JOIN '+line[3])
	elif line[1]=='482':
		irc.msg(line[3], 'Not op')
	#elif line[1]=='332' or line[1]=='TOPIC':
	#	if line[1]=='332':
	#		ch=line[3]
	#		tp=' '.join(line[4:])[1:]
	#	elif line[1]=='TOPIC':
	#		ch=line[2]
	#		tp=' '.join(line[3:])[1:]
	#	#Do the magic here
	
	msglock.acquire()
	if (line[1]=='PRIVMSG' or line[1]=='JOIN') and nick in msgs:
		for sender,msg in msgs.pop(nick):
			irc.msg(nick, '<%s> %s' % (sender, msg))
	msglock.release()

def execcmd(cmdline):
	if cmdline[0]=='/q':
		msglock.acquire()
		f=open('msgs.txt','w')
		for receiver in msgs:
			for sender, msg in msgs[receiver]:
					f.write('%s\t%s\t%s\n'%(receiver,sender,msg))
		f.close()
		msglock.release()
		savetrusted()
		
		cron.ctrl('QUIT')
	elif cmdline[0]=='/lt':
		loadtrusted()
	elif cmdline[0]=='/st':
		savetrusted()
	elif cmdline[0]=='/lg':
		loadgods()

def help(cmd):
	if cmd=='':
		return '#echo #op #deop #voice #devoice #kick #src #msg #trusted? #trust #untrust #ls-trusted #invite #help'
	elif cmd=='#echo':
		return '#echo text      echo text back'
	elif cmd=='#op':
		return '#op [nick]      give nick or yourself op rights in case you are trusted by oonbotti2 and identified with NickServ'
	elif cmd=='#deop':
		return '#deop [nick]      remove your/nick\'s op rights'
	elif cmd=='#voice':
		return '#voice [nick]      give nick or yourself voice in case you are trusted by oonbotti2 and identified with NickServ'
	elif cmd=='#devoice':
		return '#devoice [nick]      remove your or nick\'s voice in case you are trusted by oonbotti2 and identified with NickServ'
	elif cmd=='#kick':
		return '#kick nick reason      kicks nick with specified reason'
	elif cmd=='#src':
		return '#src      paste a link to oonbotti2\'s git repo'
	elif cmd=='#msg':
		return '#msg nick message      send a message to nick'
	elif cmd=='#trusted?':
		return '#trusted? [nick]      tell you if nick or yourself is trusted by oonbotti2'
	elif cmd=='#trust':
		return '#trust nick      add nick to trusted list'
	elif cmd=='#untrust':
		return '#untrust nick      remove nick from trusted list'
	elif cmd=='#ls-trusted':
		return '#ls-trusted      list nicks that are trusted. use only in a query'
	elif cmd=='#invite':
		return '#invite nick      invites nick to channel'
	elif cmd=='#help':
		return '#help [command]      give short info of command or list commands'
	elif cmd=='me':
		return 'I shall.'
	else:
		return None
