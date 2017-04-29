# -*- coding: utf-8 -*-

"""
utils
"""
from hashlib import md5
import requests
import time
import os.path as path


def get_server_time():
    """
    get server time (GMT timestamp)
    :return:
    """
    response = requests.get('http://www.aliyun.com')
    t = response.headers.get('date')
    time_tuple = time.strptime(t[5:25], "%d %b %Y %H:%M:%S")
    stamp = int(time.mktime(time_tuple))
    return stamp


def content_md5(content):
    """
    md5 of string content
    :param content:
    :return:
    """
    m = md5()
    m.update(content.encode())
    return m.hexdigest().upper()


def file_md5(file_path):
    """
    calculation file md5 (upper case)
    :param file_path:
    :return:
    """
    if path.isdir(file_path):
        raise TypeError('input is a directory, use "dir_md5()" instead')
    m = md5()
    a_file = open(file_path, 'rb')
    m.update(a_file.read())
    a_file.close()
    return m.hexdigest().upper()


def dir_md5(dir_path):
    """
    calculate directory md5 (upper case)
    :param dir_path:
    :return:
    """
    pass


if __name__ == "__main__":
    print(content_md5("$DIR$"))
