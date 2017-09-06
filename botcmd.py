# TODO: python3-ify eliza and switch it back on
#import eliza
import threading
import random
import re
import time

concmd=['/q', '/lt', '/st', '/lg', '/lm', '/sm']

blacklist = ['bslsk05']

# TODO: python3-ify eliza and switch it back on
#doctor = eliza.eliza()

# channel: [user1, user2, ..., userN]
trusted = {}
trustedlock = threading.Lock()
gods = {}
godslock = threading.Lock()

# receiver: [(sender1, origin1, message1), (sender2, origin2, message2), ..., (senderN, origin2, messageN)]
msgs = {}
msgslock = threading.Lock()

# (ID, nick, account)
accountcheck = []
accountcheckid = 0
accountchecklock = threading.Lock()

die_expr=re.compile("#[0-9]*d([0-9]+|%)([+-][0-9]+)?$")

def initialize():
	global cron

	cron = Cron()
	cron.start()

	loadmessages()

	loadtrusted()
	loadgods()

class Cron(threading.Thread):
	def __init__(self):
		self.timedjobs = []
		self.timedjobslock = threading.Lock()
		self.cronctrl = []
		self.cronctrllock = threading.Lock()
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
		run = True
		while run:
			time.sleep(1) # Accuracy doesn't need to be high
			
			self.cronctrllock.acquire()
			for cmd in self.cronctrl:
				if cmd == 'QUIT':
					run = False
			self.cronctrl=[]
			self.cronctrllock.release()
			
			self.timedjobslock.acquire()
			self.timedjobs = [(time-1, fn) for (time, fn) in self.timedjobs]
			torun = [fn for time, fn in self.timedjobs if time<=0]
			self.timedjobs = [(time, fn) for (time, fn) in self.timedjobs if time>0]
			self.timedjobslock.release()
			
			for fn in torun:
				fn()

def loadmessages():
	global msgs, msgslock
	
	with msgslock:
		msgs = {}
		f = open('msgs.txt', 'r')
		
		for line in f:
			while len(line) > 0 and line[-1] == '\n':
				line = line[:-1]
			if len(line.split('\t')) == 4:
				receiver, sender, origin, msg = line.split('\t')
				if receiver not in msgs:
					msgs[receiver] = []
				msgs[receiver].append((sender, origin, msg))
		
		f.close()

def savemessages():
	global msgs, msgslock
	
	with msgslock:
		f=open('msgs.txt', 'w')
		
		for receiver in msgs:
			for sender, origin, msg in msgs[receiver]:
					f.write('%s\t%s\t%s\t%s\n' % (receiver, sender, origin, msg))
		
		f.close()

def addtrusted(chan, account):
	global trusted, trustedlock
	
	trustedlock.acquire()
	
	if chan not in trusted:
		trusted[chan] = []
	
	if account not in trusted[chan]:
		trusted[chan].append(account)
	
	trustedlock.release()

def rmtrusted(chan, account):
	global trusted, trustedlock
	
	trustedlock.acquire()
	
	if chan in trusted and account in trusted[chan]:
		trusted[chan].remove(account)
	
	trustedlock.release()

def loadtrusted():
	global trusted, trustedlock
	
	trustedlock.acquire()
	trusted = {}
	trustedlock.release()
	
	f=open('trusted.txt', 'r')
	
	for line in f:
		while len(line) > 0 and line[-1] == '\n':
			line = line[:-1]
		if len(line) > 0:
			chan, account = line.split()
			addtrusted(chan, account)
	
	f.close()

def loadgods():
	global gods, godslock
	
	godslock.acquire()
	gods = {}
	f=open('gods.txt', 'r')
	
	for line in f:
		while len(line) > 0 and line[-1] == '\n':
			line = line[:-1]
		if len(line) > 0:
			chan, account = line.split()
			
			if chan not in gods:
				gods[chan] = []
			
			gods[chan].append(account)
			addtrusted(chan, account)
	
	f.close()
	godslock.release()

def savetrusted():
	global trusted, trustedlock
	
	trustedlock.acquire()
	f=open('trusted.txt', 'w')
	
	for chan in trusted:
		for account in trusted[chan]:
			f.write('%s %s\n' % (chan, account))
	
	f.close
	trustedlock.release()
	
def chmode(irc, chan, nick, mode, args):
	set_unset = mode[0]
	mode = mode[1:]
	
	if isauthorized(irc, chan, nick):
		if args == ['']:
			irc.send('MODE %s %s %s' % (chan, set_unset+mode, nick))
		else:
			nicks = []
			for nick in args:
				nicks.append(nick)
				if len(nicks) == 4:
					irc.send('MODE %s %s %s' % (chan, set_unset+mode*4, ' '.join(nicks)))
					nicks = []
			if nicks:
				irc.send('MODE %s %s %s' % (chan, set_unset+mode*len(nicks), ' '.join(nicks)))

