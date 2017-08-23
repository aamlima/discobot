import gevent
from disco.bot import Plugin
from disco.bot.command import CommandError
from disco.voice.client import VoiceException
from disco.voice.packets import VoiceOPCode
from disco.voice.playable import UnbufferedOpusEncoderPlayable, YoutubeDLInput
from disco.voice.player import Player
from disco.voice.queue import PlayableQueue
from flask import abort, flash, jsonify, request, redirect, url_for

from Utils import remove_angular_brackets


class CircularQueue(PlayableQueue):
    def __init__(self):
        super(CircularQueue, self).__init__()
        self._data.append(0)

    def get(self):
        # pylint: disable=W0212
        item = self._get()
        new_item = YoutubeDLInput(item.source._url, item.source._ie_info)
        new_item._info = item.info
        self.append(new_item.pipe(UnbufferedOpusEncoderPlayable))
        return item

    def remove(self, index):
        if len(self._data) > index:
            return self._data.pop(index)
        return None

    def prepend(self, item):
        self._data.insert(0, item)

        if self._event:
            self._event.set()
            self._event = None


class MusicPlayer(Player):
    def __init__(self, client, guild_member, guild):
        super(MusicPlayer, self).__init__(client, CircularQueue())
        self.queue.clear()
        self.guild_member = guild_member
        self.guild = guild
        self.nick = guild_member.nick
        self.speaking = {}
        self.__autopause = self.autopause = False
        self.__autovolume = self.autovolume = True
        self.__base_volume = self.volume = 0.1
        self.__ducking_volume = self.ducking_volume = 0.1
        self.__clear = False
        self.anyonespeaking = False
        self.items = PlayableQueue()

        gevent.spawn(self.add_items)

        self.events.on(self.Events.START_PLAY, self.on_start_play)
        self.events.on(self.Events.EMPTY_QUEUE,
                       self.on_disconnect_or_empty_queue)
        self.events.on(self.Events.DISCONNECT,
                       self.on_disconnect_or_empty_queue)
        self.client.packets.on(VoiceOPCode.SPEAKING, self.on_speaking)

    def on_start_play(self, item):
        nickname = '🎵 ' + (item.info.get('alt_title')
                           or item.info.get('title', ''))
        if len(nickname) > 32:
            nickname = nickname[:29] + '...'
        self.guild_member.set_nickname(nickname)
        self.update_volume()

    def on_disconnect_or_empty_queue(self):
        self.guild_member.set_nickname(self.nick)

    def on_speaking(self, data):
        if (not self.autopause) and (not self.autovolume):
            return

        if not self.guild.get_member(data['user_id']).get_voice_state().channel is self.client.channel:
            return

        self.speaking[data['user_id']] = data['speaking']

        self.anyonespeaking = any(self.speaking.values())

        if self.autovolume:
            self.update_volume()
        elif self.autopause:
            if self.anyonespeaking:
                self.pause()
            else:
                self.resume()

    @property
    def autopause(self):
        return self.__autopause

    @autopause.setter
    def autopause(self, value):
        self.__autopause = value
        if not value:
            self.resume()
        else:
            self.autovolume = False

    @property
    def autovolume(self):
        return self.__autovolume

    @autovolume.setter
    def autovolume(self, value):
        self.__autovolume = value
        if value:
            self.autopause = False
        else:
            self.update_volume()

    @property
    def volume(self):
        return self.__base_volume

    @volume.setter
    def volume(self, value):
        self.__base_volume = value
        self.update_volume()

    @property
    def ducking_volume(self):
        return self.__ducking_volume

    @ducking_volume.setter
    def ducking_volume(self, value):
        self.__ducking_volume = value
        self.update_volume()

    def update_volume(self):
        if isinstance(self.now_playing, UnbufferedOpusEncoderPlayable):
            if self.autovolume and self.anyonespeaking:
                self.now_playing.volume = self.__base_volume * self.ducking_volume
            else:
                self.now_playing.volume = self.__base_volume

    def add_items(self):
        while True:
            self.queue.append(self.items.get().pipe(
                UnbufferedOpusEncoderPlayable))
            if self.__clear:
                self.__clear = False
                self.queue.clear()

    def clear(self):
        self.items.clear()
        self.queue.clear()
        self.__clear = True

    def tell_or_seek(self, offset=None):
        # pylint: disable=W0212
        if self.now_playing and self.now_playing.source and self.now_playing.source._buffer and self.now_playing.source._buffer.seekable():
            if offset is None:
                return self.now_playing.source._buffer.tell()
            self.now_playing.source._buffer.seek(offset)
            return offset
        return -1


