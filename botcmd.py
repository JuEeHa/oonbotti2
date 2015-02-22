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

def chmode(irc, chan, nick, mode, args):
	if args == []:
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

class ArgsfmtError(Exception):
	def __init__(self, msg):
		self.msg = msg
	def __str__(self):
		return 'Error with argument format: '+msg

ARG_STD = 0
ARG_OPT = 1
ARG_UNL = 2

def parseargsfmt(args):
	# parses the argument format used by matchcmd and parsecmd
	# e.g. parseargsfmt("foo [bar] {baz} ) -> [ARG_STD, ARG_OPT, ARG_UNL]
	
	args = args.split(' ')
	out = []
	for arg in args:
		if len(arg) >= 2 and arg[0] == '[' and arg[-1] == ']': # Optional (0-1) argument: [bar]
			out.append(ARG_OPT)
		elif len(arg) >= 2 and arg[0] == '{' and arg[-1] == '}': # Unlimited (0-) number of arguments: {baz}
			out.append(ARG_UNL)
		else: # Normal argument: foo
			out.append(ARG_STD)
	
	return out

def getargnums(argtypes):
	min = 0
	max = 0 # max = None if number of arguments is unlimited
	
	for argtype in argtypes:
		if argtype == ARG_STD:
			min += 1
			if max != None: # Don't try to increment if max is unlimited
				max += 1
		elif argtype == ARG_OPT:
			if max != None: # Don't try to increment if max is unlimited
				max += 1
		elif argtype == ARG_UNL:
			max = None
	
	return min, max

def matchcmd(line, cmd, args=None):
	# matchcmd(line, cmd) matched if the command cmd is used, matchcmd(line, cmd, args) checks whether the args match too
	
	if len(line) == 0:
		return False
	if line[0] != cmd:
		return False
	
	if not args:
		return True
	
	min, max = getargnums(parseargsfmt(args))
	
	if max and len(line)-1 >= min and len(line)-1 <= max:
		return True
	elif not max and len(line)-1 >= min:
		return True
	else:
		return False

def parsecmd(line, args):
	# Returns a tuple containing the arguments. An optional argument that didn't get a value will be assigned ''
	argtypes = parseargsfmt(args)
	
	if len(argtypes) >= 1 and ARG_UNL in argtypes[:-1]: # Disallow non-final unlimited arguments
		raise ArgsfmtError('Non-final unlimited argument')
	if len(filter((lambda type: type == ARG_OPT or type == ARG_UNL), argtypes)) > 1: # Disallow more than one optional or unlimited argument per argument string
		raise ArgsfmtError('Ambiguous argument format')
	
	# Remove the command
	if len(line) == 0:
		raise ArgsfmtError('No command given')
	line = line[1:]
	
	min, max = getargnums(argtypes)
	if len(line) == min:
		# Only standard arguments given
		out = []
		for type in argtypes:
			if type == ARG_STD:
				out.append(line[0])
				line = line[1:]
			else:
				out.append('')
	elif max and len(line) == max:
		# Optional argument given
		out = []
		for type in argtypes:
			if type == ARG_STD or type == ARG_OPT:
				out.append(line[0])
				line = line[1:]
			else:
				out.append('')
	elif not max and len(line) > min:
		# Unlimited argument given
		out = []
		for type in argtypes:
			if type == ARG_STD or type == ARG_OPT:
				out.append(line[0])
				line = line[1:]
			elif type == ARG_UNL:
				out.append(' '.join(line))
				line = []
	else:
		raise ArgsfmtError('Number of given arguments not possible for given format string')
	
	if len(out) == 1:
		return out[0]
	else:
		return out
	
