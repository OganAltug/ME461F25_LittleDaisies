# ---------------------------------------------------------------
# pico_tetris_unified.py – Auto USB/Wi-Fi Tetris Server (Raspberry Pi Pico W)
# ---------------------------------------------------------------

import machine, time, sys, random, network, socket, ujson, select

# ---------------- CONFIG ----------------
WIFI_SSID = "YOUR_WIFI_SSID"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"
SERVER_PORT = 8080
DISPLAY_WIDTH, DISPLAY_HEIGHT = 16, 32
SPI_BUS, NUM_MATRICES = 0, 8
SPI_SCK_PIN, SPI_MOSI_PIN, SPI_CS_PIN = machine.Pin(10), machine.Pin(11), machine.Pin(9)
GAME_TICK_RATE = 0.5
PLAYER_1_COLOR, PLAYER_2_COLOR, STATIC_COLOR = 1, 2, 3
TETROMINOES = {
    'O': [(0,0),(1,0),(0,1),(1,1)],
    'I': [(0,1),(1,1),(2,1),(3,1)],
    'S': [(1,0),(2,0),(0,1),(1,1)],
    'Z': [(0,0),(1,0),(1,1),(2,1)],
    'L': [(0,1),(1,1),(2,1),(2,0)],
    'J': [(0,1),(1,1),(2,1),(0,0)],
    'T': [(1,1),(0,1),(2,1),(1,0)]
}
T_KEYS = list(TETROMINOES.keys())

# ---------------- DISPLAY ----------------
class MAX7219Display:
    def __init__(self, spi, cs_pin, n):
        self.spi, self.cs, self.n = spi, cs_pin, n
        self.cs.init(cs_pin.OUT, value=1)
        self.buf = bytearray(8*n)
        self._SCAN, self._DECODE, self._INTENSITY, self._SHUTDOWN, self._TEST = 0xB,0x9,0xA,0xC,0xF
        self.init()
    def _cmd(self,r,d):
        self.cs(0)
        for _ in range(self.n): self.spi.write(bytearray([r,d]))
        self.cs(1)
    def init(self):
        for r,d in [(self._SHUTDOWN,1),(self._TEST,0),(self._SCAN,7),(self._DECODE,0),(self._INTENSITY,7)]:
            self._cmd(r,d)
        self.clear(); self.show()
    def clear(self): self.buf[:] = b'\x00'*len(self.buf)
    def set_pixel(self,x,y,v):
        if not(0<=x<DISPLAY_WIDTH and 0<=y<DISPLAY_HEIGHT): return
        mx,my=x//8,y//8; idx=my*2+mx; off=idx*8+(y%8); b=1<<(7-(x%8))
        if v:self.buf[off]|=b
        else:self.buf[off]&=~b
    def show(self):
        for r in range(8):
            self.cs(0)
            for i in reversed(range(self.n)):
                o=i*8+r
                self.spi.write(bytearray([r+1,self.buf[o]]))
            self.cs(1)
    def text(self,t):
        self.clear()
        if t=="USB": self.set_pixel(2,2,1)
        elif t=="WIFI": self.set_pixel(1,1,1)
        elif t=="FAIL": [self.set_pixel(i,2,1) for i in range(4)]
        self.show()

