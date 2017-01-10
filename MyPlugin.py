﻿import disco
from disco.bot import Bot, Plugin
from disco.types.user import Status, Game
from disco.types.message import MessageEmbed, MessageEmbedImage
from configparser import RawConfigParser
import sys
import requests
import ujson
import os
import random
import time

global riotApiKey, ownerid, commandsText, ownerCommandsText, autosave, copypastas, channelLogId, copyCatId

reload(sys)
sys.setdefaultencoding('utf8')

def getConfig():
    global riotApiKey, ownerid, autosave, channelLogId
    config = RawConfigParser()
    try:
        config.read('config.cfg')
        ownerid = config.get('plugin', 'ownerid').split(',')
        autosave = bool(int(config.get('plugin', 'autosave')))
        channelLogId = int(config.get('plugin', 'channelLogId'))
        riotApiKey = config.get('riotapi', 'apikey')
    except(RawConfigParser.NoSectionError, RawConfigParser.NoOptionError):
        quit('The "config.cfg" file is missing or corrupt!')
        
def createConfigFile():
    with open('config.cfg', 'w') as cfg:
        cfg.write('[plugin]\nownerid = 000000000000000,1111111111\nautosave = 1\nchannelLogId = 0000000000000000\n\n[riotapi]\napikey = **************')

def getCommandsText():
    if not os.path.isfile('commands.txt'):
        return 'commands.txt não encontrado.'
    with open('commands.txt', 'r') as file:
        commands = file.read()
    return commands

def getOwnerCommandsText():
    if not os.path.isfile('ownercommands.txt'):
        return 'ownercommands.txt não encontrado.'
    with open('ownercommands.txt', 'r') as file:
        commands = file.read()
    return commands
    
def getCopyPastas():
    if not os.path.isfile('copypastas.json'):
        print 'copypastas.json não encontrado.'
        return {}
    with open('copypastas.json', 'r') as file:
        copypastas = ujson.load(file)
    return copypastas
    
def saveCopyPastas(copypastas):
    with open('copypastas.json', 'w') as file:
        file.write(ujson.dumps(copypastas, indent=4, ensure_ascii=False))
        
if not os.path.isfile('config.cfg'):
    createConfigFile()

getConfig()
commandsText = getCommandsText()
ownerCommandsText = getOwnerCommandsText()
copypastas = getCopyPastas()
copyCatId = None   

