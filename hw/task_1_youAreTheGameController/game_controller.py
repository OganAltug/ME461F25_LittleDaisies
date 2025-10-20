# !/usr/bin/env python3
# !/usr/bin/env python3
import rclpy
from rclpy.node import Node
from example_interfaces.msg import Int64
from geometry_msgs.msg import Twist

import numpy as np
import pyautogui    
    
class GameControllerNode(Node): # MODIFY NAME
    def __init__(self):
        super().__init__("game_controller") # MODIFY NAME
        self.sub_ = self.create_subscription(Int64, "hand_gesture", self.sub_callback, 10)
        self.coords_sub_ = self.create_subscription(Twist, "hand_coords", self.coords_sub_callback, 10)
        self.space_pressed = False
        self.arrow_pressed = False
        self.coords = np.zeros(2)
        self.pre_coords = np.zeros(2)
        self.Kp = 10

    def sub_callback(self, msg: Int64):
        if msg.data == 0:
            if self.arrow_pressed:
                pyautogui.keyUp("down")
                self.arrow_pressed = False
        if msg.data == 1:
            pyautogui.press("space")
            self.get_logger().info("Pressed space")
        if msg.data == 2:
            if not self.arrow_pressed:
                pyautogui.keyDown("down")
                self.get_logger().info("Pressing down")
                self.arrow_pressed = True
        if msg.data == 3:
            #pyautogui.press("enter")
            pyautogui.click() 
            self.get_logger().info("Clicking")
            pass

    def coords_sub_callback(self, msg: Twist):
        #image size x:960 y:540
        self.coords = [msg.linear.x, msg.linear.y]
        if 960 > self.coords[0] >= 660:
            pyautogui.press("right")
            self.get_logger().info("Pressed Right")
        elif 300 > self.coords[0] >= 0:
            pyautogui.press("left")
            self.get_logger().info("Pressed Left")
        elif (660 > self.coords[0] > 300) & (200 > self.coords[1] > 0):
            pyautogui.press("up")
            self.get_logger().info("Pressed Up")
        elif (660 > self.coords[0] > 300) & (540 > self.coords[1] > 340):
            pyautogui.press("down")
            self.get_logger().info("Pressed Down")
        else:
            pass
        
    
def main(args=None):
    rclpy.init(args=args)
    node = GameControllerNode() # MODIFY NAME
    rclpy.spin(node)
    rclpy.shutdown()
    
    
if __name__ == "__main__":
    main()