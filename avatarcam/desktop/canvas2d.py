from collections import OrderedDict
import math
import time
from PIL.ImageQt import ImageQt
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPixmap, QColor, QRadialGradient, QPen, QImage
from PySide6.QtWidgets import QWidget


class Avatar2D(QWidget):
    def __init__(self, controller, capture=False, parent=None):
        super().__init__(parent); self.controller = controller; self.capture = capture
        self.start = time.monotonic(); self.paused_at=None; self.paused_seconds=0.; self.pixmaps = OrderedDict(); self.cache_revision = -1; self.pixmap_bytes = 0; self.drag_start = None; self.last_error=None
        self.animation_epoch=controller.animation_epoch
        self.setMinimumSize(260, 260); self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.controller.changed.connect(self.update)

    def frame(self, role, seconds):
        paths = self.controller.sets.get(role) or self.controller.sets.get('idle', [])
        if not paths: return None
        try:
            sequence = self.controller.store.load(paths)
            if not sequence.frames: return None
            index = sequence.index(seconds, self.controller.settings.animation_fps)
            if self.cache_revision != self.controller.store.revision:
                self.clear_cache(); self.cache_revision = self.controller.store.revision
            key = (sequence.signature, index)
            if key not in self.pixmaps:
                pixmap=QPixmap.fromImage(ImageQt(sequence.frames[index]))
                size=pixmap.width()*pixmap.height()*4
                budget=self.controller.performance['pixmap_mb']*1048576
                while self.pixmaps and self.pixmap_bytes+size>budget:
                    _,old=self.pixmaps.popitem(last=False); self.pixmap_bytes-=old.width()*old.height()*4
                if size<=budget:
                    self.pixmaps[key]=pixmap; self.pixmap_bytes+=size
                return pixmap
            self.pixmaps.move_to_end(key)
            return self.pixmaps[key]
        except (OSError, ValueError) as error:
            text=str(error)
            if text!=self.last_error: self.last_error=text; self.controller.notice.emit(text)
            return None

    def clear_cache(self):
        self.pixmaps.clear(); self.pixmap_bytes=0

    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.draw_avatar(painter)
        painter.end()

    def transparent_image(self):
        size = self.size().scaled(640, 640, Qt.AspectRatioMode.KeepAspectRatio)
        image = QImage(size, QImage.Format.Format_RGBA8888); image.fill(0)
        painter = QPainter(image); painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.scale(size.width()/max(1,self.width()), size.height()/max(1,self.height()))
        self.draw_avatar(painter, transparent=True); painter.end(); return image

    def draw_avatar(self, painter, transparent=False):
        c = self.controller; s = c.settings; face = c.visual_face; now=time.monotonic()
        if self.animation_epoch!=c.animation_epoch:
            self.animation_epoch=c.animation_epoch; self.start=now; self.paused_seconds=0.; self.paused_at=None
        if c.paused and self.paused_at is None: self.paused_at=now
        elif not c.paused and self.paused_at is not None:
            self.paused_seconds+=now-self.paused_at; self.paused_at=None
        seconds=(self.paused_at if self.paused_at is not None else now)-self.start-self.paused_seconds
        if transparent: pass
        elif self.capture: painter.fillRect(self.rect(), QColor(c.output_color))
        else:
            gradient = QRadialGradient(self.width()*.5,self.height()*.5,max(self.width(),self.height())*.7)
            gradient.setColorAt(0,QColor('#24272d')); gradient.setColorAt(1,QColor('#1a1c20'))
            painter.fillRect(self.rect(),gradient)
            painter.setPen(QPen(QColor('#2c2f34'),1))
            painter.drawEllipse(QRectF(self.width()*.16,self.height()*.74,self.width()*.68,self.height()*.16))
        speaking = c.speaking or face['jaw']>.18
        blinking = max(face['blinkLeft'],face['blinkRight'])>.5 if face['detected'] else seconds%4<.15
        role = 'blink' if blinking and c.sets.get('blink') else 'talk' if speaking else 'idle'
        mappings = c.preferences.get('expressions2d',{})
        if isinstance(mappings,dict) and c.expression in mappings and not speaking and not blinking:
            paths = mappings[c.expression]
            if isinstance(paths,list) and paths and all(isinstance(p,str) for p in paths):
                c.sets['_expression'] = paths; role = '_expression'
        pixmap = self.frame(role,seconds)
        if pixmap:
            size = min(self.width()*.68/pixmap.width(),self.height()*.82/pixmap.height())*s.avatar_scale
            width,height = pixmap.width()*size,pixmap.height()*size
            painter.save()
            painter.translate(self.width()*(.5+s.avatar_offset_x*.4)+face['yaw']*35,
                              self.height()*(.52+s.avatar_offset_y*.4)+face['pitch']*20)
            gesture = c.gesture_state(); extra = 0.
            if gesture:
                phase = gesture['progress']; envelope = math.sin(phase * math.pi)
                if gesture['name'] == 'wave': extra = math.sin(phase*math.pi*8)*12*envelope
                elif gesture['name'] == 'yes': painter.translate(0, math.sin(phase*math.pi*6)*18*envelope)
                elif gesture['name'] == 'no': painter.translate(math.sin(phase*math.pi*6)*22*envelope, 0)
                elif gesture['name'] == 'celebrate': painter.translate(0, -abs(math.sin(phase*math.pi*5))*30*envelope)
            painter.rotate(s.avatar_rotation+face['roll']*45+extra)
            painter.drawPixmap(QRectF(-width/2,-height/2,width,height),pixmap,QRectF(pixmap.rect()))
            painter.restore()
        else:
            painter.setPen(QColor('#a2b4ca')); painter.drawText(self.rect(),Qt.AlignmentFlag.AlignCenter,'Importe PNG, GIF ou WebP para começar')
        if s.pet_enabled and c.sets.get('pet'):
            pet = self.frame('pet_talk' if speaking and c.sets.get('pet_talk') else 'pet',seconds)
            if pet:
                size = min(self.width(),self.height())*.2*s.pet_size
                painter.drawPixmap(QRectF(self.width()*.78,self.height()*.72,size,size*pet.height()/pet.width()),pet,QRectF(pet.rect()))

    def mousePressEvent(self,event):
        if self.capture: return
        if event.button()==Qt.MouseButton.LeftButton:
            self.controller.record_change()
            s=self.controller.settings; self.drag_start=(event.position(),s.avatar_offset_x,s.avatar_offset_y)

    def mouseMoveEvent(self,event):
        if self.drag_start:
            point,x,y=self.drag_start; delta=event.position()-point; s=self.controller.settings
            s.avatar_offset_x=max(-.8,min(.8,x+delta.x()/max(1,self.width())*2.5))
            s.avatar_offset_y=max(-.8,min(.8,y+delta.y()/max(1,self.height())*2.5))
            self.controller.defer_save(); self.update()

    def mouseReleaseEvent(self,event): self.drag_start=None

    def wheelEvent(self,event):
        if self.capture: return
        self.controller.record_change()
        s=self.controller.settings; s.avatar_scale=max(.25,min(2.5,s.avatar_scale+event.angleDelta().y()/1200))
        self.controller.defer_save(); self.update()
