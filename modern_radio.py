"""Christmas Radio - moderne seizoensinterface met live radio-audio.

De bestaande, bewezen audio-engine blijft ongewijzigd:
  radio_engine.py + radio_v6.py (uit de Christmas Radio V6-repository).
De native connector wordt met dezelfde gepinde bron gebouwd als PTT Direct.
De gebruikersinterface vermeldt uitsluitend radiospecifieke termen.
"""

import math
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QRectF, QSettings, QPointF, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap, QPainterPath, QLinearGradient
from PySide6.QtWidgets import QApplication, QWidget, QInputDialog, QMessageBox

from radio_v6 import RadioEngine


GROUPS = ('TG-103 Voorburg', 'TG-108 Heerlen')
THEMES = ('kerst', 'winter', 'zomer', 'space')
THEME_TITLES = ('Kerst Thema', 'Winter Thema', 'Zomer Thema', 'Space Thema')
PALETTES = {
    'kerst': dict(accent='#26e874', accent2='#ff455f', panel='#07182a', light='#a3d7ff', title='#ff6477'),
    'winter': dict(accent='#6ee8ff', accent2='#008ef5', panel='#07192b', light='#b5ecff', title='#a8f3ff'),
    'zomer': dict(accent='#f9b63c', accent2='#02d7e6', panel='#0a2330', light='#fbe6a0', title='#ffd16a'),
    'space': dict(accent='#42b7ff', accent2='#b076ff', panel='#090d2a', light='#b8ceff', title='#8edbff'),
}


