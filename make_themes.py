"""Maak zelf vier thema-illustraties, zonder externe downloads."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
import math, random

OUT = Path(__file__).resolve().parent / 'skins'
OUT.mkdir(exist_ok=True)
W, H = 1295, 235


def lerp(a,b,t): return round(a + (b-a)*t)
def gradient(top,bottom):
    im=Image.new('RGB',(W,H)); d=ImageDraw.Draw(im)
    for y in range(H):
        t=y/H
        d.line([(0,y),(W,y)],fill=tuple(lerp(top[i],bottom[i],t) for i in range(3)))
    return im

def light(im,x,y,r,color):
    overlay=Image.new('RGBA',(W,H)); d=ImageDraw.Draw(overlay)
    d.ellipse((x-r,y-r,x+r,y+r),fill=(*color,170))
    glow=overlay.filter(ImageFilter.GaussianBlur(r/2.5))
    im.alpha_composite(glow)

def triangles(d,x,y,h,color):
    width=h*.42
    d.polygon([(x,y-h),(x-width,y),(x+width,y)],fill=color)
    d.polygon([(x,y-h*.67),(x-width*1.25,y+h*.15),(x+width*1.25,y+h*.15)],fill=color)
    d.polygon([(x,y-h*.38),(x-width*1.5,y+h*.33),(x+width*1.5,y+h*.33)],fill=color)
    d.rectangle((x-4,y+h*.22,x+4,y+h*.52),fill=(50,39,33))

def finish(im,name):
    # Dark fade behind top navigation; transparent overlay to keep text readable.
    sh=Image.new('RGBA',(W,H)); sd=ImageDraw.Draw(sh)
    for x in range(W):
        alpha=int(170*max(0,(x-490)/(W-490)))
        sd.line([(x,0),(x,H)],fill=(3,12,27,alpha))
    im.alpha_composite(sh)
    im.convert('RGB').save(OUT/f'{name}.jpg',quality=89, optimize=True)

# Kerst: nachtblauw, besneeuwde bomen, huisjes en verlichting.
random.seed(22)
im=gradient((6,23,61),(15,66,82)).convert('RGBA');d=ImageDraw.Draw(im)
for _ in range(95):
    x=random.randrange(0,W);y=random.randrange(0,185)
    r=random.choice([1,1,1,2]);d.ellipse((x-r,y-r,x+r,y+r),fill=(201,236,250,185))
for i in range(18):
    x=i*80-40;h=55+random.randrange(20,115)
    triangles(d,x,190,h,(11,65,61) if i%2 else (9,53,73))
d.polygon([(0,214),(145,169),(280,206),(400,179),(515,226),(0,H)],fill=(187,225,230,210))
# Cottage, bright glowing windows.
d.polygon([(38,166),(131,110),(222,166)],fill=(76,40,37));d.rectangle((50,162,210,209),fill=(87,48,43))
d.polygon([(25,167),(131,105),(235,167),(214,159),(131,119),(49,172)],fill=(234,241,244))
for x in [70,123,175]:
    d.rectangle((x,172,x+23,197),fill=(250,194,82));d.line((x+11,172,x+11,197),fill=(83,46,31),width=2)
for i in range(18):
    x=30+i*26; y=30+round(9*math.sin(i*.7))
    d.ellipse((x,y,x+6,y+6),fill=random.choice([(255,206,75),(246,93,67),(102,255,134)]))
finish(im,'kerst')

# Winter: nachtblauw, maan, besneeuwde bergen.
im=gradient((6,25,59),(45,107,150)).convert('RGBA');d=ImageDraw.Draw(im)
for _ in range(140):
    x=random.randrange(W); y=random.randrange(175)
    r=random.choice([1,1,1,2]);d.ellipse((x-r,y-r,x+r,y+r),fill=(212,241,255,160))
d.ellipse((370,17,455,102),fill=(218,245,255,210))
peaks=[(-60,235),(120,68),(240,205),(380,96),(520,224),(665,76),(800,237),(1020,84),(1200,220),(1360,90)]
d.polygon(peaks+[(W,H),(0,H)],fill=(17,52,89,255))
for peak in [(120,68),(380,96),(665,76),(1020,84)]:
    x,y=peak;d.polygon([(x,y),(x-37,y+54),(x,y+35),(x+30,y+45)],fill=(231,250,255))
for x in range(10,1000,90):
    triangles(d,x,220,random.randrange(32,70),(11,55,83))
finish(im,'winter')

# Zomer: helder blauw water, palmbomen, oranje zonsondergang.
im=gradient((14,133,201),(126,213,215)).convert('RGBA');d=ImageDraw.Draw(im)
d.ellipse((390,18,510,138),fill=(255,233,95))
d.rectangle((0,159,W,H),fill=(15,140,185))
for i in range(40):
    x=random.randrange(W);y=random.randrange(162,H);l=random.randrange(10,75)
    d.line((x,y,x+l,y),fill=(156,232,229),width=1)
d.polygon([(0,196),(150,175),(280,190),(410,222),(0,H)],fill=(240,205,116))
for x in (60,245):
    d.line((x,221,x+26,66),fill=(85,71,36),width=13)
    for angle in range(0,360,36):
        ex=x+26+round(math.cos(math.radians(angle))*90)
        ey=66+round(math.sin(math.radians(angle))*42)
        d.polygon([(x+26,66),(ex,ey),(x+26+round(math.cos(math.radians(angle))*40),67+round(math.sin(math.radians(angle))*17))],fill=(24,121,77))
finish(im,'zomer')

# Space: starfield, planet, blue horizon, orbit.
im=gradient((2,5,29),(7,29,85)).convert('RGBA');d=ImageDraw.Draw(im)
for i in range(250):
    x=random.randrange(W);y=random.randrange(H);r=random.choice([1,1,1,1,2])
    d.ellipse((x-r,y-r,x+r,y+r),fill=random.choice([(237,247,255),(166,216,255),(153,154,252)]))
# Ringed planet.
d.ellipse((340,8,520,188),fill=(69,100,167))
d.arc((289,64,572,144),-8,187,fill=(165,216,255),width=8)
d.arc((303,75,568,146),-8,182,fill=(221,235,255),width=3)
# A glowing blue planetary horizon.
d.ellipse((-150,168,1150,695),fill=(4,75,130))
d.arc((-150,166,1150,698),180,355,fill=(59,218,255),width=7)
d.arc((-165,175,1165,698),180,355,fill=(128,134,255),width=2)
finish(im,'space')
print('Vier thema-afbeeldingen gemaakt in skins/')