# ---------------- GAME ----------------
class Tetris:
    def __init__(s):
        s.w,s.h=DISPLAY_WIDTH,DISPLAY_HEIGHT
        s.g=[[0]*s.w for _ in range(s.h)]
        s.score=0; s.over=False
        s.p1=s.P(s,PLAYER_1_COLOR,s.w//2-4)
        s.p2=s.P(s,PLAYER_2_COLOR,s.w//2+1)
        s.p1.n=s.rand(); s.p2.n=s.rand(); s.spawn()
    def rand(s):return random.choice(T_KEYS)
    def spawn(s):
        for p in [s.p1,s.p2]:
            p.spawn(p.n); p.n=s.rand()
        if not s.p1.valid() or not s.p2.valid(): s.over=True
    class P:
        def __init__(p,g,c,x): p.g,g.c,p.x0=g,c,x; p.s=[]; p.x=p.y=0; p.isp=False;p.k=''
        def spawn(p,k):p.k=k;p.s=TETROMINOES[k];p.x,p.y=p.x0,0;p.isp=False
        def valid(p,s=None,x=None,y=None):
            s=s or p.s;x=x or p.x;y=y or p.y
            for px,py in s:
                nx,ny=x+px,y+py
                if not(0<=nx<p.g.w and 0<=ny<p.g.h):return False
                if p.g.g[ny][nx]==STATIC_COLOR:return False
            return True
        def mv(p,dx,dy):
            if p.isp:return False
            if p.valid(x=p.x+dx,y=p.y+dy):p.x+=dx;p.y+=dy;return True
            return False
        def rot(p):
            if p.isp or p.k=='O':return
            c=p.s[1];n=[(-(py-c[1])+c[0],(px-c[0])+c[1]) for px,py in p.s]
            if p.valid(s=n):p.s=n
    def grav(s):
        if s.over:return
        if not s.p1.mv(0,1): s.place(s.p1)
        if not s.p2.mv(0,1): s.place(s.p2)
        if s.p1.isp and s.p2.isp:
            l=s.lines()
            if l: s.clear(l)
            else: s.spawn()
    def place(s,p):
        if p.isp:return
        p.isp=True
        for px,py in p.s:
            nx,ny=p.x+px,p.y+py
            if 0<=nx<s.w and 0<=ny<s.h:s.g[ny][nx]=STATIC_COLOR
    def lines(s):
        L=[y for y in range(s.h) if all(s.g[y][x]==STATIC_COLOR for x in range(s.w))]
        if L:s.score+=len(L)**2
        return L
    def clear(s,L):
        for y in L:del s.g[y];s.g.insert(0,[0]*s.w)
    def inp(s,n,a):
        if s.over:return
        p=s.p1 if n==1 else s.p2
        if p.isp:return
        if a=="left":p.mv(-1,0)
        elif a=="right":p.mv(1,0)
        elif a=="down":
            while p.mv(0,1):pass
            s.place(p)
        elif a=="rotate":p.rot()
    def state(s,pause=False):
        g=[r[:] for r in s.g]
        for p in [s.p1,s.p2]:
            if not p.isp:
                for px,py in p.s:
                    nx,ny=p.x+px,p.y+py
                    if 0<=nx<s.w and 0<=ny<s.h:g[ny][nx]=p.c
        flat=[c for r in g for c in r]
        return ujson.dumps({"grid":flat,"score":s.score,"p1_next":s.p1.n,"p2_next":s.p2.n,"game_over":s.over,"paused":pause})

# ---------------- CONNECTIONS ----------------
def usb_try():
    p=select.poll();p.register(sys.stdin,select.POLLIN)
    try:
        sys.stdout.write("USB_MODE_READY\n")
        t=time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(),t)<3000:
            if p.poll(0):
                sys.stdin.read(1)
                print("USB OK")
                return True
            time.sleep_ms(50)
        print("USB timeout")
        return False
    except: return False

def wifi_try(ssid,psk):
    wlan=network.WLAN(network.STA_IF);wlan.active(True)
    wlan.config(pm=0xa11140)
    wlan.connect(ssid,psk)
    for _ in range(10):
        if wlan.status()>=3: break
        time.sleep(1)
    if wlan.status()!=3:
        print("WiFi fail");return None
    ip=wlan.ifconfig()[0]
    s=socket.socket();s.bind(("0.0.0.0",SERVER_PORT));s.listen(1);s.setblocking(False)
    print("WiFi OK",ip);return s,ip

# ---------------- MAIN LOOP ----------------
def loop(d):
    g=Tetris();paused=False;lt=time.ticks_ms()
    mode="USB" if usb_try() else "WIFI"
    if mode=="WIFI":
        try:
            s,ip=wifi_try(WIFI_SSID,WIFI_PASSWORD)
            if not s: print("WiFi failed. Ask credentials.");return
            d.text("WIFI")
        except: print("WiFi crash");return
        c=None
    else: print("Running via USB")

    while True:
        if mode=="USB":
            if sys.stdin in select.select([sys.stdin],[],[],0)[0]:
                data=sys.stdin.read(1)
                if data=="p":paused=not paused
        else:
            if not c:c=accept(s)
        now=time.ticks_ms()
        if not paused and not g.over and time.ticks_diff(now,lt)>GAME_TICK_RATE*1000:
            lt=now;g.grav()
        js=g.state(paused)
        d.clear()
        for i,v in enumerate(ujson.loads(js)["grid"]):
            if v:d.set_pixel(i%DISPLAY_WIDTH,i//DISPLAY_WIDTH,1)
        d.show()
        time.sleep_ms(10)

# ---------------- START ----------------
def init_disp():
    try:
        spi=machine.SPI(SPI_BUS,sck=SPI_SCK_PIN,mosi=SPI_MOSI_PIN)
        return MAX7219Display(spi,SPI_CS_PIN,NUM_MATRICES)
    except:
        class D: pass
        return D()

def main():
    d=init_disp(); d.text("WAIT")
    while True:
        loop(d)

if __name__=="__main__":
    main()