def istrusted(chan, account):
	trustedlock.acquire()
	if chan in trusted and account in trusted[chan]:
		trustedlock.release()
		return True
	else:
		trustedlock.release()
		return False

def initaccountcheck(nick):
	global accountcheck, accountcheckid, accountchecklock
	
	accountchecklock.acquire()
	id = accountcheckid
	accountcheck.append((id, nick, None))
	accountcheckid += 1
	accountchecklock.release()
	
	return id

# Warning: this does no locking, should only be used internally
# The index returned cannot be guaranteed valid if lock is released between call to getindexbyaccountcheckid and use!
def getindexbyaccountcheckid(id):
	global accountcheck
	
	for index in range(len(accountcheck)):
		ckid, cknick, ckaccount = accountcheck[index]
		if ckid == id:
			return index
	
	return None

def setaccountcheckvalue(id, value):
	global accountcheck, accountchecklock
	
	accountchecklock.acquire()
	index = getindexbyaccountcheckid(id)
	if index is not None:
		ckid, nick, ckvalue = accountcheck[index]
		accountcheck[index] = (id, nick, value)
	accountchecklock.release()

def getaccountcheckvalue(id):
	global accountcheck, accountchecklock
	
	accountchecklock.acquire()
	index = getindexbyaccountcheckid(id)
	if index is not None:
		 ckid, cknick, value = accountcheck[index]
	accountchecklock.release()
	
	return value

def removeaccountcheck(id):
	global accountcheck, accountchecklock
	
	accountchecklock.acquire()
	index = getindexbyaccountcheckid(id)
	if index is not None:
		del accountcheck[index]
	accountchecklock.release()

def getaccountcheckidbynick(nick):
	global accountcheck, accountchecklock
	
	accountchecklock.acquire()
	ids = [id for id, cknick, account in accountcheck if cknick == nick]
	accountchecklock.release()
	
	return ids

def getaccount(irc, nick):	
	id = initaccountcheck(nick)
	irc.send('WHOIS ' + nick)
	cron.queuejob(5, (lambda : setaccountcheckvalue(id, '')))
	
	account = None
	while account == None:
		account = getaccountcheckvalue(id)
		time.sleep(0.1)
	removeaccountcheck(id)
	
	if account == '': # '' Signifies failure
		return None
	else:
		return account

def isauthorized(irc, chan, nick):
	account = getaccount(irc, nick)
	if account:
		return istrusted(chan, account)
	else:
		irc.msg(nick, zwsp + 'Identify with NickServ')

class ArgsfmtError(Exception):
	def __init__(self, msg):
		self.msg = msg
	def __str__(self):
		return 'Error with argument format: ' + msg

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
	
def check_send_messages():
	msgs_changed = False
	with msgslock:
		if (line[1] == 'PRIVMSG' or line[1] == 'JOIN') and nick in msgs:
			for sender, origin, msg in msgs.pop(nick):
				irc.msg(nick, zwsp + '%s <%s> %s' % (origin, sender, msg))
			msgs_changed = True
	if msgs_changed:
		savemessages()

def should_ignore_message():
	zwsp = '\xe2\x80\x8b'
	
	if nick in blacklist:
		return True
	elif len(line) >= 4 and len(line[3]) >= len(zwsp)+1 and line[3][:len(zwsp)+1] == ':'+zwsp: # If line begins with ZWSP
		return True

	return False

