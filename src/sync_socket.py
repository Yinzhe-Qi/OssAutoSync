# -*- coding: utf-8 -*-

# Copyright 2016 Qi Yinzhe(Yinzhe-Qi) <goblin-qyz@163.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import src.oss2_utils as util
from src.object_manager import ObjectManager
from src.oss_model import OssObject
from oss2.models import SimplifiedObjectInfo
from watchdog.events import *
import logging
import os
import re

logger = logging.getLogger("main.syncSocket")


class SyncSocket(FileSystemEventHandler):
    """
    class representing a local-remote sync link
    """
    def __init__(self, bucket, local_remote_tup):
        FileSystemEventHandler.__init__(self)
        self.__bucket = bucket
        self.__local_remote_tup = local_remote_tup
        self.__obj_manager = ObjectManager(bucket)
        self.__local_index = self._local_indexing()
        self.synchronize()

    def on_moved(self, event):
        """rename"""
        try:
            remote_old = self.__local_to_remote(event.src_path)
            remote_new = self.__local_to_remote(event.dest_path)
            if not self.__obj_manager.rename_object(remote_old, remote_new):
                # put new file if old file does not exist
                self.__obj_manager.put_object(remote_new, event.dest_path)
            logger.info("file moved from {0} to {1}".format(event.src_path, event.dest_path))
        except Exception as e:
            logger.error("rename error-- " + util.exception_string(e))

    def on_created(self, event):
        """create"""
        remote = self.__local_to_remote(event.src_path)
        self.__obj_manager.put_object(remote, event.src_path)
        logger.info("file created:{0}".format(event.src_path))

    def on_deleted(self, event):
        """delete"""
        remote = self.__local_to_remote(event.src_path)
        self.__obj_manager.delete_object(remote)
        logger.info("file deleted:{0}".format(event.src_path))

    def is_name_equal(self, local_obj, remote_obj):
        """
        :param local_obj: local file object, should be of type OssObject
        :param remote_obj: remote oss object, should be of type SimplifiedObjectInfo
        :return:
        """
        if not type(local_obj) is OssObject:
            raise TypeError('local_obj should be of type OssObject')
        if not type(remote_obj) is SimplifiedObjectInfo:
            raise TypeError('remote_obj should be of type SimplifiedObjectInfo')
        return self.__local_to_remote(local_obj.key) == remote_obj.key

    def is_content_equal(self, local_obj, remote_obj):
        """
        :param local_obj: local file object, should be of type OssObject
        :param remote_obj: remote oss object, should be of type SimplifiedObjectInfo
        :return:
        """
        if not type(local_obj) is OssObject:
            raise TypeError('local_obj should be of type OssObject')
        if not type(remote_obj) is SimplifiedObjectInfo:
            raise TypeError('remote_obj should be of type SimplifiedObjectInfo')
        return local_obj.etag == remote_obj.etag

    def synchronize(self):
        """
        synchronize local_path with the remote bucket
        :return:
        """
        # get remote objects
        remote_iter = self.__obj_manager.get_object_iter(self.__local_remote_tup[1])

        tmp_set = set([])
        for obj in remote_iter:
            local_key = self.__remote_to_local(obj.key)
            if local_key in self.__local_index:   # both have this file
                local_obj = self.__local_index[local_key]
                if not self.is_content_equal(local_obj, obj):   # different content
                    if local_obj.last_modified >= obj.last_modified:    # local is newer
                        self.__obj_manager.put_object(obj.key, local_key)
                    else:                                               # remote is newer
                        self.__obj_manager.get_object(obj.key, local_key)
            else:
                if os.path.isdir(local_key):
                    if not os.path.exists(local_key):
                        os.makedirs(local_key)
                else:
                    tmp_dir = local_key[:local_key.rfind('\\') + 1]
                    if not os.path.exists(tmp_dir):
                        os.makedirs(tmp_dir)
                    self.__obj_manager.get_object(obj.key, local_key)
            tmp_set.add(local_key)

        for local_key in self.__local_index:
            if local_key not in tmp_set:
                self.__obj_manager.put_object(self.__local_to_remote(local_key), local_key)

    def _local_indexing(self):
        """
        generate local file index map {local_path: OssObject}
        :return:
        """
        oss_map = self._recursive_indexing(self.__local_remote_tup[0], None)
        return oss_map

    def _recursive_indexing(self, local_path, oss_map):
        if not oss_map:
            oss_map = {}
        for _dir in os.listdir(local_path):
            abs_dir = local_path + '\\' + _dir
            if not os.path.isdir(abs_dir):
                oss_map[abs_dir] = OssObject(abs_dir)
            else:
                oss_map[abs_dir + '\\'] = OssObject(abs_dir)
                self._recursive_indexing(abs_dir, oss_map)
        return oss_map

    def __local_to_remote(self, local_path):
        """
        transfer local path to the corresponding remote path using directory map
        :param local_path:
        :return:
        """
        rootl, rootr = self.__local_remote_tup[0], self.__local_remote_tup[1]
        if rootl[-1] != '\\':
            rootl += '\\'
        if rootr[-1] != '/':
            rootr += '/'
        rootl_re = rootl.replace('\\', '\\\\')
        pt = re.compile(r"^" + rootl_re)
        if not pt.match(local_path):
            raise FileNotFoundError('local_path does not belong to this root')

        common = local_path[len(rootl):]
        remote = rootr + common
        if len(os.path.splitext(remote)[-1]) == 0:
            remote += '/'
        remote = remote.replace('\\', '/')
        return remote

    def __remote_to_local(self, remote_path):
        """
        transfer remote path to the corresponding local path using directory map
        :param remote_path:
        :return:
        """
        rootl, rootr = self.__local_remote_tup[0], self.__local_remote_tup[1]
        if rootl[-1] != '\\':
            rootl += '\\'
        if rootr[-1] != '/':
            rootr += '/'
        pt = re.compile(r"^" + rootr)
        if not pt.match(remote_path):
            raise FileNotFoundError('remote_path does not belong to this root')

        common = remote_path[len(rootr):]
        local = rootl + common
        local = local.replace('/', '\\')
        return local