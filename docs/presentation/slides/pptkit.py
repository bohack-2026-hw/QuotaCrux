"""Thin helpers over python-pptx: px-based layout, CJK fonts, transitions and entrance/emphasis animations."""
from lxml import etree
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

PX = 6350  # 1920 px == 13.333 in

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
NSDECL = " ".join(f'xmlns:{k}="{v}"' for k, v in NS.items())

import os as _os

CJK = "PingFang SC"   # macOS; Windows substitutes its own CJK sans
SERIF = "Georgia"
NUM = "Arial"         # Latin text and figures: present on macOS, Windows and in WPS
MONO = "Menlo"
KAI = "楷体"


def px(v):
    return Emu(int(round(v * PX)))


def rgb(h):
    return RGBColor.from_string(h.lstrip("#"))


def frag(xml):
    return etree.fromstring(f"<root {NSDECL}>{xml}</root>")[0]


# ---------------------------------------------------------------- shapes
def set_alpha(fill_elm_parent, alpha):
    """Add <a:alpha> to the first srgbClr under the given element."""
    clr = fill_elm_parent.find(".//" + qn("a:srgbClr"))
    if clr is not None:
        a = etree.SubElement(clr, qn("a:alpha"))
        a.set("val", str(int(alpha * 100000)))


def shape(slide, kind, x, y, w, h, fill=None, line=None, line_w=2, alpha=None, name=None, adj=None,
          dash=None, rot=0):
    shp = slide.shapes.add_shape(kind, px(x), px(y), px(w), px(h))
    shp.shadow.inherit = False
    if fill:
        shp.fill.solid()
        shp.fill.fore_color.rgb = rgb(fill)
        if alpha is not None:
            set_alpha(shp._element.spPr.find(qn("a:solidFill")), alpha)
    else:
        shp.fill.background()
    if line:
        shp.line.color.rgb = rgb(line)
        shp.line.width = px(line_w)
        if dash:
            ln = shp._element.spPr.find(qn("a:ln"))
            pd = etree.SubElement(ln, qn("a:prstDash"))
            pd.set("val", dash)
            ln.set("cap", "rnd")
    else:
        shp.line.fill.background()
    if adj:
        for i, v in enumerate(adj):
            shp.adjustments[i] = v
    if name:
        shp.name = name
    if rot:
        shp.rotation = rot
    # strip the theme style so nothing (shadow, text colour) leaks in
    st = shp._element.find(qn("p:style"))
    if st is not None:
        shp._element.remove(st)
    return shp


def rect(slide, x, y, w, h, fill, radius=None, **kw):
    if radius is None:
        return shape(slide, MSO_SHAPE.RECTANGLE, x, y, w, h, fill, **kw)
    s = shape(slide, MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h, fill, **kw)
    s.adjustments[0] = min(0.5, radius / min(w, h))
    return s


def oval(slide, cx, cy, r, fill, **kw):
    return shape(slide, MSO_SHAPE.OVAL, cx - r, cy - r, 2 * r, 2 * r, fill, **kw)


def line(slide, x1, y1, x2, y2, color, w=2, dash=None, alpha=None, name=None, arrow=False):
    ln = slide.shapes.add_connector(1, px(x1), px(y1), px(x2), px(y2))
    ln.line.color.rgb = rgb(color)
    ln.line.width = px(w)
    lnx = ln._element.spPr.find(qn("a:ln"))
    lnx.set("cap", "rnd")
    if alpha is not None:
        set_alpha(lnx, alpha)
    if dash:
        pd = etree.SubElement(lnx, qn("a:prstDash"))
        pd.set("val", dash)
    if arrow:
        te = etree.SubElement(lnx, qn("a:tailEnd"))
        te.set("type", "triangle"); te.set("w", "med"); te.set("len", "med")
    st = ln._element.find(qn("p:style"))
    if st is not None:
        ln._element.remove(st)
    if name:
        ln.name = name
    return ln


def pic(slide, path, x, y, w=None, h=None, name=None, rot=0):
    p = slide.shapes.add_picture(path, px(x), px(y), px(w) if w else None, px(h) if h else None)
    if name:
        p.name = name
    if rot:
        p.rotation = rot
    return p


