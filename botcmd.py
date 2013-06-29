import eliza

doctor=eliza.eliza()
opnicks=['nortti','nortti_','shikhin','shikhin`','`shikhin','^[]','sortiecat','martinFTW','graphitemaster','XgF']
opchans=['#osdev-offtopic']
oprights={}
for i in opnicks:
	oprights[i]=opchans

def parse((line,irc)):
	line=line.split(' ')
	if line[1]=='PRIVMSG':
		if line[3]==':#echo':
			irc.send('PRIVMSG %s :%s'%(line[2],' '.join(line[4:])))
		elif line[3]==':#op':
			irc.send('PRIVMSG NickServ :ACC '+line[0].split('!')[0][1:])
		elif line[3]==':#src':
			irc.send('PRIVMSG %s :https://github.com/JuEeHa/oonbotti2'%line[2])
		elif line[3][1:] in ('oonbotti:', 'oonbotti', 'oonbotti,', 'oonbotti2', 'oonbotti2:', 'oonbotti2,'):
			irc.send('PRIVMSG %s :%s'%(line[2],doctor.respond(' '.join(line[4:]))))
	elif line[1]=='NOTICE' and line[0].split('!')[0]==':NickServ' and  line[4]=='ACC':
		if line[3][1:] in oprights and int(line[5])==3:
			for chan in oprights[line[3][1:]]:
				irc.send('MODE %s +o %s'%(chan,line[3][1:]))
