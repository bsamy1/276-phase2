import os
import sys

submodule_name = "user_service"
(parent_folder_path, current_dir) = os.path.split(os.path.dirname(__file__))
sys.path.append(os.path.join(parent_folder_path, submodule_name))
