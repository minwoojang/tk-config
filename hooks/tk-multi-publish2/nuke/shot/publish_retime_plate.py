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

HookBaseClass = sgtk.get_hook_baseclass()

class NukeRetimePublishPlugin(HookBaseClass):
    """
    Nuke Retime 퍼블리싱 플러그인 (기본 구조)
    """

    @property
    def description(self):
        """
        퍼블리싱 기능에 대한 설명 (UI에 표시됨)
        """
        return """<p> 리타임 플레이트 작업의 경우 이 플러그인이 작동합니다.<br>
        그 외 누크 퍼블리쉬 과정에서는 이 플러그인은 작동하지 않습니다.
        </p>"""

    @property
    def settings(self):
        """
        퍼블리싱에 필요한 설정값 정의
        """
        base_settings = super(NukeRetimePublishPlugin, self).settings or {}

        self.init()

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
        if task_name == "retime":
            return {"accepted": True, "checked": True}
        return {"accepted": False}
    

    def init(self):
        # 현재 Toolkit 컨텍스트 가져오기
        self.__engine = sgtk.platform.current_engine() 
        self.__context = self.__engine.context
        self.__project = self.__context.project
        self.__sg = self.__engine.shotgun
        self.__user = self.__context.user
        self.__shot_ent = self.__context.entity
        self.__project_info = self.__sg.find_one("Project", [['id', 'is', self.__project['id']]],
                                                ['sg_color_space', 'sg_mov_codec', 'sg_out_format', 'sg_fps', 'sg_mov_colorspace'])
        self.__user_info = self.__sg.find_one('HumanUser', [['id', 'is', self.__user['id']]], ['sg_initials'])
        self.__first_frame = int(nuke.root()["first_frame"].value())
        self.__last_frame = int(nuke.root()["last_frame"].value())

        tk = sgtk.sgtk_from_entity("Project", self.__project_info['id'])
        self.__nuke_shot_work = tk.templates['nuke_shot_work']
        self.__retime_org_mov = tk.templates['nuke_write_mov_plate']
        self.__retime_jpg = tk.templates['retime_jpg']
        self.__retime_exr = None
        self.__retime_dpx = None
        self.__type = None
        
        if "exr" in self.__project_info['sg_out_format']:
            self.__retime_exr = tk.templates['retime_exr']
            self.__type = "exr"
        else:
            self.__retime_dpx = tk.templates['retime_dpx']
            self.__type = "dpx"
        # path = nuke.root().name().replace("/", os.path.sep)
        path = _session_path()
        fields = self.__nuke_shot_work.get_fields(path)

        # 누크씬파일에 프로젝트 이름 없을 경우
        if 'Project' not in fields:        
            fields['Project'] = self.__project['name']
            
        self.__retime_exr_path = None
        self.__retime_dpx_path = None
        self.__retime_org_mov_path = self.__retime_org_mov.apply_fields(fields)
        self.__retime_jpg = self.__retime_jpg.apply_fields(fields)
        if self.__type == "exr":
            self.__retime_exr_path = self.__retime_exr.apply_fields(fields)
        else:
            self.__retime_dpx_path = self.__retime_dpx.apply_fields(fields)
        ppath = path.split('/')
        ppath = os.path.join('/'.join(ppath[:-4]), "plate", ppath[-1])
        self._upload_mov_path = ppath.replace(".nk", ".mov")

        

    def validate(self, settings, item):
        """
        퍼블리싱 전에 확인할 사항 검증
        """
        path = _session_path()
        
        if not path:
            error_msg = "Nuke 스크립트가 저장되지 않았습니다."
            self.logger.error(error_msg)
            raise Exception(error_msg)
        
        #write 노드가 존재하는지 확인
        write_nodes = [node for node in nuke.allNodes() if node.Class() == "Write"]
        if not write_nodes:
            nuke.message("write node 을 생성하세요.")
            return False
        
        #write노드가 여러개일 경우를 대비하여 retime_ 가 들어간 부분만 리타임으로 생각한다.
        self.retime_write_nodes = [node for node in write_nodes if "retime_" in node.name()]
        if not self.retime_write_nodes:
            nuke.message("write node의 이름을 점검하세요. ex) retime_ 부분이 필요합니다.")
            return False
        
        print(self._upload_mov_path)
        print(self._upload_mov_path)
        print(self._upload_mov_path)
        print(self._upload_mov_path)
        

        self.logger.info("Nuke Retime 퍼블리싱 검증 완료")
        return True
    
    def _create_mov_to_jpg_job(self):
        jpg = self._upload_mov_path.replace(".mov", "_convert_jpg.py")
        
        nk = '# -*- coding: utf-8 -*-\n'
        nk += 'import nuke\n'
        nk += 'import os\n\n'
        nk += 'nuke.root().knob("colorManagement").setValue("OCIO")\n'

        nk += 'read = nuke.nodes.Read(file = "{}")\n'.format(self._upload_mov_path)
        nk += 'nuke.knob("root.first_frame", "{}")\n'.format(str(int(self.__first_frame)))
        nk += 'nuke.knob("root.last_frame", "{}")\n'.format(str(int(self.__last_frame)))
        nk += 'read["colorspace"].setValue("{}")\n'.format("rec709")

        nk += 'previous_node = read\n'
        nk += 'timeshift = nuke.nodes.TimeOffset(inputs=[previous_node], time_offset=1000)\n'
        nk += 'previous_node = timeshift\n'
        nk += 'read["first"].setValue({})\n'.format(int(self.__first_frame)-1000)
        nk += 'read["last"].setValue({})\n'.format(int(self.__last_frame)-1000)
        nk += 'write = nuke.nodes.Write(inputs=[previous_node], file="{}")\n'.format(self.__retime_jpg)
        nk += 'write["create_directories"].setValue(True)\n'
        nk += 'write["colorspace"].setValue("{}")\n'.format("sRGB")
        nk += 'write.knob("file_type").setValue("jpg")\n'
        nk += 'write["_jpeg_quality"].setValue(1.0)\n'
        nk += 'write["_jpeg_sub_sampling"].setValue("4:4:4")\n'
        nk += 'nuke.execute(write, {}, {})\n'.format(int(self.__first_frame), int(self.__last_frame))
        nk += 'exit()\n'

        with open(jpg, "w") as f:
                f.write(nk)
            
        os.chmod(jpg, 0o777)
            
        return jpg  

    def _create_jpg_job(self, nuke_script):
        command = ['rez-env','nuke-13.2.8','--','nuke','-ix',nuke_script]
        return command
    
    def _create_mov_job(self, nuke_script):
        colorspace = str(self.__project_info['sg_color_space'])
        if not colorspace.find("ACES") == -1:
            command = ['rez-env', 'nuke-13.2.8','ocio_config','--', 'nuke', '-ix',nuke_script]
        elif not colorspace.find("Arri") == -1:
            command = ['rez-env', 'nuke-13.2.8','alexa4_config','--', 'nuke', '-ix',nuke_script]
        elif not colorspace.find("Alexa") == -1:
            command = ['rez-env', 'nuke-13.2.8','alexa_config','--', 'nuke', '-ix',nuke_script]
        elif not colorspace.find('Sony') == -1:
            command = ['rez-env', 'nuke-13.2.8','sony_config','--', 'nuke', '-ix',nuke_script]
        else:
            command = ['rez-env', 'nuke-13.2.8','--', 'nuke', '-ix']

        return command

    def _create_retime_mov_job(self):
        color_space = self.__project_info['sg_color_space']
        mov_codec = self.__project_info['sg_mov_codec']
        mov_fps = self.__project_info['sg_fps']
        mov_colorspace = self.__project_info['sg_mov_colorspace']
        
        # return 

        nk = ''
        nk += '# -*- coding: utf-8 -*-\n'
        nk += 'import nuke\n'
        nk += 'nuke.root().knob("colorManagement").setValue("OCIO")\n'
        nk += 'nuke.knob("root.first_frame", "{}")\n'.format(str(int(self.__first_frame)))
        nk += 'nuke.knob("root.last_frame", "{}")\n'.format(str(int(self.__last_frame)))
        nk += 'nuke.knob("root.fps", "{}")\n'.format(mov_fps)
        if self.__type == "exr":
            nk += 'read = nuke.nodes.Read(name="Read1", file="{}")\n'.format(self.__retime_exr_path)
        elif self.__type == "dpx":
            nk += 'read = nuke.nodes.Read(name="Read1", file="{}")\n'.format(self.__retime_dpx_path)
        nk += 'read["first"].setValue({})\n'.format(int(self.__first_frame))
        nk += 'read["last"].setValue({})\n'.format(int(self.__last_frame))
        nk += 'read["colorspace"].setValue("{}")\n'.format(color_space)
        nk += 'output = "{}"\n'.format(self._upload_mov_path)
        nk += 'write = nuke.nodes.Write(name="mov_write", file=output)\n'
        nk += 'write.setInput(0, read)\n'
        nk += 'write["file_type"].setValue("mov")\n'
        nk += 'write["create_directories"].setValue(True)\n'
        nk += 'write["mov64_codec"].setValue("{}")\n'.format(mov_codec)
        nk += 'write["colorspace"].setValue("{}")\n'.format(mov_colorspace)
        nk += 'write["mov64_fps"].setValue({})\n'.format(mov_fps)
        nk += 'nuke.execute(write, {}, {})\n'.format(int(self.__first_frame), int(self.__last_frame))
        nk += 'exit()\n'
        
        mov = self._upload_mov_path.replace(".mov",".py")


        with open(mov, "w") as f:
            f.write(nk)

        os.chmod(mov, 0o777)

        return mov

    def is_publish_type_available(self, publish_type):
        """
        ShotGrid에서 특정 퍼블리시 타입이 존재하는지 확인
        :param publish_type: 확인할 퍼블리시 타입 (예: "Plate")
        :return: 존재하면 True, 없으면 False
        """

        # ShotGrid에서 사용 가능한 퍼블리시 타입 목록 가져오기
        filters = [["code", "is", publish_type]]
        fields = ["code","id"]
        result = self.__sg.find_one("PublishedFileType", filters, fields)

        return result
        

    def publish(self, settings, item):
        """
        퍼블리싱 실행 (현재는 동작 없음)
        """
        
        path = _session_path()

        #퍼블리쉬로 이동해야함
        '''
        1. nuke 파일에 write노드 렌더
        2. 렌더 노드된 결과물을 가지고 mov생성
        3. mov생성된걸로 jpg
        '''
        if self.is_publish_type_available("Retime"):
            # EXR 파일 경로 가져오기
            self._exr_path = self.retime_write_nodes[0]['file'].value()
            # self._create_output_path()
            mov_job = self._create_retime_mov_job()
            jpg_job = self._create_mov_to_jpg_job()

            colorspace = str(self.__project_info['sg_color_space'])

            # Retime 퍼블리쉬 아이템 등록
            # 1. Retime exr or dpx 플레이트
            # jpg 시퀀스는 생략
            name = item.properties.get("publish_name", os.path.basename(path))        
            version = int(name.split("_")[4].split(".")[0].split("v")[-1])
            if self.__type == "exr":
                item.properties["local_path"] = self.__retime_exr_path
                # print(self.__retime_exr_path)
            elif self.__type == "dpx":
                item.properties["local_path"] = self.__retime_dpx_path
                # print(self.__retime_dpx_path)

            sg = self.parent.shotgun
            publish_type = sg.find_one("PublishedFileType", [["code", "is", "Retime"]], ["code"])
            item.properties["published_file_type"] = publish_type["code"]
            item.thumbnail_enabled = False


            tk = sgtk.sgtk_from_entity("Project", self.__project["id"])
            context = tk.context_from_entity("Shot", self.__shot_ent["id"])

            publish_data = {
                "tk" : tk,
                "context" : context,
                "path" : item.properties["local_path"],
                "name" : name,
                "create_by" : self.__user,
                "version_number": version,
                "published_file_type": item.properties["published_file_type"],
            }

            # ShotGrid API를 사용하여 퍼블리시 생성
            self.published_ent = sgtk.util.register_publish(**publish_data)
            pub_id = self.published_ent['id']
            shupload_job = self.sg_upload_version(pub_id)

            # Job 생성
            job = author.Job(service="tractor")
            
            title = '<font color="#008000">[RETIME_PUBLISH]</font> <font color="#87cefa">[{0}]</font> {1}_publish'.format(self.__user_info['sg_initials'], "retime")
            job.title = title
            job.projects = [self.__project['name']]
            job.service = "Linux64"
            job.priority = 10

            # Main Task 생성
            main_task = author.Task(title="Main")

            # Render Task 생성
            render_task = author.Task(title="Render")

            command = None
            if "ACES" in colorspace:
                command = ['rez-env', 'nuke-13.2.8', 'ocio_config']
            elif "Arri" in colorspace:
                command = ['rez-env', 'nuke-13.2.8', 'alexa4_config']
            elif "Alexa" in colorspace:
                command = ['rez-env', 'nuke-13.2.8', 'alexa_config']
            elif "Sony" in colorspace:
                command = ['rez-env', 'nuke-13.2.8', 'sony_config']
            else:
                command = ['rez-env', 'nuke-13.2.8']

            command.append('--')
            command.append('nuke')
            command.append('-t')
            command.append('-X')
            command.append(self.retime_write_nodes[0].name())
            command.append('-F')
            command.append(f"{self.__first_frame}-{self.__last_frame}") 
            command.append(_session_path())
            frame_task = author.Task(title=f"Frame Render")
            frame_task.addCommand(author.Command(argv=command))
            render_task.addChild(frame_task)

            # Render Task 추가
            # main_task.addChild(render_task)

            mov_command = self._create_mov_job(mov_job)
            mov_task = author.Task(title="MOV Generation")
            mov_task.addCommand(author.Command(argv=mov_command))
            mov_task.addChild(render_task)

            #RM Task를 Main Task의 독립적인 Task로 추가
            rm_task = author.Task(title="MOV JOB rm")
            rm_command = ['rm', '-rf', mov_job]
            rm_task.addCommand(author.Command(argv=rm_command))
            rm_task.addChild(mov_task)

            jpg_command = self._create_jpg_job(jpg_job)
            jpg_task = author.Task(title="JPG Generation")
            jpg_task.addCommand(author.Command(argv=jpg_command))
            jpg_task.addChild(rm_task)


            jpg_rm_task = author.Task(title="jpg JOB rm")
            jpg_rm_command = ['rm','-rf', jpg_job]
            jpg_rm_task.addCommand(author.Command(argv=jpg_rm_command))
            jpg_rm_task.addChild(jpg_task)

            sg_upload_task = author.Task(title="sg_version_upload")
            sg_upload_task.addCommand(author.Command(argv=shupload_job))
            sg_upload_task.addChild(jpg_rm_task)
            
            main_task.addChild(sg_upload_task)


            job.addChild(main_task)
            job.spool(hostname="10.0.20.30", owner="cocoa")       
            

        self.logger.info("퍼블리싱 실행")
        
        # 실제 퍼블리싱 코드 추가 가능

    def sg_upload_version(self, published_file_id):
        """
        ShotGrid에 Version 생성 후 MOV 파일 업로드
        """
        script_path = self._upload_mov_path.replace(".mov", "_sg_version.py")
        code = os.path.basename(self._upload_mov_path.split(".")[0])
        description = "Retime publish"
        task_name = "Plate"
        status = "rdy"
        # Plate Task 찾기
        plate_task = self.__sg.find_one("Task", [["content", "is", task_name],], ["id","content"])

        nk = ''
        nk += '# -*- coding: utf-8 -*-\n'
        nk += 'import os\n'
        nk += 'import shotgun_api3\n'
        nk += 'HOST = "https://cocoavision.shotgunstudio.com"\n'
        nk += 'script_name = "cocoa"\n'
        nk += 'script_key = "gxvyr^nrbiccacHoijjtrz4fs"\n'
        nk += 'sg = shotgun_api3.Shotgun(HOST, script_name=script_name, api_key=script_key)\n\n'
        nk += 'version_data = {\n'
        nk += '    "project": {"type": "Project", "id": %d},\n' % self.__project["id"]
        nk += '    "code": "%s",\n' % code
        nk += '    "entity": {"type": "Shot", "id": %d},\n' % self.__shot_ent["id"]
        nk += '    "sg_task": {"type": "Task", "id": %d},\n' % plate_task["id"]  # Plate Task 연결
        nk += '    "user": {"type": "HumanUser", "id": %d},\n' % self.__user["id"]
        nk += '    "description": "%s",\n' % description
        nk += '    "sg_status_list": "%s"\n' % status
        nk += '}\n'
        nk += 'version = sg.create("Version", version_data)\n'
        nk += 'mov_path = "%s"\n' % self._upload_mov_path
        nk += 'sg.upload("Version", version["id"], mov_path, "sg_uploaded_movie")\n'
        # nk += 'sg.update("PublishedFile", %d, {"sg_version": version})\n' % published_file_id
        nk += 'os.remove("%s")\n' % script_path

        # print(nk)
        # 스크립트 삭제

        # 스크립트 파일 생성
        with open(script_path, 'w') as f:
            f.write(nk)

        # 실행할 명령어 리턴
        command = ['rez-env', 'shotgunapi3', '--', 'python3.7', script_path]
        # print(command)
        return command

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

