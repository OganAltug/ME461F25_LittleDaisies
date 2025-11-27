```
                       ┌───────────────────U───────────────────┐
      VCC / 5V       ---|● 1  EN1                     VCC1 16 ●|--- VBUS (5V)
      Pico GP0 (IN1) ---|● 2  IN1                     IN4  15 ●|--- Pico GP16 (IN4)
  [Left LEDs/Motor]  ---|● 3  OUT1                    OUT4 14 ●|--- [Right LEDs/Motor]
             GND     ---|● 4  GND                     GND  13 ●|------- GND
             GND     ---|● 5  GND                     GND  12 ●|------- GND
  [Left LEDs/Motor]  ---|● 6  OUT2                    OUT3 11 ●|--- [Right LEDs/Motor]
      Pico GP1 (IN2) ---|● 7  IN2                     IN3  10 ●|--- Pico GP17 (IN3)
      VBUS / Battery ---|● 8  VCC2 (Power)            EN2   9 ●|--- VCC / 5V
                        └───────────────────────────────────────┘
```

```
	                   ┌────────────────────────────────────────────┐
     L293D IN1 (Left)  <---|● GP0                            VBUS (5V) ●|--- L293D Pin 16
     L293D IN2 (Left)  <---|● GP1                            VSYS      ●|--- L293D Pin 8
                           |● GND                            GND       ●|--- Common Ground
       Button FORWARD  --->|● GP2                            GP28      ●|
      Button BACKWARD  --->|● GP3                            GP27      ●|
                           |● GP4                            GP26      ●|
                           |● GP5                            RUN       ●|
                           |● GND                            GP22      ●|
                           |● GP6                            GND       ●|
                           |● GP7                            GP21      ●|
                           |● GP8                            GP20      ●|
                           |● GP9                            GP19      ●|
                           |● GP10                           GP18      ●|
                           |● GP11                           GP17      ●|---> L293D IN3 (Right)
                           |● GP12                           GP16      ●|---> L293D IN4 (Right)
                           |● GP13                           GP15      ●|
                           |● GP14                           GND       ●|
                           └────────────────────────────────────────────┘
```
