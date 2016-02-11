# vim: ts=4 et sw=4 sts=4
# -*- coding: utf-8 -*-
import random
import asyncio
import re
import itertools
import irc3
from irc3.plugins.command import command
import time
import threading

from taunts import USE_FORBIDDEN, TALKING_REACTION, TAUNTS

CLANMEMBER = {}
IGNOREUSERS = ['NickServ', 'ChanServ', 'OperServ']
ALLTAUNTS = []
BEQUIETCHANNELS = ['#aeolus']
LETMEGOOGLE = "http://lmgtfy.com/?q="
MODERATEDCHANNELS = []


@irc3.extend
def action(bot, *args):
    bot.privmsg(args[0], '\x01ACTION ' + args[1] + '\x01')

@irc3.plugin
class Plugin(object):

    def __init__(self, bot):
        self.bot = bot
        self.timers = {}
        self._rage = {}

        global ALLTAUNTS, IGNOREUSERS, MODERATEDCHANNELS
        ALLTAUNTS.extend(USE_FORBIDDEN)
        ALLTAUNTS.extend(TAUNTS)
        ALLTAUNTS.extend(TALKING_REACTION)
        IGNOREUSERS.extend([self.bot.config['nick']])
        for channel in self.bot.config['moderatedChannels']:
            MODERATEDCHANNELS.append('#' + channel)

        #self.slackThread = slack.slackThread(self.bot.config['slack_api_key'])
        #self.slackThread.daemon = True
        #self.slackThread.start()


    @classmethod
    def reload(cls, old):
        return cls(old.bot)


    def after_reload(self):
        pass


    @irc3.event(irc3.rfc.CONNECTED)
    def nickserv_auth(self, *args, **kwargs):
        self.bot.privmsg('nickserv', 'identify %s' % self.bot.config['nickserv_password'])
        if 'clan' in self.bot.db:
            if 'names' in self.bot.db['clan']:
                global CLANMEMBER
                CLANMEMBER = self.bot.db['clan'].get('names', {}) #doing this here to init CLANMEMBER after the bot got its db


    @irc3.event(irc3.rfc.JOIN)
    def on_join(self, channel, mask):
        if channel == '#aeolus':
            for channel in self.bot.db['chatlists']:
                if mask.nick in self.bot.db['chatlists'].get(channel, {}).keys():
                    self.move_user(channel, mask.nick)


    @irc3.event(irc3.rfc.PRIVMSG)
    @asyncio.coroutine
    def on_privmsg(self, *args, **kwargs):
        msg, channel, sender = kwargs['data'], kwargs['target'], kwargs['mask']
        #print(sender + ": " + msg)
        if sender.nick in IGNOREUSERS:
            return
        if not channel in MODERATEDCHANNELS:
            return
        if self.__handledNonMember(sender.nick, channel=channel, tauntTable=TALKING_REACTION, kick=False):
            return


    @command
    def hug(self, mask, target, args):
        """Hug someone

            %%hug
            %%hug <someone>
        """
        if self.__handledNonMember(mask.nick, target, ALLTAUNTS):
            return
        someone = args['<someone>']
        if someone == None:
            someone = mask.nick
        elif someone == self.bot.config['nick']:
            return
        self.bot.action(target, "hugs " + someone)


    @command(permission='admin')
    def join(self, mask, target, args):
        """Join the given channel

            %%join <channel>
        """
        self.bot.join(args['<channel>'])


    @command(permission='admin')
    def leave(self, mask, target, args):
        """Leave the given channel

            %%leave
            %%leave <channel>
        """
        channel = args['<channel>']
        if channel is None:
            channel = target
        self.bot.part(channel)


    @command(permission='admin', public=False)
    def puppet(self, mask, target, args):
        """Puppet

            %%puppet <target> WORDS ...
        """
        t = args.get('<target>')
        m = " ".join(args.get('WORDS'))
        self.bot.privmsg(t, m)


    @command(permission='admin', public=False)
    def clan(self, mask, target, args):
        """Adds/removes a user to/from the clanlist 

            %%clan get
            %%clan add <name>
            %%clan del <name>
        """
        global CLANMEMBER
        if 'clan' not in self.bot.db:
            self.bot.db['clan'] = {'names': {}}
        add, delete, get, name = args.get('add'), args.get('del'), args.get('get'), args.get('<name>')
        if add:
            try:
                allUser = self.bot.db['clan'].get('names', {})
                allUser[name] = True
                self.bot.db.set('clan', names=allUser)
                CLANMEMBER = allUser
                return 'Added "{name}" to clan members'.format(**{
                        "name": name,
                    })
            except:
                return "Failed adding the user. What did you do?!"
        elif delete:
            allUser = self.bot.db['clan'].get('names', {})
            if allUser.get(name):
                del self.bot.db['clan']['names'][name]
                CLANMEMBER = self.bot.db['clan'].get('names', {})
                return 'Removed "{name}" from clan members'.format(**{
                        "name": name,
                    })
            else:
                return 'Name not found in the list.'
        elif get:
            self.bot.privmsg(mask.nick, str(len(CLANMEMBER)) + " members listed:")
            self.bot.privmsg(mask.nick, 'names: ' + ', '.join(CLANMEMBER.keys()))


    @command
    def google(self, mask, target, args):
        """google

            %%google WORDS ...
        """
        link = LETMEGOOGLE + "+".join(args.get('WORDS'))
        self.bot.privmsg(target, link)


    def __isClanMember(self, nick):
        return nick in CLANMEMBER


    def __handledNonMember(self, nick, channel=None, tauntTable=TALKING_REACTION, kick=True):
        if self.__isClanMember(nick):
            return False
        if not channel:
            channel = nick
        elif kick == True:
            self.__kickFromChannel(nick, channel)
        self.__taunt(nick, channel=channel, tauntTable=tauntTable)
        return True


    def __kickFromChannel(self, nick, channel):
        self.bot.privmsg("ChanServ", "kick {channel} {nick}".format(**{
                'channel': channel,
                'nick': nick,
            }))


    @command
    def kick(self, mask, target, args):
        """Kick someone from channel

            %%kick <person>
        """
        if self.__handledNonMember(mask.nick, target, USE_FORBIDDEN):
            return
        p = args.get('<person>')
        if self.__isClanMember(p):
            return
        if p == self.bot.config['nick']:
            p = mask.nick
        self.__kickFromChannel(p, target)


    @command
    def taunt(self, mask, target, args):
        """Send a taunt

            %%taunt <person>
        """
        if self.__handledNonMember(mask.nick, target, USE_FORBIDDEN):
            return
        p = args.get('<person>')
        if p == self.bot.config['nick']:
            p = mask.nick
        self.__taunt(nick=p, channel=target, tauntTable=TAUNTS)


    def __taunt(self, nick, channel=None, tauntTable=TAUNTS):
        if channel is None:
            channel = "#qai_channel"
        if channel in BEQUIETCHANNELS:
            return
        if tauntTable is None:
            tauntTable = ALLTAUNTS
        self.bot.privmsg(channel, random.choice(tauntTable).format(**{
                'name' : nick
            }))