# -*- coding: utf-8 -*-
# # Copyright (c) 2017 Shotgun Software Inc.
# #
# # CONFIDENTIAL AND PROPRIETARY
# #
# # This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# # Source Code License included in this distribution package. See LICENSE.
# # By accessing, using, copying or modifying this work you indicate your
# # agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# # not expressly granted therein are reserved by Shotgun Software Inc.

import os
import nuke
import sgtk
import tractor.api.author as author
from tank.platform.qt import QtCore, QtGui

HookBaseClass = sgtk.get_hook_baseclass()

class NukeUndistPublishPlugin(HookBaseClass):
    """
    MM Undist 퍼블리쉬
    """

    @property
    def description(self):
        """
        퍼블리싱 기능에 대한 설명 (UI에 표시됨)
        """
        return """<p> 언디스토션에 대한 퍼블리쉬입니다. .<br>
        undist(reformat) 노드를 찾아 샷의 해상도와 비교 후 다를 경우,
        언디스토션을 샷그리드에 적용 및 퍼블리쉬합니다..
        </p>"""

    @property
    def settings(self):
        """
        퍼블리싱에 필요한 설정값 정의
        """
        base_settings = super(NukeUndistPublishPlugin, self).settings or {}

        # self.init()

        nuke_publish_settings = {
            "Publish Template": {
                "type": "template",
                "default": None,
                "description": "퍼블리싱할 때 사용할 템플릿 경로 (templates.yml 참고)",
            }
        }

        base_settings.update(nuke_publish_settings)
        return base_settings
    
    @property
    def item_filters(self):
        """
        퍼블리싱 가능한 아이템 유형 설정 (Nuke의 특정 유형만 선택)
        """
        publisher = self.parent
        engine = publisher.engine

        return ["nuke.session"]
    
    def accept(self, settings, item):
        """
        현재 Nuke 세션이 퍼블리싱 가능한지 확인
        """
        path = _session_path()

        publisher = self.parent
        engine = publisher.engine

        current_task = publisher.context.task
        task_name = current_task['name']

        if not path:
            self.logger.warn("Nuke 스크립트가 저장되지 않았습니다.")
            return {"accepted": False}

        self.logger.info("Nuke Retime 퍼블리싱 가능")
        if task_name == "mm":
            return {"accepted": True, "checked": True}
        return {"accepted": False}
    


    def validate(self, settings, item):
        """
        퍼블리싱 전에 확인할 사항 검증
        """

        undist_node = nuke.toNode("undist")
        if not undist_node:
            msg = QtGui.QMessageBox()
            msg.setIcon(QtGui.QMessageBox.Warning)
            msg.setText("undist 이름을 가진 reformat 노드가 존재 하지 않습니다.")
            msg.setInformativeText("undist는 소문자로 해주세요.")
            msg.setWindowTitle("Publish Validate Warning")
            msg.setStandardButtons(QtGui.QMessageBox.Ok)
            msg.exec_()
            return False
                
        
        self.logger.info("Nuke Retime 퍼블리싱 검증 완료")
        return True
    
    def compare_resolution(self, resolution, undist_resolution):
        x = int(resolution.split("*")[0])
        y = int(resolution.split("*")[1])
        ux = int(undist_resolution.split("*")[0])
        uy = int(undist_resolution.split("*")[1])

        # 다를경우 undist 적용
        if x != ux and y != uy:
            return True



    def publish(self, settings, item):
        """
        퍼블리싱 실행 (현재는 동작 없음)
        """

        self.__engine = sgtk.platform.current_engine()
        self.__context = self.__engine.context
        sg = self.__engine.shotgun
        entity =  self.__context.entity
        resolution = sg.find_one("Shot", [['id', 'is', entity['id']]],['sg_resolution'])
        # print(resolution)
        # print(resolution["sg_resolution"])

        undist_node = nuke.toNode("undist")
        format_value = undist_node["format"].value()
        undist_resolution = str(format_value.width()) + "*" + str(format_value.height())
        print(undist_resolution)
        print(resolution["sg_resolution"])

        if self.compare_resolution(undist_resolution,resolution["sg_resolution"]):
            print("undist 적용해야함")
            sg.update(
                "Shot",
                entity['id'],
                {
                    "sg_undistortion": True,
                    "sg_undistortion_resolution": undist_resolution
                }
            )

        self.logger.info("퍼블리싱 실행")
        

    def finalize(self, settings, item):
        """
        퍼블리싱 후 정리 (현재는 동작 없음)
        """
        self.logger.info("퍼블리싱 완료 후 정리 (현재 동작 없음)")

    

def _session_path():
    """
    현재 Nuke 스크립트의 경로를 반환
    """
    root_name = nuke.root().name()
    return None if root_name == "Root" else root_name

