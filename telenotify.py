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
    APIBASE = 'https://api.telegram.org/bot'

    def __init__(self, argv=None, configfile=None):
        self.interval = 4
        self.appendcount = 0
        self.train_losses = []
        self.train_iters = []
        self.test_losses = []
        self.test_iters = []
        if configfile is None:
            self.loadConfig(CONFIGFILE)
        else:
            self.loadConfig(configfile)
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
        Notifier.API = Notifier.APIBASE + config['TELEGRAM_APIKEY'] + '/'
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
            testiter = 0
            while True:
                curr_position = f.tell()
                line = f.readline()
                if not line:
                    f.seek(curr_position)
                    time.sleep(self.interval)
                else:
                    testiter = self.callback(line, name, testiter)

    def callback(self, line, name, testiter):
        testloss = re.search('Iteration ([0-9]+), Testing net', line)
        if testloss is not None:
            testloss = testloss.groups()
            return int(testloss[0])
        trainloss = re.search('Iteration ([0-9]+), loss = (.+)$', line)
        testloss = re.search('Test net output \#([0-9])+: loss = ([0-9]+\.[0-9]+) .+$', line)
        if testloss is not None:
            testloss = testloss.groups()
            self.test_iters.append(testiter)
            self.test_losses.append(float(testloss[1]))
            print('Test: {} - {}'.format(testloss[0], testloss[1]))
        if trainloss is not None:
            trainloss = trainloss.groups()
            self.train_iters.append(int(trainloss[0]))
            self.train_losses.append(float(trainloss[1]))
            print('Train: {} - {}'.format(trainloss[0], trainloss[1]))
            self.appendcount += 1
            if self.appendcount >= 5:
                self._send_telegram_photo(self.lossgraph(name), name)
                self.appendcount = 0
        return 0

    def lossgraph(self, title):
        fname = str(time.time()) + '_lossgraph.png'
        fig = plt.figure(frameon=False)
        plt.plot(self.train_iters, self.train_losses, 'r',
                 self.test_iters, self.test_losses, 'g')
        plt.xlabel('iterations')
        plt.ylabel('loss')
        plt.title(title)
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
        r.raise_for_status()


def main(argv):
    n = Notifier(argv)
    n.start()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('No arguments given')
        sys.exit()
    main(sys.argv[1:])