class MusicPlugin(Plugin):
    def load(self, ctx):
        super(MusicPlugin, self).load(ctx)
        self.bot.http.secret_key = 'secret_key_change_this'
        self.guilds = {}  # pylint: disable=W0201

    @Plugin.listen('VoiceStateUpdate')
    def on_voice_update(self, event):
        if event.state.user == self.state.me:
            try:
                player = self.get_player(event.guild.id)
                if event.state.deaf and player.now_playing:
                    player.skip()
            except CommandError:
                pass

    @Plugin.command('join', description='Faz o bot se conectar ao seu canal de voz.')
    def on_join(self, event):
        if event.guild.id in self.guilds:
            return event.msg.reply('Já estou tocando música aqui.')

        state = event.guild.get_member(event.author).get_voice_state()
        if not state:
            return event.msg.reply('Você precisa estar conectado em um canal de voz para usar este comando.')

        try:
            client = state.channel.connect()
        except VoiceException as exception:
            return event.msg.reply('Falha ao conectar no canal de voz: `{}`'.format(exception))

        self.guilds[event.guild.id] = MusicPlayer(
            client, event.guild.get_member(self.state.me.id), event.guild)

        event.msg.reply(
            'http://bot.brodi.design/player/{}/'.format(event.guild.id))

        self.guilds[event.guild.id].complete.wait()

        if event.guild.id in self.guilds:
            del self.guilds[event.guild.id]

    def get_player(self, guild_id):
        if guild_id not in self.guilds:
            raise CommandError('Não estou tocando música aqui.')
        return self.guilds.get(guild_id)

    @Plugin.command('leave', description='Faz o bot se desconectar do canal de voz.')
    def on_leave(self, event):
        player = self.get_player(event.guild.id)
        player.disconnect()
        if event.guild.id in self.guilds:
            del self.guilds[event.guild.id]

    @Plugin.command('play', '<url:str>', description='Adiciona um item na playlist.')
    def on_play(self, event, url):
        self.get_player(event.guild.id).queue.append(YoutubeDLInput(remove_angular_brackets(
            url)).pipe(UnbufferedOpusEncoderPlayable))

    @Plugin.command('playlist', '<url:str>', description='Adiciona vários items na playlist.')
    def on_playlist(self, event, url):
        for item in YoutubeDLInput.many(remove_angular_brackets(url)):
            self.get_player(event.guild.id).items.append(item)

    @Plugin.command('shuffle', description='Embaralha a playlist.')
    def on_shuffle(self, event):
        self.get_player(event.guild.id).queue.shuffle()

    @Plugin.command('pause', description='Pausa o player.')
    def on_pause(self, event):
        self.get_player(event.guild.id).pause()

    @Plugin.command('resume', description='Despausa o player.')
    def on_resume(self, event):
        self.get_player(event.guild.id).resume()

    @Plugin.command('skip', description='Pula o item atual.')
    def on_skip(self, event):
        if self.get_player(event.guild.id).now_playing:
            self.get_player(event.guild.id).skip()

    @Plugin.command('link', description='Mostra o link do item atual.')
    def on_link(self, event):
        if self.get_player(event.guild.id).now_playing:
            info = self.get_player(event.guild.id).now_playing.info
            return event.msg.reply('{}'.format(info.get('webpage_url', 'Não tem. :(')))
        return event.msg.reply('Não estou tocando no momento.')

    @Plugin.command('autopause', description='Ativa/desativa o autopause.')
    def on_autopause(self, event):
        self.get_player(event.guild.id).autopause = not self.get_player(
            event.guild.id).autopause
        return event.msg.reply('Autopause foi {}.'.format('ativado' if self.get_player(event.guild.id).autopause else 'desativado'))

    @Plugin.command('autovolume', description='Ativa/desativa o autovolume.')
    def on_autovolume(self, event):
        self.get_player(event.guild.id).autovolume = not self.get_player(
            event.guild.id).autovolume
        return event.msg.reply('Autovolume foi {}.'.format('ativado' if self.get_player(event.guild.id).autovolume else 'desativado'))

    @Plugin.command('volume', '[vol:float]', description='Altera o volume.')
    def on_volume(self, event, vol=None):
        player = self.get_player(event.guild.id)
        if vol:
            player.volume = vol
        else:
            return event.msg.reply('Volume atual: {}'.format(player.volume))

    @Plugin.command('duckingvolume', '[vol:float]', description='Altera a atenuação do autovolume.')
    def on_ducking_volume(self, event, vol=None):
        player = self.get_player(event.guild.id)
        if vol:
            player.ducking_volume = vol
        else:
            return event.msg.reply('Atenuação atual: {}'.format(player.ducking_volume))

    @Plugin.route('/player/')
    @Plugin.route('/player/<int:guild>/')
    def on_player_route(self, guild=0):
        from flask import render_template

        try:
            channelid = int(request.args.get('channel', 0))
        except ValueError as exception:
            return jsonify(error='Falha ao converter valor: {}'.format(exception))

        if channelid:
            try:
                channel = self.state.channels[channelid]
            except KeyError as exception:
                return jsonify(error='Canal não encontrado.\nId: {}'.format(channelid))
            if channel.is_guild and channel.is_voice:
                if channel.guild_id not in self.guilds:
                    try:
                        client = channel.connect()
                    except VoiceException as exception:
                        return jsonify(error='Falha ao conectar no canal de voz: `{}`'.format(exception))

                    self.guilds[channel.guild_id] = MusicPlayer(
                        client, channel.guild.get_member(self.state.me.id), channel.guild)
                #return jsonify(error='Já estou tocando música nesse servidor.')
                return redirect(url_for('on_player_route', guild=channel.guild_id))
            else:
                return jsonify(error='Canal precisa ser um canal do tipo voz e pertencer a uma guild.\nCanal: {}\nGuild: {}\nVoz: {}'.format(channel, channel.is_guild, channel.is_voice))

        return render_template('player.html', player=self.guilds[guild] if guild in self.guilds else None)

    @Plugin.route('/player/<int:guild>/add', methods=['POST'])
    def on_player_add_route(self, guild):

        if guild not in self.guilds:
            abort(400)

        url = request.form['url']

        if 'playlist' in request.form:
            items = list(YoutubeDLInput.many(url))
            for item in items:
                self.get_player(guild).items.append(item)
            flash('{} foram adicionados na playlist.'.format(
                len(items)), 'success')
        else:
            item = YoutubeDLInput(url)

            self.get_player(guild).queue.append(
                item.pipe(UnbufferedOpusEncoderPlayable))
            flash('"{}" foi adicionado na playlist.'.format(
                item.info['title']), 'success')

        return jsonify(action='add', data={'url': url})

    @Plugin.route('/player/<int:guild>/<string:action>')
    def on_player_queue_action_route(self, guild, action):

        if guild not in self.guilds:
            abort(400)

        player = self.get_player(guild)
        data = {}

        if action == 'shuffle':
            player.queue.shuffle()
            flash('Playlist foi embaralhada.', 'info')
        elif action == 'clear':
            player.clear()
            flash('Playlist foi esvaziada.', 'info')
        elif action == 'play' or action == 'resume':
            player.resume()
            flash('O player foi despausado.', 'info')
        elif action == 'pause':
            player.pause()
            flash('O player foi pausado.', 'info')
        elif action == 'skip':
            if player.now_playing:
                player.skip()
            player.resume()
        elif action == 'status':
            data['paused'] = True if player.paused else False
            data['queue'] = len(player.queue)
            data['items'] = len(player.items)
            data['curItem'] = None
            if player.now_playing:
                data['curItem'] = {
                    'id': player.now_playing.info['id'],
                    'duration': player.now_playing.info['duration'],
                    'fps': player.now_playing.sampling_rate * player.now_playing.sample_size / player.now_playing.frame_size,
                    'frame': player.tell_or_seek() / player.now_playing.frame_size
                }
        elif action == 'info':
            if player.now_playing:
                data['info'] = player.now_playing.info
        elif action == 'leave':
            player.disconnect()
            if guild in self.guilds:
                del self.guilds[guild]
            flash('O player foi desconectado.', 'warning')
            return redirect(url_for('on_player_route'))

        return jsonify(action=action, data=data)

    @Plugin.route('/player/<int:guild>/<string:action>/<int:index>')
    def on_player_action_route(self, guild, action, index):

        if guild not in self.guilds:
            abort(400)

        player = self.get_player(guild)

        if action == 'remove':
            item = player.queue.remove(index)
            if item:
                flash('"{}" foi removido da playlist.'.format(
                    item.info['title']), 'info')
            else:
                flash('Algo deu errado. O índice {} não foi encontrado na playlist.'.format(
                    index), 'warning')
        elif action == 'play':
            item = player.queue.remove(index)
            if item:
                player.queue.prepend(item)
                if player.now_playing:
                    player.skip()
                player.resume()
                flash('"{}" está tocando agora.'.format(
                    item.info['title']), 'success')
            else:
                flash('Algo deu errado. O índice {} não foi encontrado na playlist.'.format(
                    index), 'warning')

        return jsonify(action=action, data={'index': index})

    @Plugin.route('/player/<int:guild>/vol/<volume>')
    def on_player_volume_route(self, guild, volume):

        if guild not in self.guilds:
            abort(400)

        self.get_player(guild).volume = float(volume)

        return jsonify(action='volume', data={'volume': self.get_player(guild).volume})

    @Plugin.route('/player/<int:guild>/opt', methods=['POST'])
    def on_player_opt_route(self, guild):

        if guild not in self.guilds:
            abort(400)

        player = self.get_player(guild)

        option = request.form['options']

        if option == 'duck':
            player.autovolume = True
            player.ducking_volume = float(request.form['duckVolume'])
        elif option == 'pause':
            player.autopause = True
        elif option == 'none':
            player.autovolume = player.autopause = False

        return jsonify(action='opt', data={'option': option, 'autovolume': player.autovolume, 'autopause': player.autopause, 'duckvolume': player.ducking_volume})

    @Plugin.route('/player/<int:guild>/seek/<int:seconds>')
    def on_player_seek_route(self, guild, seconds):

        if guild not in self.guilds:
            abort(400)

        player = self.get_player(guild)

        player.tell_or_seek(
            seconds * player.now_playing.sampling_rate * player.now_playing.sample_size)

        return jsonify(action='seek', data={'frame': seconds})
