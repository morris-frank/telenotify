#!/usr/bin/env python3
import argparse
import matplotlib.pyplot as plt
import os
import re
import requests
import sys
import tempfile
import time
import yaml


CONFIGFILE = 'config.yaml'


class Notifier(object):
    API = 'https://api.telegram.org/bot'

    def __init__(self, argv=None):
        self.interval = 4
        self.appendcount = 0
        self.losses = []
        self.iters = []
        self.loadConfig(CONFIGFILE)
        if argv is not None:
            self.parseArgs(argv)

    def loadConfig(self, configfile):
        with open(configfile, 'r') as f:
            try:
                config = yaml.load(f)
            except yaml.YAMLError as e:
                print('Config {} not loadable.'.format(configfile))
                sys.exit(1)
        Notifier.APIKEY = config['TELEGRAM_APIKEY']
        Notifier.API += config['TELEGRAM_APIKEY'] + '/'
        Notifier.ID = config['TELEGRAM_ID']

    def parseArgs(self, argv):
        '''Parse the arguments for an experiment script'''
        parser = argparse.ArgumentParser(
            description='Adds an Notifier for that file')
        parser.add_argument('file', type=str, nargs=1,
                            help='The Caffe log file')
        parser.add_argument('--lossgraph', action='store_true')
        self.sysargs = parser.parse_args(args=argv)

    def start(self):
        for path in self.sysargs.file:
            self._start(path)

    def _start(self, path):
        name = os.path.basename(path)
        with open(path, 'r') as f:
            f.seek(0, 2)
            while True:
                curr_position = f.tell()
                line = f.readline()
                if not line:
                    f.seek(curr_position)
                    time.sleep(self.interval)
                else:
                    self.callback(line, name)

    def callback(self, line, name):
        losslist = re.search('Iteration ([0-9]+), loss = (.+)$', line)
        if losslist is None:
            return
        losslist = losslist.groups()
        self.iters.append(int(losslist[0]))
        self.losses.append(float(losslist[1]))
        print('{} - {}'.format(losslist[0], losslist[1]))
        self.appendcount += 1
        if self.appendcount >= 5:
            self._send_telegram_photo(self.lossgraph(), name)
            self.appendcount = 0

    def lossgraph(self):
        fname = str(time.time()) + '_lossgraph.png'
        fig = plt.figure(frameon=False)
        plt.plot(self.iters, self.losses)
        plt.xlabel('iterations')
        plt.ylabel('loss')
        plt.title(self.sysargs.file)
        fig.savefig(fname)
        plt.close(fig)
        return fname

    def _send_telegram_photo(self, impath, caption=None):
        basename = os.path.basename(impath)
        ext = os.path.splitext(impath)[1][1:].lower()
        ctypes = {'jpeg': 'image/jpeg', 'jpg': 'image/jpeg',
                    'png': 'image/png'}
        if ext not in ctypes:
            raise OSError('''Image {}
                          has no known extension {}
                          for _send_telegram_photo!'''.format(impath, ctypes))
        uri = Notifier.API + 'sendPhoto'
        photopayload = {'photo': (basename, open(impath, 'rb'), ctypes[ext])}
        payload = {'chat_id': Notifier.ID}
        if caption is not None:
            payload['caption'] = caption
        self._make_telegram_request(uri, payload, files=photopayload)

    def _send_telegram_msg(self, title, msg):
        message = '{0} : {1}'.format(title.encode(), msg.encode())
        uri = Notifier.API + 'sendMessage'
        payload = {'chat_id': Notifier.ID, 'text': msg}
        self._make_telegram_request(uri, payload)

    def _make_telegram_request(self, uri, payload, files=None):
        print('Telegram in use with API KEY: {0}'.format(
            Notifier.APIKEY))
        r = requests.post(uri, payload, files=files)
        print(r.json())
        r.raise_for_status()


def main(argv):
    n = Notifier(argv)
    n.start()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('No arguments given')
        sys.exit()
    main(sys.argv[1:])
