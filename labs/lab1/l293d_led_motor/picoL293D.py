#              .';:cc;.
#            .,',;lol::c.
#            ;';lddddlclo
#            lcloxxoddodxdool:,.
#            cxdddxdodxdkOkkkkkkkd:.
#          .ldxkkOOOOkkOO000Okkxkkkkx:.
#        .lddxkkOkOOO0OOO0000Okxxxxkkkk:
#       'ooddkkkxxkO0000KK00Okxdoodxkkkko
#      .ooodxkkxxxOO000kkkO0KOxolooxkkxxkl
#      lolodxkkxxkOx,.      .lkdolodkkxxxO.
#      doloodxkkkOk           ....   .,cxO;
#      ddoodddxkkkk:         ,oxxxkOdc'..o'
#      :kdddxxxxd,  ,lolccldxxxkkOOOkkkko,
#       lOkxkkk;  :xkkkkkkkkOOO000OOkkOOk.
#        ;00Ok' 'O000OO0000000000OOOO0Od.
#         .l0l.;OOO000000OOOOOO000000x,
#            .'OKKKK00000000000000kc.
#               .:ox0KKKKKKK0kdc,.
#                      ...
#
# Author: peppe8o
# Blog: https://peppe8o.com
# Date: Jun 8th, 2021
# Version: 1.0

from machine import Pin, PWM
from time import sleep

pwmPIN=16
cwPin=14 
acwPin=15

def motorMove(speed,direction,speedGP,cwGP,acwGP):
  if speed > 100: speed=100
  if speed < 0: speed=0
  Speed = PWM(Pin(speedGP))
  Speed.freq(50)
  cw = Pin(cwGP, Pin.OUT)
  acw = Pin(acwGP, Pin.OUT)
  Speed.duty_u16(int(speed/100*65536))
  if direction < 0:
      cw.value(0)
      acw.value(1)
  if direction == 0:
      cw.value(0)
      acw.value(0)
  if direction > 0:
      cw.value(1)
      acw.value(0)

# main program
motorMove(100,1,pwmPIN,cwPin,acwPin)
sleep(5)
motorMove(100,0,pwmPIN,cwPin,acwPin)
  
   