class SeasonsRadio(QWidget):
    W, H = 1648, 930

    def __init__(self):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle('Christmas Radio')
        self.setMinimumSize(1050, 610)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.settings = QSettings('ChristmasRadio', 'Seizoenen')
        self.theme = str(self.settings.value('theme', 'kerst'))
        if self.theme not in THEMES:
            self.theme = 'kerst'
        self.selected_theme = self.theme
        self.group = str(self.settings.value('group', GROUPS[0]))
        if self.group not in GROUPS:
            self.group = GROUPS[0]
        self.selected_group = self.group
        self.nickname = str(self.settings.value('nickname', 'Gast'))[:28]
        self.volume = self.number('volume', 80)
        self.sensitivity = self.number('sensitivity', 40)
        self.muted = self.settings.value('muted', False, type=bool)
        self.vox = self.settings.value('vox', False, type=bool)
        self.screen = 'kanalen'
        self.status = 'OFFLINE'
        self.message = 'Kies een TG-groep en klik op Verbinden'
        self.channels = []
        self.members = []
        self.channel_id = None
        self.channel_name = 'Nog geen kanaal'
        self.channel_scroll = 0
        self.rx = False
        self.ptt = False
        self.mic = 0
        self.mic_ready = False
        self.chat_messages = []
        self.hits = []
        self.drag = None
        self._mouse_ptt = False
        self._space_ptt = False

        self.radio = RadioEngine(self)
        self.radio.event.connect(self.on_radio_event)
        self.radio.set_options(self.muted, self.vox, self.sensitivity)
        self.radio.set_volume(self.volume)
        stored_device = str(self.settings.value('mic_device', '')).strip()
        try:
            self.radio.input_device = int(stored_device) if stored_device else None
        except ValueError:
            self.radio.input_device = None

        folder = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
        self.art = {key: QPixmap(str(folder / 'skins' / f'{key}.jpg')) for key in THEMES}

        display = QApplication.primaryScreen()
        if display:
            bounds = display.availableGeometry()
            factor = min(1.0, (bounds.width() - 24) / self.W, (bounds.height() - 30) / self.H)
            self.resize(round(self.W * factor), round(self.H * factor))
            self.move(bounds.center() - self.rect().center())
        else:
            self.resize(1236, 697)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(1000)

    def number(self, key, fallback):
        try:
            return max(0, min(100, int(self.settings.value(key, fallback))))
        except (TypeError, ValueError):
            return fallback

    def save(self):
        for key in ('theme', 'group', 'nickname', 'volume', 'sensitivity', 'muted', 'vox'):
            self.settings.setValue(key, getattr(self, key))

    def transform(self):
        scale = min(self.width() / self.W, self.height() / self.H)
        return scale, (self.width() - self.W * scale) / 2, (self.height() - self.H * scale) / 2

    def coords(self, pos):
        s, ox, oy = self.transform()
        return (pos.x() - ox) / s, (pos.y() - oy) / s

    @staticmethod
    def rgba(value, alpha=None):
        color = QColor(value)
        if alpha is not None:
            color.setAlpha(alpha)
        return color

    @staticmethod
    def rect(p, x, y, w, h, top, bottom=None, border=None, radius=14, line=1.5):
        # Glass-style rounded panel.
        path = QPainterPath()
        path.addRoundedRect(QRectF(x, y, w, h), radius, radius)
        if bottom:
            grad = QLinearGradient(x, y, x, y + h)
            grad.setColorAt(0, QColor(top))
            grad.setColorAt(1, QColor(bottom))
            p.fillPath(path, grad)
        else:
            p.fillPath(path, QColor(top))
        if border:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(border), line))
            p.drawPath(path)

    @staticmethod
    def text(p, txt, x, y, w, h, size=18, color='#ffffff', bold=False, align=None, italic=False):
        if align is None:
            align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        font = QFont('Segoe UI', size)
        font.setBold(bold)
        font.setItalic(italic)
        p.setFont(font)
        p.setPen(QColor(color))
        p.drawText(QRectF(x, y, w, h), align, str(txt))

    def hit(self, name, rect):
        self.hits.append((name, rect))

    def label_panel(self, p, text, x, y, w, h, accent=None):
        t = PALETTES[self.theme]
        self.rect(p, x, y, w, h, t['panel'], '#030c19', '#3c6685', 16)
        self.text(p, text, x+19, y+10, w-30, 41, 19, '#f5faff', True)
        p.setPen(QPen(QColor(accent or t['light']), 1.5))
        p.drawLine(int(x+17), int(y+55), int(x+w-17), int(y+55))

    def click_button(self, p, key, label, x, y, w, h, selected=False, danger=False, fontsize=17):
        t = PALETTES[self.theme]
        if danger:
            top, bottom, edge = ('#8f1f36', '#310a15', '#ff5269')
        elif selected:
            top, bottom, edge = ('#168247', '#07532d', t['accent'])
        else:
            top, bottom, edge = ('#26445e', '#0e223a', '#597fa7')
        self.rect(p,x,y,w,h,top,bottom,edge,10)
        self.text(p,label,x+7,y,w-14,h,fontsize,'#f4fbff',True,Qt.AlignmentFlag.AlignCenter)
        self.hit(key,(x,y,w,h))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.fillRect(self.rect(),QColor('#020914'))
        s,ox,oy=self.transform(); p.translate(ox,oy);p.scale(s,s)
        self.hits=[]
        t=PALETTES[self.theme]
        self.rect(p,0,0,self.W,self.H,'#020c1b','#02101c',None,0)

        # Thematische header, zonder statische tekst of nepgebruikers.
        if not self.art[self.theme].isNull():
            p.drawPixmap(QRectF(0,0,1295,235),self.art[self.theme],QRectF(self.art[self.theme].rect()))
        self.rect(p,0,212,1297,28,'#071326',None,None,0)
        self.text(p,'Christmas Radio',45,24,555,83,55,t['title'],True,italic=True)
        self.text(p,('KERST EDITIE' if self.theme=='kerst' else 'RADIO • SEIZOENENTHEMA'),49,104,430,25,16,'#dce9f7',True)
        self.text(p,'Dezelfde radio. Vier verschillende werelden.',49,143,500,34,18,'#b8d6ec')

        # Vensterknoppen.
        for key,symbol,x in [('min','−',1515),('max','□',1560),('close','×',1605)]:
            self.rect(p,x,11,36,33,'#10243b','#07172a','#57728e',7)
            self.text(p,symbol,x,10,36,34,22,'#e7f6ff',True,Qt.AlignmentFlag.AlignCenter)
            self.hit(key,(x,11,36,33))

        # De vijf navigatieknoppen uit het voorbeeld.
        nav=[('kanalen','KANALEN'),('gebruikers','GEBRUIKERS'),('groepen','TG-GROEPEN'),('instellingen','INSTELLINGEN'),('thema','THEMA')]
        for i,(key,txt) in enumerate(nav):
            x=632+i*131
            selected=self.screen==key
            self.rect(p,x,128,125,84,'#5f1a2e' if selected else '#183650', '#310c18' if selected else '#091b31', t['accent2'] if selected else '#41627d',14)
            ico={'kanalen':'◉','gebruikers':'●●','groepen':'◎','instellingen':'⚙','thema':'◈'}[key]
            self.text(p,ico,x,135,125,35,24,'#f3faff',True,Qt.AlignmentFlag.AlignCenter)
            self.text(p,txt,x+2,171,121,33,13,'#f3faff',True,Qt.AlignmentFlag.AlignCenter)
            self.hit('nav:'+key,(x,128,125,84))

        # Compacte 4-koloms indeling.
        self.draw_connection(p)
        self.draw_channels(p)
        self.draw_members(p)
        self.draw_groups_audio(p)
        self.draw_ptt(p)
        self.draw_themes(p)
        self.draw_footer(p)
        if self.screen=='instellingen':
            self.draw_settings(p)
        p.end()

    def draw_connection(self,p):
        x,y,w,h=20,240,316,432
        self.label_panel(p,'◉  Verbinden met radio',x,y,w,h)
        self.text(p,'Kies je TG-groep',x+20,y+67,w-40,29,16,'#a5c6d9')
        for i,group in enumerate(GROUPS):
            yy=y+104+i*49
            chosen=self.selected_group==group
            self.rect(p,x+17,yy,w-34,43,'#0d4c35' if chosen else '#081b2e',None,'#37ce80' if chosen else '#466684',8)
            self.text(p,'◉' if chosen else '○',x+26,yy+3,29,37,20,'#48f391' if chosen else '#c8d6e5')
            self.text(p,group,x+58,yy+1,w-76,41,17,'#e7f5f5',chosen)
            self.hit('select-group:'+group,(x+17,yy,w-34,43))
        self.click_button(p,'connect','VERBINDEN',x+17,y+208,w-34,47,True)
        self.click_button(p,'disconnect','VERBREKEN',x+17,y+262,w-34,42)
        self.rect(p,x+12,y+319,w-24,103,'#0b2336','#071827','#3f7192',12)
        color='#6fff93' if self.radio.connected else '#f3c77a' if self.radio.connecting else '#ff8089'
        self.text(p,'●  '+('Verbonden' if self.radio.connected else 'Verbinding maken' if self.radio.connecting else 'Niet verbonden'),x+20,y+330,w-38,29,18,color,True)
        self.text(p,'TG: '+self.group,x+20,y+365,w-38,22,14,'#d3eaf1')
        self.text(p,self.nickname[:23]+'  •  '+str(len(self.members))+' leden',x+20,y+390,w-38,23,13,'#b9d0db')

    def draw_channels(self,p):
        x,y,w,h=346,240,315,432
        self.label_panel(p,f'☷  Kanalen ({len(self.channels)})',x,y,w,h)
        if not self.radio.connected:
            self.text(p,'Verbind om kanalen te zien',x+22,y+125,w-44,43,16,'#bed8e5')
            self.text(p,'Hier verschijnen alle echte',x+22,y+167,w-44,28,14,'#7faabb')
            self.text(p,'kanalen van jouw radiogroep.',x+22,y+196,w-44,28,14,'#7faabb')
            return
        if not self.channels:
            self.text(p,'Kanaallijst wordt geladen...',x+18,y+115,w-36,42,16,'#d0eafa')
            return
        visible=9
        self.channel_scroll=max(0,min(self.channel_scroll,max(0,len(self.channels)-visible)))
        for i,c in enumerate(self.channels[self.channel_scroll:self.channel_scroll+visible]):
            yy=y+68+i*36
            current=str(c.get('id'))==str(self.channel_id)
            if current:
                self.rect(p,x+13,yy,w-26,34,'#0f733f','#07542f',PALETTES[self.theme]['accent'],6)
            self.text(p,'◉' if current else '○',x+24,yy,w=27,h=33,size=20,color=('#50ff93' if current else '#9badca'))
            name=str(c.get('name','Kanaal')).replace('\n',' ')[:32]
            self.text(p,name,x+58,yy,w-73,33,15,'#f2f9ff',current)
            self.hit('channel:'+str(c.get('id')),(x+13,yy,w-26,34))
        if len(self.channels)>visible:
            self.text(p,f'{self.channel_scroll+1}-{min(len(self.channels),self.channel_scroll+visible)} / {len(self.channels)}  •  scroll',x+20,y+390,w-35,25,12,'#b9d4e2')
            self.hit('scroll-channels',(x+13,y+66,w-26,351))

    def draw_members(self,p):
        x,y,w,h=670,240,311,432
        self.label_panel(p,f'♟  Gebruikers ({len(self.members)})',x,y,w,h)
        for i,c in enumerate(self.members[:8]):
            yy=y+69+i*40
            talking=bool(c.get('talking'))
            if talking:
                self.rect(p,x+13,yy,w-26,37,'#12553f','#0b3129','#25de76',8)
            self.text(p,'●',x+20,yy,26,35,22,'#42f47b' if talking else '#638fa6')
            self.text(p,str(c.get('name',''))[:26],x+52,yy,w-83,35,15,'#f2fbfd',talking)
            if talking:
                self.text(p,'♫',x+w-35,yy,24,35,18,'#6dffad',True)
        if not self.members:
            self.text(p,'Nog geen gebruikers zichtbaar',x+17,y+116,w-30,34,16,'#b5d2e4')
        self.click_button(p,'chat','CHATBERICHT',x+18,y+373,w-36,40,False,False,14)

    def draw_groups_audio(self,p):
        x,y,w=991,240,295
        self.label_panel(p,'◎  TG-Groepen',x,y,w,210)
        for i,group in enumerate(GROUPS):
            yy=y+64+i*42
            selected=group==self.selected_group
            active=group==self.group and self.radio.connected
            self.rect(p,x+13,yy,w-26,38,'#125c34' if active else '#10283b',None,'#48db81' if selected else '#456783',8)
            self.text(p,'◉' if selected else '○',x+22,yy+1,28,34,20,'#51ff8c' if selected else '#a1b5c8')
            self.text(p,group,x+52,yy+1,w-66,34,15,'#eef8fb',selected)
            self.hit('select-group:'+group,(x+13,yy,w-26,38))
        self.click_button(p,'switch','SCHAKELEN NAAR GROEP',x+14,y+156,w-28,43,True,fontsize=14)

        self.label_panel(p,'♩  Microfoon & Audio',x,460,w,212)
        self.click_button(p,'mic','MICROFOON KIEZEN',x+15,519,w-30,45,fontsize=15)
        self.text(p,'Mic',x+15,569,39,23,14,'#bdd7e4')
        self.draw_bars(p,x+57,573,215,18,self.mic/100,14)
        self.text(p,'VOL',x+15,603,36,28,13,'#bdd7e4')
        self.rect(p,x+61,615,193,7,'#244359',None,None,4)
        ratio=self.volume/100
        self.rect(p,x+61,615,193*ratio,7,PALETTES[self.theme]['accent'],None,None,4)
        p.setBrush(QColor('#f4faff'));p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(x+61+193*ratio,619),9,9)
        self.hit('volume',(x+51,602,222,35))
        self.text(p,f'{self.volume}%',x+247,602,43,28,13,'#e7faff',True)
        self.text(p,'MIC OK' if self.mic_ready else 'Microfoon niet geopend',x+17,642,w-34,24,12,'#7af6a2' if self.mic_ready else '#f0b37a')

    def draw_bars(self,p,x,y,w,h,level,n=14):
        count=min(n,max(0,round(level*n)))
        step=w/n
        for i in range(n):
            color='#35ef65' if i<int(n*.62) else '#f0d04b' if i<int(n*.83) else '#ff6c65'
            self.rect(p,x+i*step,y+(3 if i<n//3 else 0),step-4,h-(3 if i<n//3 else 0),color if i<count else '#233f50',None,None,2)

    def draw_ptt(self,p):
        t=PALETTES[self.theme]
        self.rect(p,20,682,1266,159,'#091d30','#031323','#4d7798',17)
        # S-meter: actual activity, no made-up values.
        self.rect(p,35,697,316,131,'#060b14','#101e2a','#6f91aa',14)
        cx,cy=190,810
        active=self.mic if self.radio.transmitting else (62 if self.rx else 0)
        for i in range(18):
            angle=math.radians(200+i*(140/17))
            r1,r2=79,112
            color='#43ef81' if i<9 else '#f5ce5c' if i<14 else '#ff5e61'
            if i>=max(1,round(active/100*18)):
                color='#294055'
            p.setPen(QPen(QColor(color),5))
            p.drawLine(int(cx+r1*math.cos(angle)),int(cy+r1*math.sin(angle)),int(cx+r2*math.cos(angle)),int(cy+r2*math.sin(angle)))
        self.text(p,'SIGNAAL',90,780,200,43,18,'#e8f7fd',True,Qt.AlignmentFlag.AlignCenter)
        self.rect(p,362,697,224,131,'#050f18','#10253a','#5684a3',13)
        self.text(p,'MODULATIE',380,704,192,24,14,'#c6dcea',True,Qt.AlignmentFlag.AlignCenter)
        self.draw_bars(p,384,746,180,52,max(self.mic,15 if self.rx else 0)/100,10)
        self.click_button(p,'ptt','●  TALK',609,707,368,112,True,True,35)
        rx_active=self.radio.connected and self.rx
        tx_active=self.radio.connected and self.radio.transmitting
        self.click_button(p,'indicator-rx','●  RX',1000,726,124,65,rx_active,False,23)
        self.click_button(p,'indicator-tx','●  TX',1138,726,124,65,tx_active,False,23)
        if self.radio.connected and not self.muted:
            self.text(p,'Houd TALK of SPATIE ingedrukt om te praten',602,818,375,18,12,'#a6c9df',False,Qt.AlignmentFlag.AlignCenter)
        elif self.muted:
            self.text(p,'MUTE staat aan — microfoon uit',602,818,375,18,12,'#ffb6b6',False,Qt.AlignmentFlag.AlignCenter)
        else:
            self.text(p,'Verbind eerst met een radiogroep',602,818,375,18,12,'#a6c9df',False,Qt.AlignmentFlag.AlignCenter)

    def draw_themes(self,p):
        t=PALETTES[self.theme]
        self.rect(p,1306,53,331,787,'#071e34','#031321','#5986a8',23,2)
        self.text(p,'◈  Thema Kiezen',1322,73,300,52,27,'#f7fafe',True,Qt.AlignmentFlag.AlignCenter)
        for i,key in enumerate(THEMES):
            y=151+i*110
            selected=self.selected_theme==key
            active=self.theme==key
            self.rect(p,1325,y,291,101,'#0b3b2f' if selected else '#0a263b','#061a2c',t['accent'] if selected else '#325e7c',17,2)
            # Thumbnail is the actual background of the selected theme.
            img=self.art[key]
            if not img.isNull():
                p.save()
                path=QPainterPath();path.addRoundedRect(QRectF(1335,y+11,97,79),10,10)
                p.setClipPath(path)
                p.drawPixmap(QRectF(1335,y+11,97,79),img,QRectF(0,0,290,235))
                p.restore()
            self.text(p,THEME_TITLES[i],1440,y+24,145,49,17,'#f2f9ff',selected)
            self.text(p,'◉' if selected else '○',1579,y+23,29,49,25,t['accent'] if selected else '#8aabc8',True)
            self.hit('theme:'+key,(1325,y,291,101))
        self.click_button(p,'apply-theme','✓  THEMA TOEPASSEN',1340,609,260,65,True,fontsize=20)
        self.text(p,'Wissel op elk moment, ook',1340,706,270,28,15,'#bdd7e4',False,Qt.AlignmentFlag.AlignCenter)
        self.text(p,'terwijl de radio verbonden is.',1340,735,270,28,15,'#bdd7e4',False,Qt.AlignmentFlag.AlignCenter)
        self.text(p,'Het radiogeluid blijft actief.',1340,773,270,25,13,t['accent'],False,Qt.AlignmentFlag.AlignCenter)

    def draw_footer(self,p):
        t=PALETTES[self.theme]
        self.rect(p,12,850,1625,68,'#091b2e','#03111d','#4b7191',19)
        color='#4bf77b' if self.radio.connected else '#ffc15d' if self.radio.connecting else '#f2757b'
        self.text(p,'●',39,861,38,43,27,color,True)
        label='Verbonden' if self.radio.connected else 'Verbinden...' if self.radio.connecting else 'Offline'
        self.text(p,label,83,859,173,46,20,'#ebf6fd',True)
        self.text(p,'│',257,863,12,39,21,'#6888a5')
        self.text(p,self.group,280,860,245,45,18,'#d5f0fd')
        self.text(p,'│',534,863,12,39,21,'#6888a5')
        self.text(p,'Kanaal: '+self.channel_name[:25],555,860,360,45,18,'#e0eef8')
        self.text(p,'VOL',1003,861,48,43,15,'#c5d8e5')
        self.rect(p,1057,880,214,6,'#25495a',None,None,3)
        self.rect(p,1057,880,214*self.volume/100,6,t['accent'],None,None,3)
        self.hit('footer-volume',(1042,860,245,45))
        self.text(p,str(self.volume)+'%',1285,862,75,40,19,'#f7faff',True)
        self.text(p,datetime.now().strftime('%H:%M'),1471,860,135,43,24,'#f5faff',True,Qt.AlignmentFlag.AlignCenter)

    def draw_settings(self,p):
        t=PALETTES[self.theme]
        self.rect(p,382,273,881,366,'#0b2944','#031623',t['accent'],19,2)
        self.text(p,'INSTELLINGEN',404,280,790,48,29,'#f7fbff',True)
        self.click_button(p,'nickname','Gebruiker: '+self.nickname[:20]+'  (wijzigen)',408,344,450,50,fontsize=17)
        self.click_button(p,'mute','Microfoon dempen: '+('AAN' if self.muted else 'UIT'),408,407,450,47,self.muted,fontsize=16)
        self.click_button(p,'vox','VOX spraakactivatie: '+('AAN' if self.vox else 'UIT'),408,463,450,47,self.vox,fontsize=16)
        self.click_button(p,'sensitivity','VOX gevoeligheid: '+str(self.sensitivity)+'%',408,519,450,47,fontsize=16)
        self.click_button(p,'close-settings','✓  SLUITEN',891,534,331,51,True,fontsize=17)
        self.text(p,'De verbinding blijft actief als je instellingen wijzigt.',890,401,310,61,16,'#bde2f5')

    def on_radio_event(self, data):
        if data.get('generation')!=self.radio._generation:
            return
        kind=data.get('type')
        if kind=='connecting':
            self.status='VERBINDEN';self.message='Verbinding wordt gemaakt...'
        elif kind=='connected':
            self.status='ONLINE';self.message='Verbonden met '+self.group
            ident=data.get('identity','')
            if ident:self.settings.setValue('identity_'+self.group,ident)
            if self.radio._input is None and self.radio._output is None:
                self.radio.start_audio()
        elif kind=='disconnected':
            self.status='OFFLINE';self.message='Verbinding verbroken';self.members=[];self.channels=[]
            self.channel_id=None;self.channel_name='Nog geen kanaal';self.mic_ready=False;self.rx=False
            self.stop_ptt()
        elif kind=='channels_list':
            self.channels=[c for c in data.get('channels',[]) if isinstance(c,dict) and c.get('id') is not None]
            self.channel_id=data.get('current_id')
            target=next((x for x in self.channels if str(x.get('id'))==str(self.channel_id)),None)
            if target:self.channel_name=str(target.get('name','Kanaal'))
            self.members=self.radio.members()
        elif kind in ('members','talkers'):
            self.members=self.radio.members()
            if kind=='talkers':self.rx=bool(data.get('rx'))
            self.channel_id=self.radio._channel_id
            target=next((x for x in self.radio._channels if str(x.get('id'))==str(self.channel_id)),None)
            if target:self.channel_name=str(target.get('name','Kanaal'))
        elif kind=='mic_ready':
            self.mic_ready=True
        elif kind=='mic_level':
            self.mic=int(data.get('value',0))
        elif kind=='audio_error':
            self.message=str(data.get('message','Audioprobleem'))
            if 'microfoon' in self.message.lower():self.mic_ready=False
        elif kind=='error':
            self.message='Radioactie of verbinding mislukt'
        elif kind=='chat':
            name=str(data.get('from_user',''))[:22];msg=str(data.get('message',''))[:120]
            self.chat_messages.append(f'{name}: {msg}')
            self.chat_messages=self.chat_messages[-30:]
        self.update()

    def connect(self):
        if self.radio.connected or self.radio.connecting:
            self.radio.stop()
        self.group=self.selected_group
        if not self.nickname.strip() or self.nickname.lower()=='gast':
            name,ok=QInputDialog.getText(self,'Christmas Radio','Jouw radionaam:',text='')
            if not ok or not name.strip():return
            self.nickname=name.strip()[:28]
        self.save()
        self.channel_id=None;self.channel_name='Kanalen laden...';self.members=[];self.channels=[];self.mic=0;self.mic_ready=False
        self.radio.set_options(self.muted,self.vox,self.sensitivity)
        self.radio.set_volume(self.volume)
        self.radio.request_channel(14)
        identity=str(self.settings.value('identity_'+self.group,''))
        self.radio.start(self.group,self.nickname,identity)

    def disconnect(self):
        self.stop_ptt()
        self.radio.stop()
        self.status='OFFLINE';self.members=[];self.channels=[];self.channel_name='Nog geen kanaal'
        self.update()

    def switch_group(self):
        if self.selected_group!=self.group or not self.radio.connected:
            self.connect()

    def stop_ptt(self):
        self.ptt=False;self._space_ptt=False;self._mouse_ptt=False
        self.radio.set_ptt(False)
        self.update()

    def update_ptt(self):
        self.ptt=(self._space_ptt or self._mouse_ptt) and self.radio.connected and not self.muted
        self.radio.set_ptt(self.ptt)
        self.update()

    def mic_dialog(self):
        try:
            import sounddevice as sd
            choices=[(i,str(d['name'])) for i,d in enumerate(sd.query_devices()) if d['max_input_channels']>0]
        except Exception:
            QMessageBox.warning(self,'Christmas Radio','Geen microfoonapparaten beschikbaar.')
            return
        if not choices:
            QMessageBox.warning(self,'Christmas Radio','Windows heeft geen microfoon gevonden.')
            return
        names=[f'{i}: {name}' for i,name in choices]
        idx=next((j for j,(i,_) in enumerate(choices) if i==self.radio.input_device),0)
        name,ok=QInputDialog.getItem(self,'Microfoon kiezen','Kies een opnameapparaat:',names,idx,False)
        if not ok:return
        device=choices[names.index(name)][0]
        self.radio.input_device=device
        self.settings.setValue('mic_device',device)
        if self.radio.connected:
            self.stop_ptt()
            stream=self.radio._input;self.radio._input=None
            if stream:
                try:stream.stop();stream.close()
                except Exception:pass
            self.radio.start_audio()
        self.update()

    def chat_dialog(self):
        if not self.radio.connected:
            QMessageBox.information(self,'Christmas Radio','Verbind eerst met een radiogroep.')
            return
        contents='\n'.join(self.chat_messages[-8:]) if self.chat_messages else 'Nog geen berichten.'
        msg,ok=QInputDialog.getText(self,'Kanaalchat',contents+'\n\nBericht typen:')
        if ok and msg.strip():
            self.radio.send_chat(msg.strip())
            self.chat_messages.append(self.nickname+': '+msg.strip()[:100]);self.update()

    def activate(self,key,x):
        if key=='connect':self.connect()
        elif key=='disconnect':self.disconnect()
        elif key=='switch':self.switch_group()
        elif key.startswith('select-group:'):
            self.selected_group=key.partition(':')[2]
            self.update()
        elif key.startswith('theme:'):
            self.selected_theme=key.partition(':')[2];self.screen='thema';self.update()
        elif key=='apply-theme':
            self.theme=self.selected_theme;self.save();self.update()
        elif key.startswith('nav:'):
            self.screen=key.partition(':')[2];self.update()
        elif key.startswith('channel:'):
            if self.radio.connected:self.radio.select_channel(key.partition(':')[2]);self.update()
        elif key in ('volume','footer-volume'):
            start,width=(1049,222) if key=='footer-volume' else (1052,206)
            self.volume=max(0,min(100,round((x-start)/width*100)))
            self.radio.set_volume(self.volume);self.save();self.update()
        elif key=='mic':self.mic_dialog()
        elif key=='chat':self.chat_dialog()
        elif key=='nickname':
            name,ok=QInputDialog.getText(self,'Radionaam','Naam:',text=self.nickname)
            if ok and name.strip():
                if self.radio.connected:self.disconnect()
                self.nickname=name.strip()[:28];self.save();self.update()
        elif key=='mute':
            self.muted=not self.muted
            if self.muted:self.stop_ptt()
            self.radio.set_options(self.muted,self.vox,self.sensitivity);self.save();self.update()
        elif key=='vox':
            self.vox=not self.vox;self.radio.set_options(self.muted,self.vox,self.sensitivity);self.save();self.update()
        elif key=='sensitivity':
            v,ok=QInputDialog.getInt(self,'VOX gevoeligheid','0 tot 100:',self.sensitivity,0,100)
            if ok:self.sensitivity=v;self.radio.set_options(self.muted,self.vox,self.sensitivity);self.save();self.update()
        elif key=='close-settings':self.screen='kanalen';self.update()
        elif key=='min':self.showMinimized()
        elif key=='max':self.showNormal() if self.isMaximized() else self.showMaximized()
        elif key=='close':self.close()

    def mousePressEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton:return
        x,y=self.coords(event.position())
        for key,(bx,by,bw,bh) in reversed(self.hits):
            if bx<=x<=bx+bw and by<=y<=by+bh:
                if key=='ptt':
                    self._mouse_ptt=True;self.update_ptt();return
                if key in ('indicator-rx','indicator-tx','scroll-channels'):
                    return
                # Prevent controls beneath settings overlay from firing.
                if self.screen=='instellingen' and key not in ('nickname','mute','vox','sensitivity','close-settings','min','max','close'):
                    if key.startswith('nav:'):
                        self.screen=key.partition(':')[2];self.update()
                    return
                self.activate(key,x);return
        if 0<=x<=600 and 0<=y<222:
            self.drag=event.globalPosition().toPoint()-self.frameGeometry().topLeft()

    def mouseMoveEvent(self,event):
        if self.drag is not None and event.buttons() & Qt.MouseButton.LeftButton:
            if not self.isMaximized():self.move(event.globalPosition().toPoint()-self.drag)
            return
        x,y=self.coords(event.position())
        hover=any(bx<=x<=bx+bw and by<=y<=by+bh for _,(bx,by,bw,bh) in self.hits)
        self.setCursor(Qt.CursorShape.PointingHandCursor if hover else Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            self.drag=None
            if self._mouse_ptt:
                self._mouse_ptt=False;self.update_ptt()

    def wheelEvent(self,event):
        x,y=self.coords(event.position())
        if 346<=x<=660 and 302<=y<=671:
            move=-3 if event.angleDelta().y()>0 else 3
            self.channel_scroll=max(0,min(max(0,len(self.channels)-9),self.channel_scroll+move))
            self.update();event.accept()
        else:super().wheelEvent(event)

    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_ptt=True;self.update_ptt();event.accept()
        elif event.key()==Qt.Key.Key_Escape and self.screen=='instellingen':
            self.screen='kanalen';self.update()
        else:super().keyPressEvent(event)

    def keyReleaseEvent(self,event):
        if event.key()==Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_ptt=False;self.update_ptt();event.accept()
        else:super().keyReleaseEvent(event)

    def focusOutEvent(self,event):
        self.stop_ptt();super().focusOutEvent(event)

    def closeEvent(self,event):
        self.stop_ptt();self.radio.stop();self.save();super().closeEvent(event)


def main():
    app=QApplication(sys.argv)
    app.setApplicationName('Christmas Radio')
    window=SeasonsRadio()
    window.show()
    return app.exec()


if __name__=='__main__':
    sys.exit(main())
