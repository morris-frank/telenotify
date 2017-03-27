#!/usr/bin/env python3
import argparse
from itertools import count
import matplotlib.pyplot as plt
import os
import re
import requests
import sys
from tabulate import tabulate
import time
import yaml


CONFIGFILE = 'config.yaml'

class Notifier(object):
    APIBASE = 'https://api.telegram.org/bot'
    TMPDIR = '/tmp/'

    CAFFE_TRAIN_LOSS = {'Search': 'Iteration ([0-9]+) \(([0-9]+\.[0-9]+) iter\/s, ([0-9]+\.[0-9]+)s\/20 iters\), loss = ([0-9]+\.[0-9]+)',
                        'Fields': [('Iteration', int, True, False),
                                 ('Iter/s', float, False, False),
                                 ('s/20 Iters', float, False, False),
                                 ('Loss', float, False, True)]}

    CAFFE_TEST_LOSS = {'Search': 'Test net output #0: loss = ([0-9]+\.[0-9]+)',
                       'Fields': [('Loss', float, False, True)]}

    def __init__(self, argv=None, configfile=None):
        self.interval = 4
        self._registered_re = {}
        self._registered_vals = {}
        self._registered_re_idx = 0
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

    def parse_log_re(self, res):
        assert(isinstance(res, dict))
        assert(len(res) == 2)
        assert('Search' in res)
        assert('Fields' in res)
        assert(isinstance(res['Search'], str))
        assert(isinstance(res['Fields'], list))
        for field in res['Fields']:
            assert(isinstance(field, tuple))
            assert(len(field) == 4)
            assert(isinstance(field[0], str))
            assert(isinstance(field[1], type))
            assert(isinstance(field[2], bool))
            assert(isinstance(field[3], bool))
        return True

    def tail(self, path):
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
                    testiter = self.callback_re(line)

    def register_re(self, res):
        self.parse_log_re(res)
        self._registered_re[str(self._registered_re_idx)] = res
        self._registered_vals[str(self._registered_re_idx)] = {}
        for fieldname, _type, _index, _display in res['Fields']:
            self._registered_vals[str(self._registered_re_idx)][fieldname] = []
        self._registered_re_idx += 1

    def callback_re(self, line):
        for res_key, res in self._registered_re.items():
            res_search = re.search(res['Search'], line)
            if res_search is None:
                continue
            res_search = res_search.groups()
            for field_it, field in enumerate(res['Fields']):
                self._registered_vals[res_key][field[0]].append(field[1](res_search[field_it]))

    def lossgraph(self, title):
        fname = Notifier.TMPDIR + str(time.time()) + '_lossgraph.png'
        fig = plt.figure(frameon=False)
        for res_key, res in self._registered_re.items():
            for field in res['Fields']:
                if field[2]:
                    indexes = self._registered_vals[res_key][field[0]]
                    xlabel = field[0]
        for res_key, res in self._registered_re.items():
            for fieldname, _type, _index, display in res['Fields']:
                if display:
                    fieldvalues = self._registered_vals[res_key][fieldname]
                    plt.plot(indexes, fieldvalues, label=fieldname)
        plt.xlabel(xlabel)
        plt.title(title)
        fig.savefig(fname)
        plt.close(fig)
        return fname

    def sendMatrix(self, matrix, preText=''):
        strTable = '```\n{}{}```'.format(preText,
                                         tabulate(matrix, tablefmt='grid'))
        self.sendMessage(strTable, markdown=True)

    def sendMessage(self, msg, markdown=False):
        self._send_telegram_msg(str(time.time()), msg, markdown=markdown)

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

    def _send_telegram_msg(self, title, msg, markdown=False):
        message = '{0} : {1}'.format(title.encode(), msg.encode())
        uri = Notifier.API + 'sendMessage'
        payload = {'chat_id': Notifier.ID, 'text': msg}
        if markdown:
            payload['parse_mode'] = 'Markdown'
        self._make_telegram_request(uri, payload)

    def _make_telegram_request(self, uri, payload, files=None):
        print('Telegram in use with API KEY: {0}'.format(
            Notifier.APIKEY))
        r = requests.post(uri, payload, files=files)
        r.raise_for_status()


def main(argv):
    n = Notifier(argv)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('No arguments given')
        sys.exit()
    main(sys.argv[1:])