class MyPlugin(Plugin):
    @Plugin.listen('Ready')
    def on_ready(self, event):
        self.client.api.channels_messages_create(channelLogId, 'I am ready!\nDisco-py: {}'.format(disco.VERSION))

    @Plugin.listen('GuildCreate')
    def on_guild_create(self, event):
        if event.created:
            self.client.api.channels_messages_create(channelLogId, 'Entrei no servidor: {}'.format(event.name))

    @Plugin.listen('GuildDelete')
    def on_guild_delete(self, event):
        if event.deleted:
            self.client.api.channels_messages_create(channelLogId, 'Saindo do servidor: {}'.format(event.id))

    @Plugin.listen('MessageCreate')
    def on_message_create(self, event):        
        if copyCatId == event.author.id:
            e = None
            if len(event.attachments):
                for k in event.attachments.keys():
                    e = MessageEmbed(title = event.attachments[k].filename, url = event.attachments[k].url)
                    e.image = MessageEmbedImage(url = event.attachments[k].url, proxy_url = event.attachments[k].proxy_url, width = event.attachments[k].width, height = event.attachments[k].height) if event.attachments[k].width else None
                    break
            self.client.api.channels_messages_create(event.channel_id, event.content, event.nonce, event.tts, None, e)            

    @Plugin.listen('TypingStart')
    def on_typing_start(self, event):
        if copyCatId == event.user_id:
            self.client.api.channels_typing(event.channel_id)
        
    @Plugin.command('updatePresence', '<status:str> [game:str...]')
    def on_updatepresence_command(self, event, status, game=None):
        if str(event.msg.author.id) in ownerid:
            if not Status[status]:
                status = 'ONLINE'
            self.client.update_presence(Game(name=game), Status[status])
            event.msg.reply('Atualizando status...')
        else:
            event.msg.reply('Você não pode usar esse comando.')
        
    @Plugin.command('setCopyCat', '[target:int]')
    def on_setcopycat_command(self, event, target=None):
        global copyCatId
        if str(event.msg.author.id) in ownerid:
            if target == 0:
                target = event.msg.author.id
            copyCatId = target
            event.msg.reply('{} setado como alvo.'.format(copyCatId))
        else:
            event.msg.reply('Você não pode usar esse comando.')
        
    @Plugin.command('comandos')
    def on_commandshelp_command(self, event):
        event.msg.reply(commandsText)
        if str(event.msg.author.id) in ownerid:
            event.msg.reply(ownerCommandsText)
        
    @Plugin.command('quit')
    def on_quit_command(self, event):
        if str(event.msg.author.id) in ownerid:
            event.msg.reply('Bye!')
            quit("Command triggered quit.")
        else:
            event.msg.reply('Você não pode usar esse comando.')
        
    @Plugin.command('reloadconfig')
    def on_reloadconfig_command(self, event):
        if str(event.msg.author.id) in ownerid:
            msg = event.msg.reply('Reloading config...')
            getConfig()
            msg.edit('Config reloaded!')
        else:
            event.msg.reply('Você não pode usar esse comando.')
        
    @Plugin.command('reloadcommandstext')
    def on_reloadcommandstext_command(self, event):
        if str(event.msg.author.id) in ownerid:
            msg = event.msg.reply('Reloading commands text...')
            commandsText = getCommandsText()
            ownerCommandsText = getOwnerCommandsText()
            msg.edit('Config reloaded!')
        else:
            event.msg.reply('Você não pode usar esse comando.')
        
    @Plugin.command('copypastaAdd', '<name:str> <copypasta:str...>')
    def on_copypastaAdd_command(self, event, name, copypasta):
        if name in copypastas:
            event.msg.reply('"' + name + '" já existente.\nUse "copypastaMod" para modificar um copypasta existente.')
        else:
            e = None
            if len(event.msg.attachments):
                for k in event.msg.attachments.keys():
                    e = MessageEmbed(title = event.msg.attachments[k].filename, url = event.msg.attachments[k].url)
                    e.image = MessageEmbedImage(url = event.msg.attachments[k].url, proxy_url = event.msg.attachments[k].proxy_url, width = event.msg.attachments[k].width, height = event.msg.attachments[k].height) if event.msg.attachments[k].width else None
                    break
            copypastas[name] = [copypasta, e]
            event.msg.reply('"' + name + '" adicionado.')
            if autosave:
                saveCopyPastas(copypastas)
        
    @Plugin.command('copypastaMod', '<name:str> <copypasta:str...>')
    def on_copypastaMod_command(self, event, name, copypasta):
        if not name in copypastas:
            event.msg.reply('"' + name + '" inexistente.\nUse "copypastaAdd" para adicionar um novo copypasta.')
        else:
            e = None
            if len(event.msg.attachments):
                for k in event.msg.attachments.keys():
                    e = MessageEmbed(title = event.msg.attachments[k].filename, url = event.msg.attachments[k].url)
                    e.image = MessageEmbedImage(url = event.msg.attachments[k].url, proxy_url = event.msg.attachments[k].proxy_url, width = event.msg.attachments[k].width, height = event.msg.attachments[k].height) if event.msg.attachments[k].width else None
                    break
            copypastas[name] = [copypasta, e]
            event.msg.reply('"' + name + '" modificado.')
            if autosave:
                saveCopyPastas(copypastas)
        
    @Plugin.command('copypastaDel', '<name:str>')
    def on_copypastaDel_command(self, event, name):
        if not name in copypastas:
            event.msg.reply('"' + name + '" inexistente.')
        else:
            del copypastas[name]
            event.msg.reply('"' + name + '" apagado.')
            if autosave:
                saveCopyPastas(copypastas)
        
    @Plugin.command('copypastaRename', '<oldname:str> <newname:str>')
    def on_copypastaRename_command(self, event, oldname, newname):
        if not oldname in copypastas:
            event.msg.reply('"' + oldname + '" inexistente.')
        else:
            copypastas[newname] = copypastas[oldname]
            del copypastas[oldname]
            event.msg.reply('"' + oldname + '" renomeado para "'+ newname + '".')
            if autosave:
                saveCopyPastas(copypastas)

    @Plugin.command('copypasta', '[copypasta:str]')
    def on_copypasta_command(self, event, copypasta=None):
        if copypasta:
            if copypasta in copypastas:
                event.msg.reply(copypastas[copypasta][0], event.msg.nonce, event.msg.tts, None, copypastas[copypasta][1])
            else:
                event.msg.reply('"' + copypasta + '" não encontrado.')
        else:
            keys = copypastas.keys()
            if len(keys):
                k = keys[random.randrange(len(keys))]
                event.msg.reply(copypastas[k][0], event.msg.nonce, event.msg.tts, None, copypastas[k][1])
            else:
                event.msg.reply("Não há copypastas salvos.")

    @Plugin.command('copypastaSpam', '<quantity:int>')
    def on_copypastaSpam_command(self, event, quantity):
        keys = copypastas.keys()
        if len(keys):
            for i in range(quantity):
                k = keys[random.randrange(len(keys))]
                event.msg.reply(copypastas[k][0], event.msg.nonce, event.msg.tts, None, copypastas[k][1])
        else:
            event.msg.reply("Não há copypastas salvos.")

    @Plugin.command('copypastaList')
    def on_copypastaList_command(self, event):
        keys = copypastas.keys()
        if len(keys):
            res = '```\n'
            for k in keys:
                res += k+'\n'
            res += '```'
            event.msg.reply(res)
        else:
            event.msg.reply("Não há copypastas salvos.")

    @Plugin.command('copypastaAll')
    def on_copypastaAll_command(self, event):
        keys = copypastas.keys()
        if len(keys):
            for k in keys:
                event.msg.reply(copypastas[k][0], event.msg.nonce, event.msg.tts, None, copypasta[k][1])
        else:
            event.msg.reply("Não há copypastas salvos.")
        
    @Plugin.command('name','<name:str...>')
    def on_name_command(self, event, name):
        self.client.api.channels_typing(event.msg.channel_id)
        result = requests.get('https://br.api.pvp.net/api/lol/br/v1.4/summoner/by-name/' + name + '?api_key=' + riotApiKey)
        event.msg.reply('```\n'+ujson.dumps(ujson.loads(result.text), indent=4, ensure_ascii=False)+'\n```')

    @Plugin.command('spam', '<count:int> <content:str...>')
    def on_spam_command(self, event, count, content):
        if str(event.msg.author.id) in ownerid:
            for i in range(count):
                self.client.api.channels_typing(event.msg.channel_id)
                event.msg.reply(content)
        else:
            event.msg.reply('Você não pode usar esse comando.')

    @Plugin.command('spamsf', '<count:int> <timesf:int> <content:str...>')
    def on_spamsf_command(self, event, count, timesf, content):
        if str(event.msg.author.id) in ownerid:
            msgs = []
            for i in range(count):
                self.client.api.channels_typing(event.msg.channel_id)
                msgs.append(event.msg.reply(content))
            time.sleep(timesf)
            for m in msgs:
                m.delete()
        else:
            event.msg.reply('Você não pode usar esse comando.')

    @Plugin.command('spamc', '<cid:int> <count:int> <content:str...>')
    def on_spamc_command(self, event, cid, count, content):
        if str(event.msg.author.id) in ownerid:
            for i in range(count):
                self.client.api.channels_typing(cid)
                self.client.api.channels_messages_create(cid, content)
        else:
            event.msg.reply('Você não pode usar esse comando.')

    @Plugin.command('spamcsf', '<cid:int> <count:int> <timesf:int> <content:str...>')
    def on_spamcsf_command(self, event, cid, count, timesf, content):
        if str(event.msg.author.id) in ownerid:
            msgs = []
            for i in range(count):
                self.client.api.channels_typing(cid)
                msgs.append(self.client.api.channels_messages_create(cid, content))
            time.sleep(timesf)
            for m in msgs:
                m.delete()
        else:
            event.msg.reply('Você não pode usar esse comando.')

    @Plugin.command('saychannel', '<cid:int> <content:str...>')
    def on_saychannel_command(self, event, cid, content):
        self.client.api.channels_messages_create(cid, content)

    @Plugin.command('faketype', '<cid:int>')
    def on_faketype_command(self, event, cid):
        self.client.api.channels_typing(cid)
    
    @Plugin.command('info', '<query:str...>')
    def on_info(self, event, query):
        users = list(self.state.users.select({'username': query}, {'id': query}))

        if not users:
            event.msg.reply("Couldn't find user for your query: `{}`".format(query))
        elif len(users) > 1:
            event.msg.reply('I found too many users ({}) for your query: `{}`'.format(len(users), query))
        else:
            user = users[0]
            parts = []
            parts.append('ID: {}'.format(user.id))
            parts.append('Username: {}'.format(user.username))
            parts.append('Discriminator: {}'.format(user.discriminator))
            if user.verified:
                parts.append('Verified: {}'.format(user.verified))
            if user.bot:
                parts.append('Bot: {}'.format(user.bot))

            if event.channel.guild:
                member = event.channel.guild.get_member(user)
                parts.append('Nickname: {}'.format(member.nick))
                parts.append('Joined At: {}'.format(member.joined_at))
                
            avatar_url = ''
            if user.avatar:
                avatar_url = '\nhttps://discordapp.com/api/users/{}/avatars/{}.jpg'.format(user.id, user.avatar)
            
            event.msg.reply(('```\n{}\n```'.format(
                '\n'.join(parts))
            )+avatar_url)