def handle_message(*, prefix, message, nick, channel, irc):
	check_send_messages()
	if should_ignore_message():
		return

	if line[3][:2] != ': ':
		reply = chan
		
		cmdline = [line[3][1:]] + line[4:]
		while '' in cmdline:
			cmdline.remove('')
		
		# #chan: channel override prefix
		if matchcmd(cmdline, '#chan'):
			if matchcmd(cmdline, '#chan', 'channel {command}'):
				newchan, newcmdline = parsecmd(cmdline, 'channel {command}')
				newcmdline = newcmdline.split(' ')
				if isauthorized(irc, newchan, nick):
					chan = newchan
					cmdline = newcmdline
			else:
				irc.msg(chan, zwsp + 'Usage #chan channel command')
		
		if matchcmd(cmdline, '#echo'):
			text = parsecmd(cmdline, '{text}')
			irc.msg(reply, zwsp+text)
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
				else:
					if isauthorized(irc, chan, nick):
						irc.send('KICK %s %s :%s'%(chan, kicknick, kickreason))
			else:
				irc.msg(reply, zwsp + 'Usage #kick nick reason')
		elif matchcmd(cmdline, '#src'):
			irc.msg(reply, zwsp + 'https://github.com/JuEeHa/oonbotti2')
		elif matchcmd(cmdline, '#prefix') and chan == '#osdev-offtopic':
			irc.msg(reply, zwsp + 'gopher://ayu.smar.fi:7070/0/hash-prefix')
		elif matchcmd(cmdline, '#msg'):
			if matchcmd(cmdline, '#msg', 'nick {message}'):
				msgnick, message = parsecmd(cmdline, 'nick {message}')
				if chan == nick: # In a query:
					origin = "[query]"
				else: # In a channel
					origin = chan
				with msgslock:
					if msgnick not in msgs:
						msgs[msgnick] = []
					msgs[msgnick].append((nick, origin, message))
				savemessages()
			else:
				irc.msg(reply, zwsp + 'Usage: #msg nick message')
		elif matchcmd(cmdline, '#trusted?'):
			if matchcmd(cmdline, '#trusted?', '[nick]'):
				trustnick = parsecmd(cmdline, '[nick]')
				if trustnick == '':
					trustnick = nick
				account = getaccount(irc, trustnick)
				if account:
					if istrusted(chan, account):
						irc.msg(reply, zwsp + '%s is trusted' % trustnick)
					else:
						irc.msg(reply, zwsp + '%s is not trusted' % trustnick)
				else:
					irc.msg(reply, zwsp + 'Failed to get account for %s' % trustnick)
			else:
				irc.msg(reply, zwsp + 'Usage: #trusted? [nick]')
		elif matchcmd(cmdline, '#trust'):
			if matchcmd(cmdline, '#trust', 'nick'):
				trustnick = parsecmd(cmdline, 'nick')
				if isauthorized(irc, chan, nick):
					account = getaccount(irc, trustnick)
					if account:
						addtrusted(chan, account)
						savetrusted()
					else:
						irc.msg(reply, zwsp + 'Failed to get account for %s' % trustnick)
			else:
				irc.msg(reply, zwsp + 'Usage #trust nick')
		elif matchcmd(cmdline, '#untrust'):
			if matchcmd(cmdline, '#untrust', 'nick'):
				untrustnick = parsecmd(cmdline, 'nick')
				if isauthorized(irc, chan, nick):
					account = getaccount(irc, untrustnick)
					# If account can't be found (e.g. it has been deleted, use the parameter as-is
					if not account:
						if istrusted(chan, untrustnick):
							account = untrustnick
					if account:
						godslock.acquire()
						if chan not in gods or account not in gods[chan]:
							rmtrusted(chan, untrustnick)
						godslock.release()
						savetrusted()
					else:
						irc.msg(reply, zwsp + 'Failed to get account for %s' % untrustnick)
			else:
				irc.msg(reply, zwsp + 'Usage #untrust nick')
		elif matchcmd(cmdline, '#ls-trusted'):
			trustedlock.acquire()
			if chan in trusted:
				lines = []
				line = ''
				for account in trusted[chan]:
					if line == '':
						line = account
					elif len(line + ', ' + account) <= 255: # Playing it safe not to get truncated
						line += ', ' + account
					else:
						lines.append(line)
						line = account
				if line != '':
					lines.append(line)

				for line in lines:
					irc.msg(nick, zwsp + '%s: %s' % (chan, line))
			trustedlock.release()
		elif matchcmd(cmdline, '#invite'):
			irc.msg(chan, zwsp + '%s: #invite has been removed. Use manual invite' % nick)
		elif matchcmd(cmdline, '#help'):
			if matchcmd(cmdline, '#help', '[command]'):
				command = parsecmd(cmdline, '[command]')
				helptext = help(command)
				if helptext:
					irc.msg(reply, zwsp+helptext)
		elif matchcmd(cmdline, '#esoteric') and chan == '#esoteric':
			irc.msg(reply, zwsp + 'Nothing here')
		elif cmdline[0] in [irc.nick, irc.nick+',', irc.nick+':']:
			question = parsecmd(cmdline, '{question}')
			if len(question) < 2 or question[:2] != ':D': # Mandated by #osdev-offtopic law
				irc.msg(reply, zwsp + '%s: %s' % (nick, doctor.respond(question)))
		elif die_expr.match(cmdline[0]):
			die = cmdline[0][1:].split('d')
			times = int(die[0]) if die[0] else 1
			
			if '+' in die[1]:
				split = die[1].index('+')
				plus = int(die[1][split + 1:])
				die[1] = die[1][:split]
			elif '-' in die[1]:
				split = die[1].index('-')
				plus = -int(die[1][split + 1:])
				die[1] = die[1][:split]
			else:
				plus = 0
			die = '%' if die[1] == '%' else int(die[1])
			
			if die == '%':
				if times != 1:
					irc.msg(reply, zwsp + 'Not supported')
				else:
					irc.msg(reply, zwsp + '%s%s' % (random.randint(0,9), random.randint(0,9)))
			elif die < 2:
				irc.msg(reply, zwsp + 'This die is not available in your space-time region.')
			elif times < 1:
				irc.msg(reply, zwsp + 'What exactly do you want me to do?')
			elif times > 128:
				irc.msg(reply, zwsp + 'Sorry, I don\'t have that many. Can I borrow yours?')
			else:
				rolls = [random.randint(1, die) for i in xrange(times)]
				result = reduce((lambda x, y: x + y), rolls)
				
				if times > 1:
					text = '%s (%s)' % (str(result), ', '.join([str(i) for i in rolls]))
				else:
					text = str(result)
				
				if plus > 0:
					text = '%i (%s + %i)' % (result + plus, text, plus)
				elif plus < 0:
					text = '%i (%s - %i)' % (result + plus, text, -plus)
				
				irc.msg(reply, zwsp + text)

