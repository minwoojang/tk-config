#coding:utf8
# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
App Launch Hook

This hook is executed to launch the applications.
"""

import os
import re
import sys
import subprocess
import tank



class AppLaunch(tank.Hook):
    """
    Hook to run an application.
    """
    
    def execute(self, app_path, app_args, version, engine_name, **kwargs):
        
        """
        The execute functon of the hook will be called to start the required application
        
        :param app_path: (str) The path of the application executable
        :param app_args: (str) Any arguments the application may require
        :param version: (str) version of the application being run if set in the
            "versions" settings of the Launcher instance, otherwise None
        :param engine_name (str) The name of the engine associated with the
            software about to be launched.

        :returns: (dict) The two valid keys are 'command' (str) and 'return_code' (int).
        """
        app_name = engine_name.split("-")[-1] #tk-nuke to nuke
        context = self.tank.context_from_path(self.tank.project_path)
        project = context.project
        self.sg = self.tank.shotgun
        packages = self.get_rez_packages(app_name,version,project)
        try:
            import rez as _
        except ImportError:
            rez_path = self.get_rez_module_root()
            if isinstance(rez_path, bytes):
                rez_path = rez_path.decode('utf-8')
            elif isinstance(rez_path, str):
                pass
            sys.path.append(rez_path)
        
        from rez import resolved_context 
        
        command = 'start "App" "{path}" {args}'.format(path=app_path, args=app_args)
        
        if not packages:
            self.logger.debug('No rez packages were found. The default boot, instead.')
            return_code = os.system(command)
            return {'command': command, 'return_code': return_code}
        else:
            context = resolved_context.ResolvedContext(packages)
            proc = context.execute_shell(
                command = command,
                stdin = False,
                block = False
            )
            # with open("D:\\command2.txt","w") as file:
            #     file.write(str(proc))
            return_code = 0
            return {'command': command,'return_code': return_code,}

    def get_rez_packages(self,app_name,version,project):
        
        filter_dict = [['code','is',app_name.title()]
                        #['projects','in',project]
                        ]
        packages = self.sg.find("Software",filter_dict,['sg_rez'])

        if packages: 
            packages =  packages[0]['sg_rez']

        if packages:
            packages = [ x for x in packages.split(",")] 
        else:
            packages = None
        
        return packages
        
    def get_rez_module_root(self):

        command = 'rez-env rez -- echo %REZ_REZ_ROOT%'
        module_path, stderr = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).communicate()

        module_path = module_path.strip()

        if not stderr and module_path:
            return module_path

        return ''





