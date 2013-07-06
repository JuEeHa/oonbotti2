import eliza

doctor=eliza.eliza()
opnicks=['nortti','nortti_','shikhin','shikhin_','shikhin__','sortiecat','martinFTW','graphitemaster','XgF','sprocklem']
opchans=['#osdev-offtopic']
oprights={}
for i in opnicks:
	oprights[i]=opchans
autoops={}
msgs={}

def parse((line,irc)):
	line=line.split(' ')
	nick=line[0].split('!')[0][1:]
	chan=line[2] if line[2][0]=='#' else nick 
	if line[1]=='PRIVMSG':
		if line[3]==':#echo':
			irc.send('PRIVMSG %s :%s'%(chan,' '.join(line[4:])))
		elif line[3]==':#op':
			if len(line)==4:
				irc.send('PRIVMSG NickServ :ACC '+nick)
			else:
				for name in line[4:]:
					irc.send('PRIVMSG NickServ :ACC '+name)
		elif line[3]==':#src':
			irc.send('PRIVMSG %s :https://github.com/JuEeHa/oonbotti2'%chan)
		elif line[3]==':#msg':
			if len(line)>5:
				if line[4] not in msgs:
					msgs[line[4]]=[]
				msgs[line[4]].append((nick,' '.join(line[5:])))
			else:
				irc.send('PRIVMSG %s :Usage: #msg nick message'%chan)
		elif line[3]==':#readmsg':
			if nick in msgs:
				for sender,msg in msgs.pop(nick):
					irc.send('PRIVMSG %s :<%s> %s'%(chan,sender,msg))
			else:
				irc.send('PRIVMSG %s :You have no unread messages'%chan)
		elif line[3]==':#help':
			irc.send('PRIVMSG %s :#echo #op #src #msg #readmsg #help'%chan)
		elif line[3][1:] in ('oonbotti:', 'oonbotti', 'oonbotti,', 'oonbotti2', 'oonbotti2:', 'oonbotti2,'):
			irc.send('PRIVMSG %s :%s: %s'%(chan,nick,doctor.respond(' '.join(line[4:]))))
	elif line[1]=='NOTICE' and line[0].split('!')[0]==':NickServ' and  line[4]=='ACC':
		if line[3][1:] in oprights and int(line[5])==3:
			for opchan in oprights[line[3][1:]]:
				irc.send('MODE %s +o %s'%(opchan,line[3][1:]))
	elif line[1]=='JOIN' and nick in autoops and chan in autoops[nick]:
		irc.send('PRIVMSG NickServ :ACC '+nick)
	
	if (line[1]=='PRIVMSG' or line[1]=='JOIN') and nick in msgs:
		irc.send('PRIVMSG %s :You have unread messages, read them with #readmsg'%chan)
