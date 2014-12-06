import eliza
import threading
import random
import re

concmd=['/q','/lt','/st','/lg']

blacklist=['bslsk05']

doctor=eliza.eliza()
trusted=[]
trustedlock=threading.Lock()
gods=[]
godslock=threading.Lock()
msgs={}
msglock=threading.Lock()
authcmds={}
authcmdlock=threading.Lock()
authfuncs={}
authfunclock=threading.Lock()

die_expr=re.compile("#[0-9]*d([0-9]+|%)")

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

def addauthcmd(nick,cmd):
	authcmdlock.acquire()
	trustedlock.acquire()
	if nick in trusted:
		if nick not in authcmds:
			authcmds[nick]=[]
		authcmds[nick].append(cmd)
	trustedlock.release()
	authcmdlock.release()

def addauthfunc(nick,f):
	authfunclock.acquire()
	trustedlock.acquire()
	if nick in trusted:
		if nick not in authfuncs:
			authfuncs[nick]=[]
		authfuncs[nick].append(f)
	trustedlock.release()
	authfunclock.release()

def chmode(irc,chan,nick,mode,args):
	if len(args)==0:
		addauthcmd(nick,'MODE %s %s %s'%(chan,mode,nick))
	else:
		for name in args:
			addauthcmd(nick,'MODE %s %s %s'%(chan,mode,name))
	irc.send('PRIVMSG NickServ :ACC '+nick)

def parse((line,irc)):
	line=line.split(' ')
	nick=line[0].split('!')[0][1:]
	chan=line[2] if line[2][0]=='#' else nick 
	
	if nick in blacklist:
		return
	
	if line[1]=='PRIVMSG':
		if line[3]==':#echo':
			irc.send('PRIVMSG %s :\xe2\x80\x8b%s'%(chan,' '.join(line[4:])))
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
				if line[4].lower()=='oonbotti2':
					irc.send('KICK %s %s :Fuck you'%(chan,nick))
				elif random.randint(0,9)==0 and len(line)==5:
					irc.send('KICK %s %s :Bam'%(chan,nick))
				else:
					addauthcmd(nick,'KICK %s %s :%s'%(chan,line[4],' '.join(line[5:])))
					irc.send('PRIVMSG NickServ :ACC '+nick)
			else:
				irc.send('PRIVMSG %s :Usage #kick nick reason'%chan)
		elif line[3]==':#src':
			irc.send('PRIVMSG %s :https://github.com/JuEeHa/oonbotti2'%chan)
		elif line[3]==':#prefix' and chan=='#osdev-offtopic':
			irc.send('PRIVMSG %s :gopher://smar.fi:7070/0/hash-prefix'%chan)
		elif line[3]==':#msg':
			if len(line)>5:
				msglock.acquire()
				if line[4] not in msgs:
					msgs[line[4]]=[]
				msgs[line[4]].append((nick,' '.join(line[5:])))
				msglock.release()
			else:
				irc.send('PRIVMSG %s :Usage: #msg nick message'%chan)
		elif line[3]==':#trusted?':
			addauthcmd(nick,'PRIVMSG %s :%s: You are trusted'%(chan,nick))
			irc.send('PRIVMSG NickServ :ACC '+nick)
		elif line[3]==':#trust':
			if len(line)==5:
				addauthfunc(nick,(lambda :addtrusted(line[4])))
				irc.send('PRIVMSG NickServ :ACC '+nick)
			else:
				irc.send('PRIVMSG %s :Usage #trust nick'%chan)
		elif line[3]==':#untrust':
			if len(line)==5:
				godslock.acquire()
				if line[4] not in gods:
					addauthfunc(nick,(lambda :rmtrusted(line[4])))
					irc.send('PRIVMSG NickServ :ACC '+nick)
				godslock.release()
			else:
				irc.send('PRIVMSG %s :Usage #trust nick'%chan)
		elif line[3]==':#ls-trusted':
			trustedlock.acquire()
			irc.send('PRIVMSG %s :%s'%(nick,', '.join(trusted)))
			trustedlock.release()
		elif line[3]==':#invite':
			if len(line)==5:
				addauthcmd(nick, 'INVITE %s %s'%(line[4], chan))
				irc.send('PRIVMSG NickServ :ACC '+nick)
			else:
				irc.send('PRIVMSG %s :Usage #invite nick'%chan)
		elif line[3]==':#help':
			helptext=help(' '.join(line[4:]))
			if helptext:
				irc.send('PRIVMSG %s : %s'%(chan,helptext))
		elif line[3]==':#esoteric' and chan=='#esoteric':
			irc.send('PRIVMSG %s :Nothing here'%chan)
		elif line[3][1:] in ('oonbotti:', 'oonbotti', 'oonbotti,', 'oonbotti2', 'oonbotti2:', 'oonbotti2,'):
			irc.send('PRIVMSG %s :%s: %s'%(chan,nick,doctor.respond(' '.join(line[4:]))))
		elif die_expr.match(line[3][1:]):
			die=line[3][2:].split('d')
			times=int(die[0]) if die[0] else 1
			die='%' if die[1]=='%' else int(die[1])
			if die=='%':
				if times!=1:
					irc.send('PRIVMSG %s :Not supported'%chan)
				else:
					irc.send('PRIVMSG %s :%s%s'%(chan, random.randint(0,9), random.randint(0,9)))
			elif die<2:
				irc.send('PRIVMSG %s :This die is not available in your space-time region.'%chan)
			elif times<1:
				irc.send('PRIVMSG %s :What exactly do you want me to do?'%chan)
			elif times>128:
				irc.send('PRIVMSG %s :Sorry, I don\'t have that many. Can I borrow yours?'%chan)
			else:
				rolls=[random.randint(1, die) for i in xrange(times)]
				result=reduce((lambda x,y:x+y), rolls)
				if times>1:
					irc.send('PRIVMSG %s :%s (%s)'%(chan, str(result), ', '.join([str(i) for i in rolls])))
				else:
					irc.send('PRIVMSG %s :%s'%(chan, str(result)))
	elif line[1]=='NOTICE' and line[0].split('!')[0]==':NickServ' and  line[4]=='ACC':
		authfunclock.acquire()
		authcmdlock.acquire()
		if line[5]=='3':
			trustedlock.acquire()
			if line[3][1:] in trusted:
				trustedlock.release()
				if line[3][1:] in authcmds:
					for i in authcmds.pop(line[3][1:]):
						irc.send(i)
				if line[3][1:] in authfuncs:
					for i in authfuncs.pop(line[3][1:]):
						i()
			else:
				trustedlock.release()
		else:
			if line[3][1:] in authcmds:
				authcmds.pop(line[3][1:])
			if line[3][1:] in authfuncs:
				authfuncs.pop(line[3][1:])
			if line[5]=='0':
				irc.send('PRIVMSG %s :Register account with NickServ'%line[3][1:])
			elif line[5]=='1':
				irc.send('PRIVMSG %s :Identify with NickServ'%line[3][1:])
			else:
				irc.send('PRIVMSG %s :WTF, NickServ returned %s'%(line[3][1:],line[5]))
		authcmdlock.release()
		authfunclock.release()
	elif line[1]=='482':
		irc.send('PRIVMSG %s :Not op'%line[3])
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
			irc.send('PRIVMSG %s :<%s> %s'%(nick,sender,msg))
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
		return '#trusted?      tell you if you are trusted by oonbotti'
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
