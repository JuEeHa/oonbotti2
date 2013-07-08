import eliza
import threading

concmd=['/q','/debg']

doctor=eliza.eliza()
trusted=['nortti','nortti_','shikhin','shikhin_','shikhin__','sortiecat','martinFTW','graphitemaster','XgF','sprocklem']
opchans=['#osdev-offtopic']
oprights={}
for i in trusted:
	oprights[i]=opchans
autoops={}
msgs={}
msglock=threading.Lock()
authcmds={}
authcmdlock=threading.Lock()

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

def addauthcmd(nick,cmd):
	authcmdlock.acquire()
	if nick not in trusted:
		return
	if nick not in authcmds:
		authcmds[nick]=[]
	authcmds[nick].append(cmd)
	authcmdlock.release()
def parse((line,irc)):
	line=line.split(' ')
	nick=line[0].split('!')[0][1:]
	chan=line[2] if line[2][0]=='#' else nick 
	if line[1]=='PRIVMSG':
		if line[3]==':#echo':
			irc.send('PRIVMSG %s :%s'%(chan,' '.join(line[4:])))
		elif line[3]==':#op':
			if len(line)==4:
				addauthcmd(nick,'MODE %s +o %s'%(chan,nick))
				irc.send('PRIVMSG NickServ :ACC '+nick)
			else:
				for name in line[4:]:
					addauthcmd(nick,'MODE %s +o %s'%(chan,name))
				irc.send('PRIVMSG NickServ :ACC '+nick)
		elif line[3]==':#deop':
			if len(line)==4:
				addauthcmd(nick,'MODE %s -o %s'%(chan,nick))
				irc.send('PRIVMSG NickServ :ACC '+nick)
			else:
				for name in line[4:]:
					addauthcmd(nick,'MODE %s -o %s'%(chan,name))
				irc.send('PRIVMSG NickServ :ACC '+nick)
		elif line[3]==':#kick':
			if len(line)>4:
				addauthcmd(nick,'KICK %s %s :%s'%(chan,line[4],' '.join(line[5:])))
				irc.send('PRIVMSG NickServ :ACC '+nick)
			else:
				irc.send('PRIVMSG %s :Usage #kick nick reason'%chan)
		elif line[3]==':#src':
			irc.send('PRIVMSG %s :https://github.com/JuEeHa/oonbotti2'%chan)
		elif line[3]==':#msg':
			if len(line)>5:
				msglock.acquire()
				if line[4] not in msgs:
					msgs[line[4]]=[]
				msgs[line[4]].append((nick,' '.join(line[5:])))
				msglock.release()
			else:
				irc.send('PRIVMSG %s :Usage: #msg nick message'%chan)
		elif line[3]==':#readmsg':
			msglock.acquire()
			if nick in msgs:
				for sender,msg in msgs.pop(nick):
					irc.send('PRIVMSG %s :<%s> %s'%(chan,sender,msg))
			else:
				irc.send('PRIVMSG %s :You have no unread messages'%chan)
			msglock.release()
		elif line[3]==':#help':
			irc.send('PRIVMSG %s :%s'%(chan,help(' '.join(line[4:]))))
		elif line[3][1:] in ('oonbotti:', 'oonbotti', 'oonbotti,', 'oonbotti2', 'oonbotti2:', 'oonbotti2,'):
			irc.send('PRIVMSG %s :%s: %s'%(chan,nick,doctor.respond(' '.join(line[4:]))))
	elif line[1]=='NOTICE' and line[0].split('!')[0]==':NickServ' and  line[4]=='ACC':
		authcmdlock.acquire()
		if line[3][1:] in trusted and line[3][1:] in authcmds and line[5]=='3':
			for i in authcmds.pop(line[3][1:]):
				irc.send(i)
		else:
			authcmds.pop(line[3][1:])
		authcmdlock.release()
	elif line[1]=='JOIN' and nick in autoops and chan in autoops[nick]:
		irc.send('PRIVMSG NickServ :ACC '+nick)
	elif line[1]=='482':
		irc.send('PRIVMSG %s :Not op'%line[3])
	
	msglock.acquire()
	if (line[1]=='PRIVMSG' or line[1]=='JOIN') and nick in msgs:
		irc.send('PRIVMSG %s :%s: You have unread messages, read them with #readmsg'%(chan,nick))
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

def help(cmd):
	if cmd=='':
		return '#echo #op #deop #kick #src #msg #readmsg #help'
	elif cmd=='#echo':
		return '#echo text      echo text back'
	elif cmd=='#op':
		return '#op [nick]      give nick or yourself op rights in case nick/you is/are trusted by oonbotti2 and identified with NickServ'
	elif cmd=='#deop':
		return '#deop [nick]      remove your/nick\'s op rights (added due to irrational demand by shikhin and sortiecat, nick support added for same reason)'
	elif cmd=='#kick':
		return '#kick nick reason      kicks nick with specified reason'
	elif cmd=='#src':
		return '#src      paste a link to oonbotti2\'s git repo'
	elif cmd=='#msg':
		return '#msg nick message      send a message to nick. messages can be read with #readmsg'
	elif cmd=='#readmsg':
		return '#readmsg      read messages you have received'
	elif cmd=='#help':
		return '#help [command]      give short info of command or list commands'
	else:
		return 'Not found'