# ---------------------------------------------------------------- text
def _style_run(run, size, color, bold=False, font=CJK, latin=None, italic=False, spc=None, alpha=None,
               outline=None):
    f = run.font
    f.size = Pt(size)
    f.bold = bold
    f.italic = italic
    rPr = run._r.get_or_add_rPr()
    if outline:
        ln = etree.SubElement(rPr, qn("a:ln"))
        ln.set("w", str(int(outline[1] * 12700)))
        sf = etree.SubElement(ln, qn("a:solidFill"))
        c = etree.SubElement(sf, qn("a:srgbClr"))
        c.set("val", outline[0].lstrip("#"))
        etree.SubElement(rPr, qn("a:noFill"))
    else:
        f.color.rgb = rgb(color)
        if alpha is not None:
            set_alpha(rPr, alpha)
    lat = etree.SubElement(rPr, qn("a:latin"))
    lat.set("typeface", latin or font)
    ea = etree.SubElement(rPr, qn("a:ea"))
    ea.set("typeface", font)
    cs = etree.SubElement(rPr, qn("a:cs"))
    cs.set("typeface", font)
    if spc is not None:
        rPr.set("spc", str(int(spc * 100)))


def text(slide, x, y, w, h, paras, size=20, color="#111111", bold=False, font=CJK, latin=NUM,
         align="l", anchor="t", spacing=None, italic=False, spc=None, name=None, wrap=True,
         space_after=0, alpha=None, outline=None, margin=0):
    """paras: str | list of paragraphs; a paragraph is str or list of (text, overrides) runs."""
    tb = slide.shapes.add_textbox(px(x), px(y), px(w), px(h))
    tf = tb.text_frame
    tf.word_wrap = wrap
    tf.auto_size = None
    for side in ("left", "right", "top", "bottom"):
        setattr(tf, f"margin_{side}", px(margin))
    tf.vertical_anchor = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}[anchor]
    if isinstance(paras, str):
        paras = [paras]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}[align]
        if spacing:
            p.line_spacing = spacing
        if space_after:
            p.space_after = Pt(space_after)
        runs = [(para, {})] if isinstance(para, str) else para
        for t, ov in runs:
            r = p.add_run()
            r.text = t
            st = dict(size=size, color=color, bold=bold, font=font, latin=latin, italic=italic, spc=spc,
                      alpha=alpha, outline=outline)
            st.update(ov)
            _style_run(r, **st)
    if name:
        tb.name = name
    return tb


# ---------------------------------------------------------------- background & transitions
def set_bg(slide, image_path):
    _, rid = slide.part.get_or_add_image_part(image_path)
    cSld = slide._element.find(qn("p:cSld"))
    old = cSld.find(qn("p:bg"))
    if old is not None:
        cSld.remove(old)
    bg = frag(f'<p:bg><p:bgPr><a:blipFill dpi="0" rotWithShape="1"><a:blip r:embed="{rid}"/><a:srcRect/>'
              f'<a:stretch><a:fillRect/></a:stretch></a:blipFill><a:effectLst/></p:bgPr></p:bg>')
    cSld.insert(0, bg)


def set_transition(slide, kind="morph", dur=1200):
    if kind == "morph":
        xml = ('<mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">'
               '<mc:Choice xmlns:p159="http://schemas.microsoft.com/office/powerpoint/2015/09/main" Requires="p159">'
               f'<p:transition xmlns:p14="http://schemas.microsoft.com/office/powerpoint/2010/main" spd="slow" p14:dur="{dur}">'
               '<p159:morph option="byObject"/></p:transition></mc:Choice>'
               '<mc:Fallback><p:transition spd="slow"><p:fade/></p:transition></mc:Fallback></mc:AlternateContent>')
    else:
        xml = f'<p:transition spd="slow"><p:fade/></p:transition>'
    el = frag(xml)
    root = slide._element
    anchor = root.find(qn("p:clrMapOvr"))
    anchor.addnext(el)


