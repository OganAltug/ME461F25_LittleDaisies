import sys
if sys.prefix == '/usr':
    sys.real_prefix = sys.prefix
    sys.prefix = sys.exec_prefix = '/home/ogan/ME461F25_LittleDaisies/project/ros_ws/install/camera_pkg'