def handle_nonmessage(*, prefix, command, arguments, irc):
	check_send_messages()
	if should_ignore_message():
		return

	if line[1] == '330': # WHOIS: is logged in as
		whoisnick = line[3]
		account = line[4]
		for id in getaccountcheckidbynick(whoisnick):
			setaccountcheckvalue(id, account)
	elif line[1] == '318': # WHOIS: End of /WHOIS list.
		whoisnick = line[3]
		for id in getaccountcheckidbynick(whoisnick):
			if getaccountcheckvalue(id) == None:
				setaccountcheckvalue(id, '') # Mark as failed, '' is used because None is already reserved
	elif line[1] == 'INVITE' and line[2] == irc.nick and line[3][1:] in irc.chan.split(' '):
		if isauthorized(irc, line[3][1:], nick):
			irc.send('JOIN ' + line[3])
	elif line[1] == '482':
		irc.msg(line[3], zwsp + 'Not op')

# TODO: move everything out of here
def parse(arg):
	line, irc = arg

	global blacklist
	global msgs, msgslock
	global trusted, trustedlock, gods, godslock
	global doctor, die_expr

	line = line.split(' ')
	nick = line[0].split('!')[0][1:]
	chan = line[2] if line[2][0] == '#' else nick
	

def execcmd(cmdline):
	if cmdline[0] == '/q':
		cron.ctrl('QUIT')
	elif cmdline[0] == '/lt':
		loadtrusted()
	elif cmdline[0] == '/st':
		savetrusted()
	elif cmdline[0] == '/lg':
		loadgods()
	elif cmdline[0] == '/lm':
		loadmessages()
	elif cmdline[0] == '/sm':
		savemessages()

def usage(cmd, message = True):
	usage = {'#echo': 'text',
	         '#op': '[nick]',
	         '#deop': '[nick]',
	         '#voice': '[nick]',
	         '#devoice': '[nick]',
	         '#kick': 'nick [reason]',
	         '#src': '',
	         '#msg': 'nick message',
	         '#trusted?': '[nick]',
	         '#trust': 'nick',
	         '#untrust': 'nick',
	         '#ls-trusted': '',
	         '#chan': 'channel command',
	         '#help': '[command]'}
	
	if cmd in usage:
		if message:
			return 'Usage: %s %s' % (cmd, usage[cmd])
		else:
			return usage[cmd]
	else:
		return None

def help(cmd):
	helptext = {'#echo': '#echo text back',
	            '#op': 'give nick or yourself op rights in case you are trusted by oonbotti2 and identified with NickServ',
	            '#deop': 'remove your/nick\'s op rights',
	            '#voice': 'give nick or yourself voice in case you are trusted by oonbotti2 and identified with NickServ',
	            '#devoice': 'remove your or nick\'s voice in case you are trusted by oonbotti2 and identified with NickServ',
	            '#kick': 'kicks nick with specified reason',
	            '#src': 'paste a link to oonbotti2\'s git repo',
	            '#msg': 'send a message to nick',
	            '#trusted?': 'tell you if nick or yourself is trusted by oonbotti2',
	            '#trust': 'add nick to trusted list',
	            '#untrust': 'remove nick from trusted list',
	            '#ls-trusted': 'list nicks that are trusted. use only in a query',
	            '#chan': 'Runs the command as if it was sent on the specified channel. Requires user to be trusted',
	            '#help': 'give short info of command or list commands'}
	
	if cmd=='':
		return '#echo #op #deop #voice #devoice #kick #src #msg #trusted? #trust #untrust #ls-trusted #chan #help'
	elif cmd=='me':
		return 'I shall.'
	elif cmd in helptext:
		if helptext[cmd]:
			return '%s %s      %s' % (cmd, usage(cmd, False), helptext[cmd])
		else:
			return '%s %s' % (cmd, usage(cmd, False))
	else:
		return None