# ---------------------------------------------------------------- animations
class Timeline:
    """Collects effects for one slide. All effects auto-play after the slide transition,
    each with its own delay (ms) — the presenter only clicks to change slides."""

    def __init__(self, slide):
        self.slide = slide
        self.fx = []
        self.grp = {}

    def add(self, shp, kind, delay=0, dur=600, **kw):
        sid = shp.shape_id
        g = self.grp.get(sid, -1) + 1
        self.grp[sid] = g
        is_sp = shp._element.tag == qn("p:sp")
        self.fx.append(dict(sid=sid, kind=kind, delay=int(delay), dur=int(dur), grp=g, sp=is_sp, kw=kw))
        return self

    # convenience
    def fade(self, s, d=0, dur=600, **kw):
        return self.add(s, "fade", d, dur, **kw)

    def rise(self, s, d=0, dur=800, **kw):
        return self.add(s, "rise", d, dur, **kw)

    def zoom(self, s, d=0, dur=700, **kw):
        return self.add(s, "zoom", d, dur, **kw)

    def pop(self, s, d=0, dur=600, **kw):
        return self.add(s, "pop", d, dur, **kw)

    def wipe(self, s, d=0, dur=700, direction="left", **kw):
        return self.add(s, "wipe", d, dur, direction=direction, **kw)

    def spin(self, s, d=0, dur=800, deg=10, **kw):
        return self.add(s, "spin", d, dur, deg=deg, **kw)

    def path(self, s, d=0, dur=2000, p="M 0 0 L 0.1 0 E", loop=False, **kw):
        return self.add(s, "path", d, dur, p=p, loop=loop, **kw)

    def flyin(self, s, d=0, dur=800, dx=-0.1, dy=0.0, **kw):
        return self.add(s, "flyin", d, dur, dx=dx, dy=dy, **kw)

    # ------------------------------------------------------------ xml
    def build(self):
        if not self.fx:
            return
        ids = iter(range(5, 100000))
        nid = lambda: next(ids)

        def tgt(sid):
            return f'<p:tgtEl><p:spTgt spid="{sid}"/></p:tgtEl>'

        def setvis(sid):
            return (f'<p:set><p:cBhvr><p:cTn id="{nid()}" dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/>'
                    f'</p:stCondLst></p:cTn>{tgt(sid)}<p:attrNameLst><p:attrName>style.visibility</p:attrName>'
                    f'</p:attrNameLst></p:cBhvr><p:to><p:strVal val="visible"/></p:to></p:set>')

        def anim(sid, attr, vals, dur, ease=True):
            tav = "".join(f'<p:tav tm="{tm}"><p:val><p:strVal val="{v}"/></p:val></p:tav>' for tm, v in vals)
            e = ' decel="100000"' if ease else ""
            return (f'<p:anim calcmode="lin" valueType="num"><p:cBhvr additive="base"><p:cTn id="{nid()}" '
                    f'dur="{dur}" fill="hold"{e}/>{tgt(sid)}<p:attrNameLst><p:attrName>{attr}</p:attrName>'
                    f'</p:attrNameLst></p:cBhvr><p:tavLst>{tav}</p:tavLst></p:anim>')

        def effect(sid, flt, dur, transition="in"):
            return (f'<p:animEffect transition="{transition}" filter="{flt}"><p:cBhvr><p:cTn id="{nid()}" '
                    f'dur="{dur}"/>{tgt(sid)}</p:cBhvr></p:animEffect>')

        pars = []
        for i, f in enumerate(self.fx):
            sid, dur, kw = f["sid"], f["dur"], f["kw"]
            node = "afterEffect" if i == 0 else "withEffect"
            ctn_id = nid()
            extra = ""
            iterate = ""
            if kw.get("letters"):
                iterate = f'<p:iterate type="lt"><p:tmPct val="{kw.get("lt_pct", 12000)}"/></p:iterate>'
            k = f["kind"]
            if k == "fade":
                preset, cls, sub = 10, "entr", 0
                kids = setvis(sid) + effect(sid, "fade", dur)
            elif k == "rise":
                preset, cls, sub = 42, "entr", 0
                off = kw.get("off", 0.06)
                kids = (setvis(sid) + effect(sid, "fade", dur)
                        + anim(sid, "ppt_x", [(0, "#ppt_x"), (100000, "#ppt_x")], dur)
                        + anim(sid, "ppt_y", [(0, f"#ppt_y+{off}"), (100000, "#ppt_y")], dur))
            elif k == "flyin":
                preset, cls, sub = 2, "entr", 8
                dx, dy = kw["dx"], kw["dy"]
                kids = (setvis(sid) + effect(sid, "fade", int(dur * 0.6))
                        + anim(sid, "ppt_x", [(0, f"#ppt_x{dx:+}"), (100000, "#ppt_x")], dur)
                        + anim(sid, "ppt_y", [(0, f"#ppt_y{dy:+}"), (100000, "#ppt_y")], dur))
            elif k == "zoom":
                preset, cls, sub = 53, "entr", 16
                kids = (setvis(sid)
                        + anim(sid, "ppt_w", [(0, "0"), (100000, "#ppt_w")], dur)
                        + anim(sid, "ppt_h", [(0, "0"), (100000, "#ppt_h")], dur)
                        + effect(sid, "fade", dur))
            elif k == "pop":
                preset, cls, sub = 53, "entr", 16
                kids = (setvis(sid)
                        + anim(sid, "ppt_w", [(0, "0"), (65000, "#ppt_w*1.12"), (100000, "#ppt_w")], dur, False)
                        + anim(sid, "ppt_h", [(0, "0"), (65000, "#ppt_h*1.12"), (100000, "#ppt_h")], dur, False)
                        + effect(sid, "fade", int(dur * 0.5)))
            elif k == "wipe":
                d = kw["direction"]
                preset, cls, sub = 22, "entr", {"left": 8, "right": 2, "up": 4, "down": 1}[d]
                kids = setvis(sid) + effect(sid, f"wipe({d})", dur)
            elif k == "spin":
                preset, cls, sub = 8, "emph", 0
                by = int(kw["deg"] * 60000)
                kids = (f'<p:animRot by="{by}"><p:cBhvr><p:cTn id="{nid()}" dur="{dur}" fill="hold" '
                        f'accel="30000" decel="50000"/>{tgt(sid)}<p:attrNameLst><p:attrName>r</p:attrName>'
                        f'</p:attrNameLst></p:cBhvr></p:animRot>')
            elif k == "play":
                preset, cls, sub = 1, "mediacall", 0
                kids = (f'<p:cmd type="call" cmd="playFrom(0.0)"><p:cBhvr><p:cTn id="{nid()}" dur="{dur}" fill="hold"/>'
                        f'{tgt(sid)}</p:cBhvr></p:cmd>')
            elif k == "path":
                preset, cls, sub = 0, "path", 0
                if kw.get("loop"):
                    extra = ' repeatCount="indefinite" autoRev="1"'
                kids = (f'<p:animMotion origin="layout" path="{kw["p"]}" pathEditMode="relative" rAng="0" '
                        f'ptsTypes=""><p:cBhvr><p:cTn id="{nid()}" dur="{dur}" fill="hold" accel="20000" '
                        f'decel="40000"/>{tgt(sid)}<p:attrNameLst><p:attrName>ppt_x</p:attrName>'
                        f'<p:attrName>ppt_y</p:attrName></p:attrNameLst></p:cBhvr><p:rCtr x="0" y="0"/>'
                        f'</p:animMotion>')
            else:
                raise ValueError(k)
            pars.append(f'<p:par><p:cTn id="{ctn_id}" presetID="{preset}" presetClass="{cls}" '
                        f'presetSubtype="{sub}" fill="hold" grpId="{f["grp"]}" nodeType="{node}"{extra}>'
                        f'<p:stCondLst><p:cond delay="{f["delay"]}"/></p:stCondLst>{iterate}'
                        f'<p:childTnLst>{kids}</p:childTnLst></p:cTn></p:par>')

        bld = "".join(f'<p:bldP spid="{f["sid"]}" grpId="{f["grp"]}" animBg="1"/>'
                      for f in self.fx if f["sp"])
        bld_all = ""
        xml = (f'<p:timing><p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot">'
               f'<p:childTnLst><p:seq concurrent="1" nextAc="seek"><p:cTn id="2" dur="indefinite" nodeType="mainSeq">'
               f'<p:childTnLst><p:par><p:cTn id="3" fill="hold"><p:stCondLst><p:cond delay="indefinite"/>'
               f'<p:cond evt="onBegin" delay="0"><p:tn val="2"/></p:cond></p:stCondLst><p:childTnLst>'
               f'<p:par><p:cTn id="4" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst>'
               f'<p:childTnLst>{"".join(pars)}</p:childTnLst></p:cTn></p:par>'
               f'</p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn>'
               f'<p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>'
               f'<p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst>'
               f'</p:seq>' + "".join(
                   f'<p:video><p:cMediaNode vol="0"><p:cTn id="{nid()}" fill="hold" display="1"><p:stCondLst>'
                   f'<p:cond delay="indefinite"/></p:stCondLst></p:cTn>{tgt(f["sid"])}</p:cMediaNode></p:video>'
                   for f in self.fx if f["kind"] == "play") + '</p:childTnLst></p:cTn></p:par></p:tnLst>'
               + (f'<p:bldLst>{bld}{bld_all}</p:bldLst>' if (bld or bld_all) else "") + '</p:timing>')
        el = frag(xml)
        root = self.slide._element
        old = root.find(qn("p:timing"))
        if old is not None:
            root.remove(old)
        # timing goes after transition (or AlternateContent wrapping it), before extLst
        ext = root.find(qn("p:extLst"))
        if ext is not None:
            ext.addprevious(el)
        else:
            root.append(el)