def parse((line,irc)):
	line=line.split(' ')
	nick=line[0].split('!')[0][1:]
	chan=line[2] if line[2][0]=='#' else nick
	
	zwsp = '\xe2\x80\x8b'
	
	if nick in blacklist:
		return
	elif len(line) >= 4 and len(line[3]) >= 4 and line[3][:len(zwsp)+1] == ':'+zwsp: # If line begins with ZWSP
		return
	
	if line[1]=='PRIVMSG':
		cmdline = [line[3][1:]] + line[4:]
		while '' in cmdline:
			cmdline.remove('')
		if matchcmd(cmdline, '#echo'):
			text = parsecmd(cmdline, '{text}')
			print text #debg
			irc.msg(chan, zwsp+text)
		elif matchcmd(cmdline, '#op'):
			args = parsecmd(cmdline, '{args}')
			chmode(irc, chan, nick, '+o', args.split(' '))
		elif matchcmd(cmdline, '#deop'):
			args = parsecmd(cmdline, '{args}')
			chmode(irc, chan, nick, '-o', args.split(' '))
		elif matchcmd(cmdline, '#voice'):
			args = parsecmd(cmdline, '{args}')
			chmode(irc, chan, nick, '+v', args.split(' '))
		elif matchcmd(cmdline, '#devoice'):
			args = parsecmd(cmdline, '{args}')
			chmode(irc, chan, nick, '-v', args.split(' '))
		elif matchcmd(cmdline, '#kick'):
			if matchcmd(cmdline, '#kick', 'nick {reason}'):
				kicknick, kickreason = parsecmd(cmdline, 'nick {reason}')
				if kicknick.lower() == irc.nick:
					irc.send('KICK %s %s :Fuck you' % (chan, nick))
				elif random.randint(0,9) == 0 and len(line) == 5:
					irc.send('KICK %s %s :Bam' % (chan, nick))
				else:
					if isauthorized(irc, nick):
						irc.send('KICK %s %s :%s'%(chan, kicknick, kickreason))
			else:
				irc.msg(chan, 'Usage #kick nick reason')
		elif matchcmd(cmdline, '#src'):
			irc.msg(chan, 'https://github.com/JuEeHa/oonbotti2')
		elif matchcmd(cmdline, '#prefix') and chan == '#osdev-offtopic':
			irc.msg(chan, 'gopher://smar.fi:7070/0/hash-prefix')
		elif matchcmd(cmdline, '#msg'):
			if matchcmd(cmdline, '#msg', 'nick {message}'):
				msgnick, message = parsecmd(cmdline, 'nick {message}')
				msglock.acquire()
				if msgnick not in msgs:
					msgs[msgnick] = []
				msgs[msgnick].append((nick, message))
				msglock.release()
			else:
				irc.msg(chan, 'Usage: #msg nick message')
		elif matchcmd(cmdline, '#trusted?'):
			if matchcmd(cmdline, '#trusted?', '[nick]'):
				trustnick = parsecmd(cmdline, '[nick]')
				if trustnick == '':
					trustnick=nick
				if istrusted(trustnick):
					irc.msg(chan, '%s is trusted' % trustnick)
				else:
					irc.msg(chan, '%s is not trusted' % trustnick)
			else:
				irc.msg(chan, 'Usage: #trusted? [nick]')
		elif matchcmd(cmdline, '#trust'):
			if matchcmd(cmdline, '#trust', 'nick'):
				trustnick = parsecmd(cmdline, 'nick')
				if isauthorized(irc, nick):
					addtrusted(trustnick)
			else:
				irc.msg(chan, 'Usage #trust nick')
		elif matchcmd(cmdline, '#untrust'):
			if matchcmd(cmdline, '#untrust', 'nick'):
				untrustnick = parsecmd(cmdline, 'nick')
				godslock.acquire()
				if untrustnick not in gods:
					if isauthorized(irc, nick):
						rmtrusted(untrustnick)
				godslock.release()
			else:
				irc.msg(chan, 'Usage #untrust nick')
		elif matchcmd(cmdline, '#ls-trusted'):
			trustedlock.acquire()
			irc.msg(nick, ', '.join(trusted))
			trustedlock.release()
		elif matchcmd(cmdline, '#invite'):
			if matchcmd(cmdline, '#invite', 'nick'):
				invitenick = parsecmd(cmdline, 'nick')
				if isauthorized(irc, nick):
					irc.send('INVITE %s %s' % (invitenick, chan))
			else:
				irc.msg(chan, 'Usage #invite nick')
		elif matchcmd(cmdline, '#help'):
			if matchcmd(cmdline, '#help', '[command]'):
				command = parsecmd(cmdline, '[command]')
				helptext = help(command)
				if helptext:
					irc.msg(chan, zwsp+helptext)
		elif matchcmd(cmdline, '#esoteric') and chan=='#esoteric':
			irc.msg(chan, 'Nothing here')
		elif cmdline[0] in [irc.nick, irc.nick+',', irc.nick+':']:
			question = parsecmd(cmdline, '{question}')
			irc.msg(chan, '%s: %s' % (nick, doctor.respond(question)))
		elif die_expr.match(cmdline[0]):
			die=cmdline[0][1:].split('d')
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
