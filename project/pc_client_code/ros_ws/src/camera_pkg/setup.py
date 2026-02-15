from setuptools import find_packages, setup

package_name = 'camera_pkg'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ogan',
    maintainer_email='oganaltug@hotmail.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            "camera_publisher_node = camera_pkg.camera_publisher:main",
            "async_camera_subscriber = camera_pkg.camera_subscriber_async:main",
            "sync_camera_subscriber = camera_pkg.camera_subscriber_sync:main",
            "calibrator_node = camera_pkg.ros_calibration:main",
            "AAAA = camera_pkg.sebastian_vettel:main"
        ],
    },
)
